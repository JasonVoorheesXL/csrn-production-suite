from __future__ import annotations

import logging
import math
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable


_LOGGER = logging.getLogger("csrn.captions")


class CaptionWorkerDependencyError(RuntimeError):
    pass


_WINDOWS_DLL_DIRECTORY_HANDLES: list[Any] = []


def _add_windows_dll_directory(path: Path) -> None:
    if not path.is_dir():
        return
    text = str(path)
    current = os.environ.get("PATH", "")
    parts = [part for part in current.split(os.pathsep) if part]
    if text.casefold() not in {part.casefold() for part in parts}:
        os.environ["PATH"] = text + os.pathsep + current
    add_dll_directory = getattr(os, "add_dll_directory", None)
    if add_dll_directory is not None:
        try:
            _WINDOWS_DLL_DIRECTORY_HANDLES.append(add_dll_directory(text))
        except OSError:
            pass


def _discover_windows_cuda_dll_paths() -> list[Path]:
    candidates: list[Path] = []
    extra_paths = os.environ.get("CSRN_CUDA_DLL_PATHS", "")
    for raw_path in extra_paths.split(os.pathsep):
        if raw_path.strip():
            candidates.append(Path(raw_path.strip()))

    for env_name in ("CUDA_PATH", "CUDA_PATH_V12_8", "CUDA_PATH_V12_6", "CUDA_PATH_V12_5", "CUDA_PATH_V12_4"):
        value = os.environ.get(env_name)
        if value:
            candidates.append(Path(value) / "bin")

    cuda_root = Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "NVIDIA GPU Computing Toolkit" / "CUDA"
    if cuda_root.is_dir():
        candidates.extend(sorted(cuda_root.glob("v12*/bin"), reverse=True))

    program_files = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
    candidates.extend(program_files.glob("NVIDIA/CUDNN/v*/bin/12*/x64"))
    candidates.extend(program_files.glob("NVIDIA/CUDNN/v*/bin/x64"))

    user_profile = os.environ.get("USERPROFILE")
    if user_profile:
        downloads = Path(user_profile) / "Downloads"
        candidates.extend(downloads.glob("cudnn-windows-x86_64-*cuda12*/**/bin/x64"))

    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate).casefold()
        if key not in seen and candidate.is_dir():
            seen.add(key)
            unique.append(candidate)
    return unique


def _prepare_windows_cuda_dll_paths() -> None:
    for path in _discover_windows_cuda_dll_paths():
        _add_windows_dll_directory(path)


def _windows_dll_is_available(name: str, paths: list[Path] | None = None) -> bool:
    if shutil.which(name) is not None:
        return True
    for path in paths or _discover_windows_cuda_dll_paths():
        if path.joinpath(name).is_file():
            return True
    return False


@dataclass(frozen=True)
class CaptionWorkerSettings:
    device: str | int | None = None
    device_name: str = ""
    device_host_api: str = ""
    model_name: str = "small.en"
    sample_rate: int = 48000
    recognition_rate: int = 16000
    chunk_seconds: float = 5.0
    overlap_seconds: float = 1.4
    speech_threshold: float = 0.008
    capture_dtype: str = "float32"
    transcription_timeout_seconds: float = 20.0
    beam_size: int = 5
    prompt_terms: tuple[str, ...] = ()
    initial_prompt: str = ""


