from __future__ import annotations

import argparse
import importlib.metadata as metadata
import json
import math
import shutil
import subprocess
import sys
import time
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "Data" / "Captions" / "Diagnostics"


@dataclass(frozen=True)
class ProbeCase:
    device_index: int
    device_name: str
    host_api: str
    samplerate: int
    channels: int
    dtype: str


def package_version(name: str) -> str:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return "not installed"


def rms(values: Any) -> float:
    if len(values) == 0:
        return 0.0
    return float(math.sqrt(float((values * values).mean())))


def save_wav(path: Path, samples: Any, samplerate: int) -> None:
    import numpy as np

    path.parent.mkdir(parents=True, exist_ok=True)
    clipped = np.clip(samples, -1.0, 1.0)
    pcm = (clipped * 32767.0).astype("<i2")
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(int(samples.shape[1]) if samples.ndim > 1 else 1)
        handle.setsampwidth(2)
        handle.setframerate(int(samplerate))
        handle.writeframes(pcm.tobytes())


def cuda_inventory() -> dict[str, Any]:
    inventory: dict[str, Any] = {
        "nvidia_smi": shutil.which("nvidia-smi") or "",
        "cuda_device_count": None,
        "devices": [],
    }
    if inventory["nvidia_smi"]:
        try:
            output = subprocess.check_output(
                [
                    inventory["nvidia_smi"],
                    "--query-gpu=name,compute_cap,memory.total,driver_version",
                    "--format=csv,noheader",
                ],
                text=True,
                stderr=subprocess.STDOUT,
                timeout=10,
            )
            for line in output.splitlines():
                if line.strip():
                    inventory["devices"].append(line.strip())
        except Exception as exc:
            inventory["nvidia_smi_error"] = str(exc)
    try:
        import ctranslate2

        if hasattr(ctranslate2, "get_cuda_device_count"):
            inventory["cuda_device_count"] = ctranslate2.get_cuda_device_count()
    except Exception as exc:
        inventory["ctranslate2_cuda_error"] = str(exc)
    return inventory


def runtime_inventory(sd: Any) -> dict[str, Any]:
    host_apis = list(sd.query_hostapis())
    devices = []
    for index, device in enumerate(sd.query_devices()):
        max_inputs = int(device.get("max_input_channels", 0) or 0)
        if max_inputs <= 0:
            continue
        host_index = int(device.get("hostapi", -1) or -1)
        host_api = host_apis[host_index]["name"] if 0 <= host_index < len(host_apis) else ""
        devices.append(
            {
                "index": index,
                "name": str(device.get("name", "")),
                "host_api": str(host_api),
                "max_input_channels": max_inputs,
                "default_samplerate": float(device.get("default_samplerate", 0) or 0),
                "default_low_input_latency": float(device.get("default_low_input_latency", 0) or 0),
                "default_high_input_latency": float(device.get("default_high_input_latency", 0) or 0),
            }
        )
    return {
        "python_version": sys.version,
        "python_executable": sys.executable,
        "sounddevice": package_version("sounddevice"),
        "portaudio": sd.get_portaudio_version(),
        "numpy": package_version("numpy"),
        "faster_whisper": package_version("faster-whisper"),
        "ctranslate2": package_version("ctranslate2"),
        "cuda": cuda_inventory(),
        "host_apis": host_apis,
        "input_devices": devices,
    }


def build_probe_cases(sd: Any, patterns: list[str], samplerate: int, *, include_wdm_ks: bool = False) -> list[ProbeCase]:
    host_apis = list(sd.query_hostapis())
    cases: list[ProbeCase] = []
    lowered_patterns = [pattern.lower() for pattern in patterns]
    for index, device in enumerate(sd.query_devices()):
        name = str(device.get("name", ""))
        if lowered_patterns and not any(pattern in name.lower() for pattern in lowered_patterns):
            continue
        max_inputs = int(device.get("max_input_channels", 0) or 0)
        if max_inputs <= 0:
            continue
        host_index = int(device.get("hostapi", -1) or -1)
        host_api = host_apis[host_index]["name"] if 0 <= host_index < len(host_apis) else ""
        if not include_wdm_ks and "wdm-ks" in str(host_api).lower():
            continue
        channel_counts = [max_inputs]
        for value in (2, 1):
            if value <= max_inputs and value not in channel_counts:
                channel_counts.append(value)
        for channels in channel_counts:
            for dtype in ("float32", "int16"):
                cases.append(ProbeCase(index, name, str(host_api), samplerate, channels, dtype))
    return cases


