from __future__ import annotations

import math
import queue
import time
from dataclasses import dataclass
from typing import Any, Callable


class CaptionWorkerDependencyError(RuntimeError):
    pass


@dataclass(frozen=True)
class CaptionWorkerSettings:
    device: str | int | None = None
    model_name: str = "small.en"
    sample_rate: int = 48000
    recognition_rate: int = 16000
    chunk_seconds: float = 3.0
    speech_threshold: float = 0.008


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


class ChannelCaptionWorker:
    """Optional local faster-whisper worker for isolated P4next input channels."""

    def __init__(
        self,
        *,
        caption_service: Any,
        load_broadcast_id: Callable[[], str],
        settings: CaptionWorkerSettings | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.caption_service = caption_service
        self.load_broadcast_id = load_broadcast_id
        self.settings = settings or CaptionWorkerSettings()
        self.clock = clock
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    def run_forever(self) -> None:
        np, sd, model_class = self._optional_dependencies()
        profile = self.caption_service.status().data["profile"]
        enabled_channels = [
            int(item["channel"])
            for item in profile.get("channels", [])
            if item.get("enabled", False)
        ]
        if not enabled_channels:
            raise RuntimeError("No caption channels are enabled.")
        maximum_channel = max(enabled_channels)
        block_queue: queue.Queue[Any] = queue.Queue(maxsize=16)

        def callback(indata, frames, timing, status) -> None:
            del frames, timing, status
            try:
                block_queue.put_nowait(indata.copy())
            except queue.Full:
                try:
                    block_queue.get_nowait()
                except queue.Empty:
                    pass
                block_queue.put_nowait(indata.copy())

        model = model_class(self.settings.model_name, device="auto", compute_type="int8")
        chunk_size = max(1, int(self.settings.sample_rate * self.settings.chunk_seconds))
        buffers = {channel: np.empty(0, dtype=np.float32) for channel in enabled_channels}
        processed_samples = {channel: 0 for channel in enabled_channels}

        with sd.InputStream(
            device=self.settings.device,
            samplerate=self.settings.sample_rate,
            channels=maximum_channel,
            dtype="float32",
            callback=callback,
        ):
            while not self._stop:
                block = block_queue.get(timeout=1.0)
                for channel in enabled_channels:
                    zero_based = channel - 1
                    buffers[channel] = np.concatenate((buffers[channel], block[:, zero_based]))
                    while len(buffers[channel]) >= chunk_size:
                        chunk = buffers[channel][:chunk_size]
                        buffers[channel] = buffers[channel][chunk_size:]
                        start_sample = processed_samples[channel]
                        processed_samples[channel] += chunk_size
                        if rms_level(chunk) < self.settings.speech_threshold:
                            continue
                        audio_16k = resample_48k_to_16k(chunk)
                        segments, _ = model.transcribe(
                            audio_16k,
                            language="en",
                            beam_size=1,
                            vad_filter=True,
                            condition_on_previous_text=False,
                        )
                        recognized = list(segments)
                        text = " ".join(
                            str(segment.text).strip()
                            for segment in recognized
                            if str(segment.text).strip()
                        ).strip()
                        if not text:
                            continue
                        confidence = self._confidence(recognized)
                        start_ms = int(
                            (start_sample / self.settings.sample_rate) * 1000
                        )
                        end_ms = start_ms + int(self.settings.chunk_seconds * 1000)
                        self.caption_service.ingest_segment(
                            {
                                "broadcast_id": self.load_broadcast_id() or "unscheduled",
                                "channel": channel,
                                "text": text,
                                "confidence": confidence,
                                "start_ms": start_ms,
                                "end_ms": end_ms,
                            }
                        )

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