class CaptionRuntime:
    """Owns one live caption worker session for the local production app."""

    def __init__(
        self,
        *,
        caption_service: Any,
        load_broadcast_id: Callable[[], str],
        build_prompt_terms: Callable[[], list[str]] | None = None,
        worker_factory: Callable[..., ChannelCaptionWorker] | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.caption_service = caption_service
        self.load_broadcast_id = load_broadcast_id
        self.build_prompt_terms = build_prompt_terms or (lambda: [])
        self.worker_factory = worker_factory or ChannelCaptionWorker
        self.clock = clock
        self._lock = threading.Lock()
        self._worker: ChannelCaptionWorker | None = None
        self._thread: threading.Thread | None = None
        self._status: dict[str, Any] = {
            "running": False,
            "started_at": 0,
            "stopped_at": 0,
            "message": "Live captions are stopped.",
            "error": "",
            "stream_started_at": 0,
            "callback_count": 0,
            "last_callback_at": 0,
            "last_callback_age_seconds": None,
            "callback_stale": False,
            "last_audio_at": 0,
            "last_audio_channel": 0,
            "last_audio_level": 0.0,
            "channel_levels": {},
            "last_chunk_at": 0,
            "last_chunk_channel": 0,
            "last_chunk_level": 0.0,
            "last_caption_at": 0,
            "last_caption_channel": 0,
            "last_caption_text": "",
            "last_transcript_at": 0,
            "last_transcript_channel": 0,
            "last_transcript_text": "",
            "last_transcript_confidence": 0.0,
            "last_transcript_status": "",
            "last_transcribe_seconds": 0.0,
            "last_gain": 1.0,
            "model_device": "",
            "model_compute_type": "",
            "model_compute_reason": "",
            "capture_device": "",
            "capture_host_api": "",
            "capture_channels": 0,
            "channel_mappings": [],
            "hardware_levels": {},
            "audio_status": "",
        }

    def status(self) -> dict[str, Any]:
        with self._lock:
            self._reconcile_thread_locked()
            return dict(self._status)

    def start(self) -> dict[str, Any]:
        with self._lock:
            self._reconcile_thread_locked()
            if self._status["running"]:
                return dict(self._status)
            profile = self.caption_service.status().data["profile"]
            source_type = str(profile.get("source_type") or "manual")
            if source_type != "audio_device":
                self._status.update(
                    {
                        "running": False,
                        "message": "Choose Microphone / USB audio device before starting live captions.",
                        "error": "CAPTION_SOURCE_NOT_AUDIO_DEVICE",
                    }
                )
                return dict(self._status)
            device = str(profile.get("audio_device") or "").strip()
            if not device:
                self._status.update(
                    {
                        "running": False,
                        "message": "Choose an audio input before starting live captions.",
                        "error": "CAPTION_AUDIO_DEVICE_REQUIRED",
                    }
                )
                return dict(self._status)
            profile_update = {"enabled": True, "overlay_visible": True, "display_delay_ms": 0}
            try:
                if float(profile.get("minimum_confidence", 0.45)) > 0.45:
                    profile_update["minimum_confidence"] = 0.45
            except (TypeError, ValueError):
                profile_update["minimum_confidence"] = 0.45
            try:
                float(profile.get("speech_threshold", 0.00075))
            except (TypeError, ValueError):
                profile_update["speech_threshold"] = 0.00075
            self.caption_service.update_profile(profile_update)
            threshold = float(profile_update.get("speech_threshold", profile.get("speech_threshold") or CaptionWorkerSettings.speech_threshold))
            settings = CaptionWorkerSettings(
                device=device,
                device_name=str(profile.get("audio_device_name") or ""),
                device_host_api=str(profile.get("audio_device_host_api") or ""),
                model_name=str(
                    profile.get("caption_model")
                    # Round 15F: a frozen build's runtime hook sets this to
                    # the bundled CTranslate2 small.en directory so captions
                    # load offline. An explicit caption_model still wins.
                    or os.environ.get("CSRN_WHISPER_MODEL_DIR")
                    or CaptionWorkerSettings.model_name
                ),
                speech_threshold=threshold,
                chunk_seconds=5.0,
                overlap_seconds=1.4,
                capture_dtype=str(profile.get("audio_capture_dtype") or "float32"),
                prompt_terms=tuple(self.build_prompt_terms()),
            )
            worker = self.worker_factory(
                caption_service=self.caption_service,
                load_broadcast_id=self.load_broadcast_id,
                settings=settings,
                clock=self.clock,
                on_event=self._worker_event,
            )
            thread = threading.Thread(target=self._run_worker, args=(worker,), daemon=True)
            self._worker = worker
            self._thread = thread
            self._status.update(
                {
                    "running": True,
                    "started_at": int(self.clock()),
                    "stopped_at": 0,
                    "message": f"Live captions listening on {profile.get('audio_device_name') or device}.",
                    "error": "",
                    "stream_started_at": 0,
                    "callback_count": 0,
                    "last_callback_at": 0,
                    "last_callback_age_seconds": None,
                    "callback_stale": False,
                    "last_audio_at": 0,
                    "last_audio_channel": 0,
                    "last_audio_level": 0.0,
                    "channel_levels": {},
                    "last_chunk_at": 0,
                    "last_chunk_channel": 0,
                    "last_chunk_level": 0.0,
                    "last_caption_at": 0,
                    "last_caption_channel": 0,
                    "last_caption_text": "",
                    "last_transcript_at": 0,
                    "last_transcript_channel": 0,
                    "last_transcript_text": "",
                    "last_transcript_confidence": 0.0,
                    "last_transcript_status": "",
                    "last_transcribe_seconds": 0.0,
                    "last_gain": 1.0,
                    "model_device": "",
                    "model_compute_type": "",
                    "model_compute_reason": "",
                    "capture_device": "",
                    "capture_host_api": "",
                    "capture_channels": 0,
                    "capture_dtype": "",
                    "channel_mappings": [],
                    "hardware_levels": {},
                    "audio_status": "",
                }
            )
            thread.start()
            return dict(self._status)

    def stop(self) -> dict[str, Any]:
        worker = None
        thread = None
        with self._lock:
            worker = self._worker
            thread = self._thread
            if worker is not None:
                worker.stop()
            self._status.update(
                {
                    "running": False,
                    "stopped_at": int(self.clock()),
                    "message": "Live captions are stopped.",
                    "error": "",
                    "callback_stale": False,
                    "last_callback_age_seconds": None,
                    "channel_levels": {},
                    "hardware_levels": {},
                    "last_audio_level": 0.0,
                    "last_chunk_level": 0.0,
                    "audio_status": "",
                }
            )
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)
        with self._lock:
            if self._worker is worker:
                self._worker = None
                self._thread = None
            return dict(self._status)

    def _run_worker(self, worker: ChannelCaptionWorker) -> None:
        try:
            worker.run_forever()
        except Exception as exc:  # pragma: no cover - exercised through integration state.
            with self._lock:
                if self._worker is worker:
                    self._status.update(
                        {
                            "running": False,
                            "stopped_at": int(self.clock()),
                            "message": str(exc),
                            "error": exc.__class__.__name__,
                        }
                    )
                    self._worker = None
                    self._thread = None

    def _worker_event(self, event: dict[str, Any]) -> None:
        kind = str(event.get("type") or "")
        with self._lock:
            if kind == "callback":
                now = int(self.clock())
                self._status.update(
                    {
                        "callback_count": int(self._status.get("callback_count") or 0) + 1,
                        "last_callback_at": now,
                        "last_callback_age_seconds": 0,
                        "callback_stale": False,
                    }
                )
            elif kind == "audio":
                channel_levels = dict(self._status.get("channel_levels") or {})
                channel_levels[str(int(event.get("channel") or 0))] = round(float(event.get("level") or 0), 5)
                self._status.update(
                    {
                        "last_audio_at": int(self.clock()),
                        "last_audio_channel": int(event.get("channel") or 0),
                        "last_audio_level": round(float(event.get("level") or 0), 5),
                        "channel_levels": channel_levels,
                    }
                )
            elif kind == "chunk":
                self._status.update(
                    {
                        "last_chunk_at": int(self.clock()),
                        "last_chunk_channel": int(event.get("channel") or 0),
                        "last_chunk_level": round(float(event.get("level") or 0), 5),
                    }
                )
            elif kind == "caption":
                self._status.update(
                    {
                        "last_caption_at": int(self.clock()),
                        "last_caption_channel": int(event.get("channel") or 0),
                        "last_caption_text": str(event.get("text") or ""),
                        "last_transcript_at": int(self.clock()),
                        "last_transcript_channel": int(event.get("channel") or 0),
                        "last_transcript_text": str(event.get("text") or ""),
                        "last_transcript_confidence": round(float(event.get("confidence") or 0), 4),
                        "last_transcript_status": "caption",
                        "last_transcribe_seconds": round(float(event.get("seconds") or self._status.get("last_transcribe_seconds") or 0), 3),
                        "last_gain": round(float(event.get("gain") or self._status.get("last_gain") or 1), 2),
                    }
                )
            elif kind == "rejected_caption":
                self._status.update(
                    {
                        "last_transcript_at": int(self.clock()),
                        "last_transcript_channel": int(event.get("channel") or 0),
                        "last_transcript_text": str(event.get("text") or ""),
                        "last_transcript_confidence": round(float(event.get("confidence") or 0), 4),
                        "last_transcript_status": str(event.get("reason") or "rejected"),
                        "last_transcribe_seconds": round(float(event.get("seconds") or self._status.get("last_transcribe_seconds") or 0), 3),
                        "last_gain": round(float(event.get("gain") or self._status.get("last_gain") or 1), 2),
                    }
                )
            elif kind == "duplicate_caption":
                self._status.update(
                    {
                        "last_transcript_at": int(self.clock()),
                        "last_transcript_channel": int(event.get("channel") or 0),
                        "last_transcript_text": str(event.get("text") or ""),
                        "last_transcript_confidence": round(float(event.get("confidence") or 0), 4),
                        "last_transcript_status": "duplicate",
                        "last_transcribe_seconds": round(float(event.get("seconds") or self._status.get("last_transcribe_seconds") or 0), 3),
                        "last_gain": round(float(event.get("gain") or self._status.get("last_gain") or 1), 2),
                    }
                )
            elif kind == "empty_transcript":
                self._status.update(
                    {
                        "last_transcript_at": int(self.clock()),
                        "last_transcript_channel": int(event.get("channel") or 0),
                        "last_transcript_text": "",
                        "last_transcript_confidence": 0.0,
                        "last_transcript_status": "empty",
                        "last_transcribe_seconds": round(float(event.get("seconds") or self._status.get("last_transcribe_seconds") or 0), 3),
                        "last_gain": round(float(event.get("gain") or self._status.get("last_gain") or 1), 2),
                    }
                )
            elif kind == "transcribing":
                self._status.update(
                    {
                        "last_transcript_at": int(self.clock()),
                        "last_transcript_channel": int(event.get("channel") or 0),
                        "last_transcript_text": "",
                        "last_transcript_confidence": 0.0,
                        "last_transcript_status": "transcribing",
                        "last_transcribe_seconds": 0.0,
                    }
                )
            elif kind == "transcript_error":
                self._status.update(
                    {
                        "last_transcript_at": int(self.clock()),
                        "last_transcript_channel": int(event.get("channel") or 0),
                        "last_transcript_text": str(event.get("message") or ""),
                        "last_transcript_confidence": 0.0,
                        "last_transcript_status": "WHISPER_ERROR",
                        "last_transcribe_seconds": round(float(event.get("seconds") or 0), 3),
                    }
                )
            elif kind == "ready":
                mappings = list(event.get("mappings") or [])
                self._status.update(
                    {
                        "stream_started_at": int(self.clock()),
                        "message": f"Live captions listening on {event.get('device_name') or 'audio device'}.",
                        "capture_device": str(event.get("device_name") or ""),
                        "capture_host_api": str(event.get("host_api") or ""),
                        "capture_channels": int(event.get("capture_channels") or 0),
                        "capture_dtype": str(event.get("capture_dtype") or ""),
                        "channel_mappings": mappings,
                    }
                )
            elif kind == "opening_stream":
                self._status.update(
                    {
                        "message": f"Opening live caption stream on {event.get('device_name') or 'audio device'}.",
                        "capture_device": str(event.get("device_name") or ""),
                        "capture_host_api": str(event.get("host_api") or ""),
                        "capture_channels": int(event.get("capture_channels") or 0),
                        "capture_dtype": str(event.get("capture_dtype") or ""),
                        "channel_mappings": list(event.get("mappings") or []),
                    }
                )
            elif kind == "model":
                self._status.update(
                    {
                        "model_device": str(event.get("device") or ""),
                        "model_compute_type": str(event.get("compute_type") or ""),
                        "model_compute_reason": str(event.get("reason") or ""),
                    }
                )
            elif kind == "hardware_audio":
                self._status["hardware_levels"] = {
                    str(index): round(float(level or 0), 5)
                    for index, level in dict(event.get("levels") or {}).items()
                }
            elif kind == "audio_status":
                self._status["audio_status"] = str(event.get("status") or "")

    def _reconcile_thread_locked(self) -> None:
        thread = self._thread
        now = int(self.clock())
        last_callback_at = int(self._status.get("last_callback_at") or 0)
        if self._status.get("running") and last_callback_at:
            age = max(0, now - last_callback_at)
            self._status["last_callback_age_seconds"] = age
            self._status["callback_stale"] = age > 3
            if age > 3:
                self._status["audio_status"] = (
                    f"No audio callbacks received for {age}s. "
                    "The stream may be open but stalled."
                )
        elif self._status.get("running") and self._status.get("stream_started_at"):
            age = max(0, now - int(self._status.get("stream_started_at") or 0))
            self._status["last_callback_age_seconds"] = None
            self._status["callback_stale"] = age > 3
            if age > 3:
                self._status["audio_status"] = (
                    "Audio stream opened, but no callbacks have been received."
                )
        if (
            self._status.get("running")
            and self._status.get("last_transcript_status") == "transcribing"
            and self._status.get("last_transcript_at")
        ):
            transcribe_age = max(0, now - int(self._status.get("last_transcript_at") or 0))
            self._status["last_transcribe_seconds"] = transcribe_age
            if transcribe_age > 10:
                self._status["audio_status"] = (
                    f"Whisper transcription has been running for {transcribe_age}s."
                )
        if thread is not None and not thread.is_alive() and self._status.get("running"):
            self._status.update(
                {
                    "running": False,
                    "stopped_at": int(self.clock()),
                    "message": self._status.get("message") or "Live captions stopped.",
                }
            )