def build_specific_probe_cases(
    sd: Any,
    device_index: int,
    samplerate: int,
    channels: int,
    dtypes: list[str],
) -> list[ProbeCase]:
    host_apis = list(sd.query_hostapis())
    devices = list(sd.query_devices())
    if device_index < 0 or device_index >= len(devices):
        raise ValueError(f"Audio device index {device_index} is not available.")
    device = dict(devices[device_index])
    host_index = int(device.get("hostapi", -1) or -1)
    host_api = host_apis[host_index]["name"] if 0 <= host_index < len(host_apis) else ""
    return [
        ProbeCase(
            device_index=device_index,
            device_name=str(device.get("name", "")),
            host_api=str(host_api),
            samplerate=samplerate,
            channels=channels,
            dtype=dtype,
        )
        for dtype in dtypes
    ]


def run_probe_case(sd: Any, np: Any, case: ProbeCase, seconds: float, output_dir: Path) -> dict[str, Any]:
    result: dict[str, Any] = {
        "device_index": case.device_index,
        "device_name": case.device_name,
        "host_api": case.host_api,
        "samplerate": case.samplerate,
        "channels": case.channels,
        "dtype": case.dtype,
        "check_input_settings": "not run",
        "opened": False,
        "callback_count": 0,
        "status_flags": [],
        "callback_times": [],
    }
    try:
        sd.check_input_settings(
            device=case.device_index,
            samplerate=case.samplerate,
            channels=case.channels,
            dtype=case.dtype,
        )
        result["check_input_settings"] = "ok"
    except Exception as exc:
        result["check_input_settings"] = f"{exc.__class__.__name__}: {exc}"
        return result

    blocks: list[Any] = []

    def callback(indata, frames, timing, status) -> None:
        del frames
        result["callback_count"] += 1
        result["callback_times"].append(
            {
                "input_buffer_adc_time": getattr(timing, "inputBufferAdcTime", None),
                "current_time": getattr(timing, "currentTime", None),
                "wall_time": time.time(),
            }
        )
        if status:
            result["status_flags"].append(str(status))
        blocks.append(indata.copy())

    try:
        with sd.InputStream(
            device=case.device_index,
            samplerate=case.samplerate,
            channels=case.channels,
            dtype=case.dtype,
            callback=callback,
        ):
            result["opened"] = True
            time.sleep(seconds)
    except Exception as exc:
        result["open_error"] = f"{exc.__class__.__name__}: {exc}"
        return result

    if not blocks:
        result["signal"] = "no callbacks"
        return result

    samples = np.concatenate(blocks, axis=0)
    if case.dtype == "int16":
        analysis_samples = samples.astype(np.float32) / 32768.0
    else:
        analysis_samples = samples.astype(np.float32)
    channel_stats = []
    changing = False
    for channel in range(analysis_samples.shape[1]):
        values = analysis_samples[:, channel]
        variance = float(np.var(values))
        peak = float(np.max(np.abs(values))) if len(values) else 0.0
        level = rms(values)
        if variance > 1e-7 or peak > 0.0005:
            changing = True
        channel_stats.append(
            {
                "channel": channel + 1,
                "rms": level,
                "peak": peak,
                "variance": variance,
            }
        )
    result["frames"] = int(analysis_samples.shape[0])
    result["channel_stats"] = channel_stats
    result["signal"] = "changing" if changing else "flat_or_silent"
    if changing:
        stem = f"probe_device{case.device_index}_{case.channels}ch_{case.dtype}_{int(time.time())}.wav"
        wav_path = output_dir / stem
        save_wav(wav_path, analysis_samples, case.samplerate)
        result["wav_path"] = str(wav_path)
    return result


def compact_result(result: dict[str, Any]) -> str:
    max_rms = 0.0
    max_peak = 0.0
    max_variance = 0.0
    for stats in result.get("channel_stats") or []:
        max_rms = max(max_rms, float(stats.get("rms") or 0))
        max_peak = max(max_peak, float(stats.get("peak") or 0))
        max_variance = max(max_variance, float(stats.get("variance") or 0))
    pieces = [
        f"idx={result.get('device_index')}",
        f"host={result.get('host_api') or 'unknown'}",
        f"ch={result.get('channels')}",
        f"dtype={result.get('dtype')}",
        f"callbacks={result.get('callback_count')}",
        f"signal={result.get('signal') or result.get('check_input_settings')}",
        f"max_rms={max_rms:.6f}",
        f"max_peak={max_peak:.6f}",
        f"max_var={max_variance:.9f}",
    ]
    if result.get("open_error"):
        pieces.append(f"error={result['open_error']}")
    if result.get("wav_path"):
        pieces.append(f"wav={result['wav_path']}")
    return " | ".join(pieces)