def rms_level(samples: Any) -> float:
    """Return normalized RMS for a numeric sample sequence."""
    try:
        size = len(samples)
    except TypeError:
        return 0.0
    if not size:
        return 0.0
    total = 0.0
    for value in samples:
        numeric = float(value)
        total += numeric * numeric
    return math.sqrt(total / size)


def resample_48k_to_16k(samples: Any) -> Any:
    """Exact 3:1 decimation used for the P4next 48 kHz commissioning profile."""
    return samples[::3]


def normalize_caption_audio(samples: Any, current_level: float, *, target_level: float = 0.035, max_gain: float = 40.0) -> tuple[Any, float]:
    if current_level <= 0:
        return samples, 1.0
    gain = min(max_gain, max(1.0, target_level / current_level))
    if gain <= 1.0:
        return samples, 1.0
    if isinstance(samples, list):
        return [float(sample) * gain for sample in samples], gain
    return samples * gain, gain


def coerce_audio_device_id(device: Any) -> str | int | None:
    if device is None:
        return None
    value = str(device).strip()
    if not value:
        return None
    if value.isdigit():
        return int(value)
    return value


def caption_channel_mappings(profile: dict[str, Any]) -> list[dict[str, int]]:
    """Return enabled logical-to-hardware channel assignments."""
    mappings: list[dict[str, int]] = []
    for item in profile.get("channels", []):
        if not item.get("enabled", False):
            continue
        logical_channel = int(item["channel"])
        hardware_channel = int(item.get("device_channel", logical_channel))
        if hardware_channel < 1:
            raise RuntimeError("Caption hardware channels must be 1 or greater.")
        mappings.append(
            {"channel": logical_channel, "device_channel": hardware_channel}
        )
    return mappings


def _normalized_device_name(value: Any) -> str:
    return " ".join(str(value or "").lower().split())


def _is_wdm_ks_host(host_name: str) -> bool:
    normalized = _normalized_device_name(host_name)
    return "wdm-ks" in normalized or "wdm ks" in normalized


def _caption_host_preference(host_name: str, device_name: str = "") -> int:
    host = host_name.lower()
    name = device_name.lower()
    if "directsound" in host and "cable output" in name:
        return 5
    if "wasapi" in host:
        return 4
    if "directsound" in host:
        return 3
    if "mme" in host:
        return 2
    return 1


def resolve_audio_input_device(
    sd: Any,
    requested_device: Any,
    requested_name: str,
    minimum_channels: int,
    requested_host_api: str = "",
) -> tuple[int | str | None, dict[str, Any], str]:
    """Resolve volatile PortAudio indices and prefer a full-channel endpoint."""
    devices = list(sd.query_devices())
    host_apis = list(sd.query_hostapis()) if hasattr(sd, "query_hostapis") else []
    requested = coerce_audio_device_id(requested_device)
    requested_normalized = _normalized_device_name(requested_name)
    requested_host_normalized = _normalized_device_name(requested_host_api)

    candidates: list[tuple[tuple[int, int, int, int, int], int, dict[str, Any], str]] = []
    for index, raw in enumerate(devices):
        device = dict(raw)
        channels = int(device.get("max_input_channels", 0) or 0)
        if channels < minimum_channels:
            continue
        raw_host_index = device.get("hostapi", -1)
        host_index = int(raw_host_index if raw_host_index is not None else -1)
        host_name = ""
        if 0 <= host_index < len(host_apis):
            host_name = str(host_apis[host_index].get("name", ""))
        if _is_wdm_ks_host(host_name):
            continue
        name = str(device.get("name", f"Input {index}"))
        normalized = _normalized_device_name(name)
        exact_index = int(isinstance(requested, int) and requested == index)
        exact_name = int(bool(requested_normalized) and normalized == requested_normalized)
        exact_host = int(
            bool(requested_host_normalized)
            and _normalized_device_name(host_name) == requested_host_normalized
        )
        partial_name = int(
            bool(requested_normalized)
            and (requested_normalized in normalized or normalized in requested_normalized)
        )
        host_preference = _caption_host_preference(host_name, name)
        candidates.append(
            (
                (exact_name, partial_name, channels, exact_host, host_preference + exact_index),
                index,
                device,
                host_name,
            )
        )

    if not candidates:
        raise RuntimeError(
            f"No audio endpoint provides the required {minimum_channels} input channel(s)."
        )
    candidates.sort(key=lambda item: item[0], reverse=True)
    _, index, device, host_name = candidates[0]
    return index, device, host_name


def likely_silence_hallucination(text: str, confidence: float, level: float) -> bool:
    normalized = " ".join(text.lower().strip(" .,!?:;\"'").split())
    known_noise = {
        "cheers",
        "i love you",
        "thank you",
        "thanks for watching",
        "you",
    }
    if normalized in known_noise and confidence < 0.8:
        return True
    if likely_non_speech_caption(text):
        return True
    word_count = len(normalized.split())
    if word_count <= 2 and confidence < 0.5 and level < 0.003:
        return True
    return False