def transcribe_wav(path: Path, *, device: str = "cuda", compute_type: str = "float16") -> dict[str, Any]:
    from faster_whisper import WhisperModel

    started = time.time()
    print(
        f"transcription loading model=small.en device={device} compute={compute_type}",
        flush=True,
    )
    model = WhisperModel("small.en", device=device, compute_type=compute_type)
    loaded_at = time.time()
    print(f"transcription model loaded in {loaded_at - started:.3f}s; starting decode", flush=True)
    segments, info = model.transcribe(
        str(path),
        language="en",
        beam_size=1,
        vad_filter=False,
        without_timestamps=True,
        condition_on_previous_text=False,
    )
    recognized = list(segments)
    finished_at = time.time()
    return {
        "device": device,
        "compute_type": compute_type,
        "model_load_seconds": round(loaded_at - started, 3),
        "transcribe_seconds": round(finished_at - loaded_at, 3),
        "language": getattr(info, "language", ""),
        "language_probability": getattr(info, "language_probability", None),
        "segments": [
            {
                "start": getattr(segment, "start", None),
                "end": getattr(segment, "end", None),
                "text": str(getattr(segment, "text", "")).strip(),
                "avg_logprob": getattr(segment, "avg_logprob", None),
            }
            for segment in recognized
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe CSRN caption capture outside Flask.")
    parser.add_argument("--seconds", type=float, default=5.0)
    parser.add_argument("--samplerate", type=int, default=48000)
    parser.add_argument("--pattern", action="append", default=["cable output"])
    parser.add_argument("--device-index", type=int, default=None, help="Probe only one PortAudio device index.")
    parser.add_argument("--channels", type=int, default=2, help="Channel count for --device-index probes.")
    parser.add_argument("--dtype", action="append", choices=["float32", "int16"], default=None)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--transcribe-wav", type=Path, default=None)
    parser.add_argument("--transcribe-device", default="cuda", choices=["cuda", "cpu"])
    parser.add_argument("--transcribe-compute-type", default="float16")
    parser.add_argument("--include-wdm-ks", action="store_true", help="Also probe WDM-KS endpoints.")
    parser.add_argument("--verbose", action="store_true", help="Print full per-case JSON to the console.")
    args = parser.parse_args()

    report: dict[str, Any] = {"started_at": int(time.time()), "probe_results": []}
    try:
        import numpy as np
        import sounddevice as sd
    except ImportError as exc:
        report["error"] = f"Missing probe dependency: {exc}"
        print(json.dumps(report, indent=2), flush=True)
        return 2

    report["runtime"] = runtime_inventory(sd)
    if args.device_index is not None:
        cases = build_specific_probe_cases(
            sd,
            args.device_index,
            args.samplerate,
            args.channels,
            args.dtype or ["float32", "int16"],
        )
    else:
        cases = build_probe_cases(sd, args.pattern or [], args.samplerate, include_wdm_ks=args.include_wdm_ks)
    report["probe_cases"] = [case.__dict__ for case in cases]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for case in cases:
        result = run_probe_case(sd, np, case, args.seconds, args.output_dir)
        report["probe_results"].append(result)
        if args.verbose:
            print(json.dumps(result, indent=2), flush=True)
        else:
            print(compact_result(result), flush=True)

    if args.transcribe_wav:
        try:
            transcription = transcribe_wav(
                args.transcribe_wav,
                device=args.transcribe_device,
                compute_type=args.transcribe_compute_type,
            )
            report["transcription"] = transcription
            print(
                "transcription"
                f" device={transcription['device']}"
                f" compute={transcription['compute_type']}"
                f" load={transcription['model_load_seconds']:.3f}s"
                f" transcribe={transcription['transcribe_seconds']:.3f}s"
                f" segments={len(transcription['segments'])}",
                flush=True,
            )
            for segment in transcription["segments"]:
                text = str(segment.get("text") or "").strip()
                if text:
                    print(f"  text={text}", flush=True)
        except Exception as exc:
            report["transcription_error"] = f"{exc.__class__.__name__}: {exc}"
            print(f"transcription error: {report['transcription_error']}", flush=True)

    report_path = args.output_dir / f"caption_audio_probe_{int(time.time())}.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Saved report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