def clean_football_caption_text(text: str, prompt_terms: tuple[str, ...] = ()) -> str:
    cleaned = " ".join(str(text or "").split())
    if not cleaned:
        return ""

    cleaned = re.sub(r"^(?:yeah|uh|um|okay|ok)[, ]+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bhas a ball\b", "has the ball", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bhas ball\b", "has the ball", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(
        r"\b(?:all|awl)\s+on\s+the\s+(\d{1,2})(?:\s|-)?yard\s+line\b",
        r"ball on the \1-yard line",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\b(?:all|awl)\s+on\s+the\s+(\d{1,2})\b",
        r"ball on the \1",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\b(first|1st)\s+(?:and|in)\s+(?:count|can|tin|tent|10)\b",
        "first and ten",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"^(?:of|off)\s+yard\s*line\s+(?=it\s+is\s+first\s+and\s+ten\b)",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"^(?:backyard|back\s+yard)\s+line\s+(?=it\s+is\s+first\s+and\s+ten\b)",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\bkicker\s+turner\b", "kick returner", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bkicker\s+turned\b", "kick return", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bkicker\s+turn\b", "kick return", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bdarkw(?:e|a|i)s\s+williams\b", "Darquez Williams", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bdarkwez\s+williams\b", "Darquez Williams", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bquiz\s+williams\b", "Jazz Williams", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bhere's\s+it\s+out\b", "he airs it out", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^open[.!?, ]+(?=he(?:'s| is)\s+at\b)", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"^return\s+(?=[A-Z][a-z]+ has the ball\b)", "After the return, ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bcaledoni\b", "Caledonia", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bleads\s+6th\s+and\b", "leads six to nothing", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(
        r"\b(\d{1,2})\s+yard\s+line\s+\d{1,2}\b",
        r"\1-yard line",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"^line\s+(?:\d{1,2}\s+){2,}\d{1,2}[.!?]?$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"^from\s+[a-z][a-z .'-]{2,30}[.!?]?$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"^5-(?=\d{2}-\d{2}-5\s+touchdown\b)",
        "50-",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(
        r"\b(?:cover layers|coverlairs|caviler(?:s)?|cavalier players)\b",
        "Cavaliers",
        cleaned,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\bfrom the (\d{1,2})(?:st|nd|rd|th)\b", r"from the \1", cleaned, flags=re.IGNORECASE)
    before_dangling_trim = cleaned
    cleaned = re.sub(r"[, ]+\b(?:it is|it's|and|on|at|with|for|to|the kick|takes the)\b[.!?]?$", "", cleaned, flags=re.IGNORECASE)
    if cleaned != before_dangling_trim:
        cleaned = cleaned.rstrip(" .!?")

    for term in prompt_terms:
        canonical = " ".join(str(term or "").split())
        if not canonical or len(canonical) < 3:
            continue
        if canonical.lower() == "cavaliers":
            cleaned = re.sub(r"\bcavaliers players\b", "Cavaliers", cleaned, flags=re.IGNORECASE)
        if canonical.lower() == "caledonia":
            cleaned = re.sub(r"\bcaledonian\b", "Caledonia", cleaned, flags=re.IGNORECASE)

    cleaned = cleaned[:1].upper() + cleaned[1:] if cleaned else cleaned
    if likely_broken_caption_fragment(cleaned, prompt_terms):
        return ""
    return cleaned


def likely_broken_caption_fragment(text: str, prompt_terms: tuple[str, ...] = ()) -> bool:
    normalized = " ".join(str(text or "").casefold().strip(" .,!?:;\"'").split())
    if not normalized:
        return False
    team_terms = {
        "caledonia",
        "cavaliers",
        *{
            " ".join(str(term or "").casefold().split())
            for term in prompt_terms
            if " ".join(str(term or "").split())
        },
    }
    team_pattern = "|".join(re.escape(term) for term in sorted(team_terms, key=len, reverse=True) if term)
    if team_pattern and re.fullmatch(rf"(?:down|from|after returning)\s+(?:{team_pattern})", normalized):
        return True
    if re.fullmatch(r"(?:and then|and now)\s+[a-z][a-z'-]{2,20}", normalized):
        return True
    return False


def normalize_caption_for_duplicate(text: str) -> str:
    normalized = re.sub(r"[^\w\s-]", " ", str(text or "").casefold())
    return " ".join(normalized.split())


def likely_non_speech_caption(text: str) -> bool:
    normalized = " ".join(text.lower().strip(" .,!?:;\"'").split())
    if not normalized:
        return False
    tokens = normalized.split()
    non_speech_tokens = {
        "woof",
        "bark",
        "arf",
        "ruff",
        "meow",
        "laugh",
        "laughter",
        "applause",
        "music",
        "beep",
        "hmm",
        "uh",
        "um",
    }
    if all(token in non_speech_tokens for token in tokens):
        return True
    if len(tokens) <= 5 and len(set(tokens)) == 1 and tokens[0] in non_speech_tokens:
        return True
    return False


def caption_initial_prompt(extra_terms: tuple[str, ...] = ()) -> str:
    terms = [
        "Caledonia",
        "Cavaliers",
        "first and ten",
        "second down",
        "third down",
        "fourth down",
        "touchdown",
        "touchdown run",
        "touchdown pass",
        "field goal",
        "extra point",
        "two point conversion",
        "punt",
        "punt return",
        "kickoff",
        "kick return",
        "kick returner",
        "onside kick",
        "interception",
        "pick six",
        "fumble",
        "fumble recovery",
        "turnover",
        "sack",
        "tackle for loss",
        "flag on the play",
        "holding",
        "false start",
        "offsides",
        "pass interference",
        "personal foul",
        "yard line",
        "line of scrimmage",
        "goal line",
        "end zone",
        "red zone",
        "sideline",
        "near side",
        "far side",
        "wide side of the field",
        "left to right",
        "right to left",
        "press box",
        "driving left to right",
        "driving right to left",
        "has the ball",
        "takes over",
        "possession",
        "quarterback",
        "running back",
        "receiver",
        "wide receiver",
        "tight end",
        "offensive line",
        "defensive line",
        "linebacker",
        "defensive back",
        "cornerback",
        "safety",
        "defense",
        "offense",
        "special teams",
        "handoff",
        "pass complete",
        "pass incomplete",
        "airs it out",
        "screen pass",
        "slant route",
        "far hash",
        "near hash",
        "first quarter",
        "second quarter",
        "third quarter",
        "fourth quarter",
        "halftime",
        "overtime",
        "six to nothing",
        "seven to nothing",
    ]
    for term in extra_terms:
        clean = " ".join(str(term or "").split())
        if clean and clean.lower() not in {item.lower() for item in terms}:
            terms.append(clean)
    return (
        "Live American football sportscast captions. Prefer complete play calls "
        "and preserve school names, mascots, numbers, downs, distances, and yard lines. "
        "Examples: Caledonia has the ball on the 45-yard line; first and ten Cavaliers. "
        "Use 'ball on the 45-yard line', not 'all on the 45-yard line'. "
        "Use 'first and ten', not 'first and count'. "
        "Do not transcribe crowd noise, barking, music, applause, or non-speech sounds. "
        "Useful vocabulary: " + "; ".join(terms) + "."
    )


class ChannelCaptionWorker:
    """Optional local faster-whisper worker for caption-bus input channels."""

    _model_cache: dict[tuple[Any, str, str, str], Any] = {}
    _model_lock = threading.Lock()

    def __init__(
        self,
        *,
        caption_service: Any,
        load_broadcast_id: Callable[[], str],
        settings: CaptionWorkerSettings | None = None,
        clock: Callable[[], float] = time.time,
        on_event: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.caption_service = caption_service
        self.load_broadcast_id = load_broadcast_id
        self.settings = settings or CaptionWorkerSettings()
        self.clock = clock
        self.on_event = on_event or (lambda event: None)
        self._recent_captions: list[tuple[float, str]] = []
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def run_forever(self) -> None:
        np, sd, model_class = self._optional_dependencies()
        profile = self.caption_service.status().data["profile"]
        mappings = caption_channel_mappings(profile)
        if not mappings:
            raise RuntimeError("No caption channels are enabled.")
        required_hardware_channels = max(item["device_channel"] for item in mappings)
        resolved_device, device_info, host_api = resolve_audio_input_device(
            sd,
            self.settings.device,
            self.settings.device_name,
            required_hardware_channels,
            self.settings.device_host_api,
        )
        capture_channels = int(device_info.get("max_input_channels", 0) or 0)
        if capture_channels < required_hardware_channels:
            raise RuntimeError(
                f"Selected audio endpoint has {capture_channels} inputs, but hardware channel "
                f"{required_hardware_channels} is assigned."
            )
        capture_dtype = str(self.settings.capture_dtype or "float32").strip()
        if capture_dtype not in {"float32", "int16"}:
            capture_dtype = "float32"
        block_queue: queue.Queue[Any] = queue.Queue(maxsize=16)

        def callback(indata, frames, timing, status) -> None:
            del frames, timing
            self.on_event({"type": "callback"})
            if status:
                self.on_event({"type": "audio_status", "status": str(status)})
            try:
                block_queue.put_nowait(indata.copy())
            except queue.Full:
                try:
                    block_queue.get_nowait()
                except queue.Empty:
                    pass
                block_queue.put_nowait(indata.copy())

        model = self._load_model(model_class)
        device, compute_type, compute_reason = getattr(
            self, "_last_compute_target", ("cuda", "float16", "")
        )
        self.on_event(
            {
                "type": "model",
                "device": device,
                "compute_type": compute_type,
                "reason": compute_reason,
            }
        )
        chunk_size = max(1, int(self.settings.sample_rate * self.settings.chunk_seconds))
        overlap_size = max(
            0,
            min(chunk_size - 1, int(self.settings.sample_rate * self.settings.overlap_seconds)),
        )
        hop_size = max(1, chunk_size - overlap_size)
        enabled_channels = [item["channel"] for item in mappings]
        buffers = {channel: np.empty(0, dtype=np.float32) for channel in enabled_channels}
        processed_samples = {channel: 0 for channel in enabled_channels}
        transcript_results: queue.Queue[dict[str, Any]] = queue.Queue()
        pending_transcripts: dict[int, dict[str, Any]] = {}
        job_counter = 0

        def submit_transcript_job(
            *,
            channel: int,
            chunk_level: float,
            gain: float,
            audio_16k: Any,
            start_ms: int,
            end_ms: int,
        ) -> None:
            nonlocal job_counter
            job_counter += 1
            job_id = job_counter
            pending_transcripts[channel] = {
                "job_id": job_id,
                "channel": channel,
                "chunk_level": chunk_level,
                "gain": gain,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "submitted_at": self.clock(),
            }
            self.on_event({"type": "transcribing", "channel": channel, "level": chunk_level})

            def run_transcript() -> None:
                transcribe_started = self.clock()
                try:
                    segments, _ = model.transcribe(
                        audio_16k,
                        language="en",
                        beam_size=max(1, int(self.settings.beam_size)),
                        vad_filter=False,
                        without_timestamps=True,
                        condition_on_previous_text=False,
                        initial_prompt=self.settings.initial_prompt
                        or caption_initial_prompt(self.settings.prompt_terms),
                    )
                    transcript_results.put(
                        {
                            "type": "transcript_result",
                            "job_id": job_id,
                            "channel": channel,
                            "seconds": self.clock() - transcribe_started,
                            "segments": list(segments),
                        }
                    )
                except Exception as exc:
                    transcript_results.put(
                        {
                            "type": "transcript_error",
                            "job_id": job_id,
                            "channel": channel,
                            "seconds": self.clock() - transcribe_started,
                            "message": f"{exc.__class__.__name__}: {exc}",
                        }
                    )

            threading.Thread(target=run_transcript, daemon=True).start()

        def drain_transcript_results() -> None:
            now = self.clock()
            for channel, pending in list(pending_transcripts.items()):
                if pending.get("timed_out"):
                    continue
                age = now - float(pending.get("submitted_at") or now)
                if age > self.settings.transcription_timeout_seconds:
                    pending["timed_out"] = True
                    self.on_event(
                        {
                            "type": "transcript_error",
                            "channel": channel,
                            "seconds": age,
                            "message": (
                                "faster-whisper CUDA transcription timed out. "
                                "The audio stream is still live, but this Whisper job did not return."
                            ),
                        }
                    )
            while True:
                try:
                    result = transcript_results.get_nowait()
                except queue.Empty:
                    return
                channel = int(result.get("channel") or 0)
                pending = pending_transcripts.get(channel)
                if not pending or int(pending.get("job_id") or 0) != int(result.get("job_id") or 0):
                    continue
                pending_transcripts.pop(channel, None)
                transcribe_seconds = float(result.get("seconds") or 0)
                gain = float(pending.get("gain") or 1.0)
                if result.get("type") == "transcript_error":
                    self.on_event(
                        {
                            "type": "transcript_error",
                            "channel": channel,
                            "seconds": transcribe_seconds,
                            "message": str(result.get("message") or ""),
                        }
                    )
                    continue
                recognized = list(result.get("segments") or [])
                text = " ".join(
                    str(segment.text).strip()
                    for segment in recognized
                    if str(segment.text).strip()
                ).strip()
                text = clean_football_caption_text(text, self.settings.prompt_terms)
                if not text:
                    self.on_event({"type": "empty_transcript", "channel": channel, "confidence": 0, "gain": gain, "seconds": transcribe_seconds})
                    continue
                confidence = self._confidence(recognized)
                chunk_level = float(pending.get("chunk_level") or 0)
                if likely_silence_hallucination(text, confidence, chunk_level):
                    self.on_event({"type": "rejected_caption", "channel": channel, "confidence": confidence, "text": text, "gain": gain, "reason": "NOISE_HALLUCINATION", "seconds": transcribe_seconds})
                    continue
                if self._is_recent_duplicate(text):
                    self.on_event({"type": "duplicate_caption", "channel": channel, "confidence": 0, "text": text, "gain": gain, "seconds": transcribe_seconds})
                    continue
                result = self.caption_service.ingest_segment(
                    {
                        "broadcast_id": self.load_broadcast_id() or "unscheduled",
                        "channel": channel,
                        "text": text,
                        "confidence": confidence,
                        "start_ms": int(pending.get("start_ms") or 0),
                        "end_ms": int(pending.get("end_ms") or 0),
                    }
                )
                if getattr(result, "ok", False):
                    self.on_event({"type": "caption", "channel": channel, "confidence": confidence, "text": text, "gain": gain, "seconds": transcribe_seconds})
                else:
                    self.on_event({"type": "rejected_caption", "channel": channel, "confidence": confidence, "text": text, "gain": gain, "reason": getattr(result, "code", "rejected"), "seconds": transcribe_seconds})
        stream_event = {
            "channels": enabled_channels,
            "mappings": mappings,
            "device_name": str(device_info.get("name") or self.settings.device_name),
            "host_api": host_api,
            "capture_channels": capture_channels,
            "capture_dtype": capture_dtype,
        }
        self.on_event({"type": "opening_stream", **stream_event})

        with sd.InputStream(
            device=resolved_device,
            samplerate=self.settings.sample_rate,
            channels=capture_channels,
            dtype=capture_dtype,
            callback=callback,
        ):
            self.on_event({"type": "ready", **stream_event})
            while not self._stop_event.is_set():
                drain_transcript_results()
                try:
                    block = block_queue.get(timeout=0.25)
                except queue.Empty:
                    continue
                if capture_dtype == "int16":
                    block = block.astype(np.float32) / 32768.0
                else:
                    block = block.astype(np.float32, copy=False)
                hardware_rms = np.sqrt(np.mean(np.square(block, dtype=np.float64), axis=0))
                self.on_event(
                    {
                        "type": "hardware_audio",
                        "levels": {
                            index + 1: float(level)
                            for index, level in enumerate(hardware_rms)
                        },
                    }
                )
                for mapping in mappings:
                    channel = mapping["channel"]
                    zero_based = mapping["device_channel"] - 1
                    level = rms_level(block[:, zero_based])
                    self.on_event({"type": "audio", "channel": channel, "level": level})
                    buffers[channel] = np.concatenate((buffers[channel], block[:, zero_based]))
                    while len(buffers[channel]) >= chunk_size:
                        chunk = buffers[channel][:chunk_size]
                        buffers[channel] = buffers[channel][hop_size:]
                        start_sample = processed_samples[channel]
                        processed_samples[channel] += hop_size
                        chunk_level = rms_level(chunk)
                        self.on_event({"type": "chunk", "channel": channel, "level": chunk_level})
                        if chunk_level < self.settings.speech_threshold:
                            continue
                        boosted_chunk, gain = normalize_caption_audio(chunk, chunk_level)
                        audio_16k = resample_48k_to_16k(boosted_chunk)
                        audio_16k = np.ascontiguousarray(audio_16k, dtype=np.float32)
                        np.clip(audio_16k, -1.0, 1.0, out=audio_16k)
                        pad = max(1, int(self.settings.recognition_rate * 0.25))
                        audio_16k = np.pad(audio_16k, (pad, pad), mode="constant")
                        start_ms = int(
                            (start_sample / self.settings.sample_rate) * 1000
                        )
                        end_ms = start_ms + int(self.settings.chunk_seconds * 1000)
                        if channel in pending_transcripts:
                            continue
                        submit_transcript_job(
                            channel=channel,
                            chunk_level=chunk_level,
                            gain=gain,
                            audio_16k=audio_16k,
                            start_ms=start_ms,
                            end_ms=end_ms,
                        )

    def _is_recent_duplicate(self, text: str) -> bool:
        normalized = normalize_caption_for_duplicate(text)
        normalized_words = normalized.split()
        now = self.clock()
        self._recent_captions = [
            (timestamp, caption)
            for timestamp, caption in self._recent_captions
            if now - timestamp <= 4.0
        ]
        for _, caption in self._recent_captions:
            caption_words = caption.split()
            if normalized == caption:
                return True
            if normalized in {"touchdown"} and normalized in caption_words:
                return True
            if len(normalized_words) >= 2 and normalized in caption:
                return True
            if len(caption_words) >= 2 and caption in normalized:
                return True
        self._recent_captions.append((now, normalized))
        return False

    @staticmethod
    def _confidence(segments: list[Any]) -> float:
        log_probabilities = [
            float(segment.avg_logprob)
            for segment in segments
            if getattr(segment, "avg_logprob", None) is not None
        ]
        if not log_probabilities:
            return 1.0
        average = sum(log_probabilities) / len(log_probabilities)
        return round(max(0.0, min(1.0, math.exp(average))), 4)

    def _resolve_compute_target(self, model_class: Any) -> tuple[str, str, str]:
        """Pick ``(device, compute_type, reason)`` for the caption model.

        Round 15B: prefer an NVIDIA CUDA GPU (float16), but fall back to CPU
        (int8) when CUDA / cuDNN is unavailable instead of refusing to
        caption. ``reason`` is a human-readable string that gets logged and
        surfaced in the caption status/diagnostics so the operator can tell
        from the logs alone which path ran.
        """

        is_faster_whisper = str(
            getattr(model_class, "__module__", "")
        ).startswith("faster_whisper")
        if not is_faster_whisper:
            # A stub/fake model class (tests) -- no hardware probe, keep the
            # historical default so existing fakes see the same arguments.
            return "cuda", "float16", "test model class (no hardware probe)"
        ok, detail = self._probe_cuda_float16()
        if ok:
            return "cuda", "float16", "NVIDIA CUDA GPU detected (float16)"
        return (
            "cpu",
            "int8",
            f"CPU int8 fallback -- CUDA float16 unavailable: {detail}",
        )

    def _load_model(self, model_class: Any) -> Any:
        device, compute_type, reason = self._resolve_compute_target(model_class)
        key = (model_class, self.settings.model_name, device, compute_type)
        with self._model_lock:
            model = self._model_cache.get(key)
            if model is not None:
                self._last_compute_target = (device, compute_type, reason)
                return model
            try:
                model = model_class(
                    self.settings.model_name,
                    device=device,
                    compute_type=compute_type,
                )
            except Exception as exc:
                raise RuntimeError(
                    f"Unable to load the live-caption model on {device} "
                    f"({compute_type}). Verify the faster-whisper / "
                    "CTranslate2 installation."
                ) from exc
            self._model_cache[key] = model
            self._last_compute_target = (device, compute_type, reason)
            _LOGGER.info(
                "Live captions: loaded model %s on %s (%s) -- %s",
                self.settings.model_name,
                device,
                compute_type,
                reason,
            )
            return model

    @staticmethod
    def _probe_cuda_float16() -> tuple[bool, str]:
        """Non-raising CUDA/cuDNN float16 readiness probe.

        Returns ``(True, "")`` when the NVIDIA GPU path is usable, or
        ``(False, <reason>)`` so the caller can fall back to CPU int8.
        """

        if sys.platform == "win32":
            _prepare_windows_cuda_dll_paths()
            dll_paths = _discover_windows_cuda_dll_paths()
            missing = [
                dll
                for dll in ("cublas64_12.dll", "cudnn_ops64_9.dll")
                if not _windows_dll_is_available(dll, dll_paths)
            ]
            if missing:
                searched = ", ".join(str(path) for path in dll_paths) or "none"
                return False, (
                    "required NVIDIA DLLs missing from PATH: "
                    + ", ".join(missing)
                    + f" (searched: {searched})"
                )

        try:
            import ctranslate2
        except Exception as exc:  # pragma: no cover - import-time only
            return False, f"CTranslate2 import failed: {exc}"

        try:
            cuda_count = int(ctranslate2.get_cuda_device_count())
        except Exception as exc:
            return False, f"CTranslate2 could not query CUDA devices: {exc}"
        if cuda_count < 1:
            return False, "no CUDA device visible to CTranslate2"

        try:
            supported = set(ctranslate2.get_supported_compute_types("cuda"))
        except Exception as exc:
            return False, f"CTranslate2 could not query CUDA compute types: {exc}"
        if "float16" not in supported:
            return False, "GPU does not report CTranslate2 float16 support"
        return True, ""

    @staticmethod
    def _optional_dependencies():
        try:
            import numpy as np
            import sounddevice as sd
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise CaptionWorkerDependencyError(
                "Live captions require optional packages: numpy, sounddevice, and faster-whisper."
            ) from exc
        return np, sd, WhisperModel


def available_audio_input_devices() -> dict[str, Any]:
    try:
        import sounddevice as sd
    except ImportError:
        fallback = _available_windows_audio_input_devices()
        if fallback["devices"]:
            return fallback
        return {
            "available": False,
            "error": "Install the optional sounddevice package or connect a Windows audio input device.",
            "devices": [],
        }

    devices = []
    try:
        host_apis = list(sd.query_hostapis())
        for index, device in enumerate(sd.query_devices()):
            max_inputs = int(device.get("max_input_channels", 0) or 0)
            if max_inputs <= 0:
                continue
            name = str(device.get("name", f"Input {index}"))
            if _is_default_audio_alias(name):
                continue
            raw_host_api_index = device.get("hostapi", -1)
            host_api_index = int(raw_host_api_index if raw_host_api_index is not None else -1)
            host_api_name = ""
            if 0 <= host_api_index < len(host_apis):
                host_api_name = str(host_apis[host_api_index].get("name", ""))
            if _is_wdm_ks_host(host_api_name):
                continue
            devices.append(
                {
                    "id": str(index),
                    "index": index,
                    "name": name,
                    "channels": max_inputs,
                    "default_sample_rate": int(float(device.get("default_samplerate", 0) or 0)),
                    "host_api": host_api_name,
                }
            )
    except Exception as exc:  # pragma: no cover - depends on local audio host APIs.
        return {"available": False, "error": str(exc), "devices": []}

    def device_rank(item: dict[str, Any]) -> tuple[int, int, str]:
        host_name = str(item.get("host_api") or "").lower()
        host_rank = 2 if "wasapi" in host_name else (1 if "wdm" in host_name else 0)
        return (-int(item.get("channels", 0)), -host_rank, str(item.get("name", "")).lower())

    devices.sort(key=device_rank)
    return {"available": True, "devices": devices}


def _is_default_audio_alias(name: str) -> bool:
    normalized = name.strip().lower()
    return normalized in {
        "microsoft sound mapper - input",
        "primary sound capture driver",
    }


def _available_windows_audio_input_devices() -> dict[str, Any]:
    script = r"""
$devices = Get-PnpDevice -Class AudioEndpoint -Status OK -ErrorAction SilentlyContinue |
  Where-Object {
    $_.FriendlyName -match '(?i)(microphone|mic|line|input|zoom|usb|audio)' -and
    $_.FriendlyName -notmatch '(?i)(speaker|headphone|output)'
  } |
  Select-Object -Property FriendlyName,InstanceId
$devices | ConvertTo-Json -Depth 3
"""
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception as exc:  # pragma: no cover - depends on local Windows APIs.
        return {"available": False, "error": str(exc), "devices": []}

    if result.returncode != 0:
        return {"available": False, "error": (result.stderr or result.stdout).strip(), "devices": []}

    raw = result.stdout.strip()
    if not raw:
        return {"available": True, "devices": [], "source": "windows"}

    try:
        import json

        parsed = json.loads(raw)
    except Exception as exc:  # pragma: no cover - malformed host output.
        return {"available": False, "error": str(exc), "devices": []}

    rows = parsed if isinstance(parsed, list) else [parsed]
    devices = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        name = str(row.get("FriendlyName") or "").strip()
        if not name:
            continue
        devices.append(
            {
                "id": row.get("InstanceId") or name,
                "index": index,
                "name": name,
                "channels": 2,
                "default_sample_rate": 48000,
                "source": "windows",
            }
        )
    return {"available": True, "devices": devices, "source": "windows"}

