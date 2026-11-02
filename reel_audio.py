"""Puts a saved announcer call on a finished reel.

The reel's picture is copied untouched, so moving or trimming the call takes a
moment instead of drawing the cartoon again.
"""

from __future__ import annotations

import io
import tempfile
from pathlib import Path
from typing import Any

import av
import numpy as np

SAMPLE_RATE = 48000
SUGGESTED_SECONDS = 12.0
SNAP_SECONDS = 1.5
QUIET_RMS = 0.002
TARGET_RMS = 0.16
MAX_PEAK = 0.89
FADE_IN_SECONDS = 0.15
FADE_OUT_SECONDS = 0.4


def video_seconds(video: bytes) -> float:
    with av.open(io.BytesIO(video)) as container:
        return round(float(container.duration or 0) / av.time_base, 2)


def _samples(path: Path) -> np.ndarray:
    """The whole call as stereo floats, shape (2, count)."""
    resampler = av.AudioResampler(format="fltp", layout="stereo", rate=SAMPLE_RATE)
    blocks = []
    with av.open(str(path)) as container:
        for frame in container.decode(audio=0):
            for converted in resampler.resample(frame):
                blocks.append(converted.to_ndarray())
    return np.concatenate(blocks, axis=1) if blocks else np.zeros((2, 0), dtype=np.float32)


def _snap(levels: np.ndarray, index: int, reach: int, first: int, last: int) -> int:
    """The quietest moment close to a cut, so a word is less likely to be chopped."""
    low, high = max(first, index - reach), min(last, index + reach)
    return low + int(np.argmin(levels[low:high + 1])) if high >= low else index


def waveform(path: Path, buckets: int = 400) -> dict[str, Any]:
    """The shape of the call for the trim controls, and the part to start from:
    the loudest stretch, which is usually the call of the play."""
    samples = _samples(path)
    seconds = samples.shape[1] / SAMPLE_RATE
    if not samples.shape[1]:
        return {"seconds": 0.0, "peaks": [], "start": 0.0, "end": 0.0, "silent": True}
    mono = samples.mean(axis=0)
    size = max(1, mono.size // buckets)
    usable = mono[: size * (mono.size // size)].reshape(-1, size)
    rms = np.sqrt((usable ** 2).mean(axis=1))
    peaks = np.abs(usable).max(axis=1)
    per_second = rms.size / seconds
    span = min(rms.size, max(1, int(SUGGESTED_SECONDS * per_second)))
    silent = float(rms.max()) < QUIET_RMS
    if silent:
        begin = max(0, rms.size - span)
    else:
        energy = np.convolve(rms ** 2, np.ones(span), mode="valid")
        begin = int(np.argmax(energy))
    stop = min(rms.size - 1, begin + span)
    if not silent:
        reach = max(1, int(SNAP_SECONDS * per_second))
        begin = _snap(rms, begin, reach, 0, rms.size - 1)
        stop = _snap(rms, stop, reach, begin + 1, rms.size - 1)
    top = float(peaks.max()) or 1.0
    return {
        "seconds": round(seconds, 2),
        "peaks": [round(float(value) / top, 3) for value in peaks],
        "start": round(begin / per_second, 1),
        "end": round(min(seconds, (stop + 1) / per_second), 1),
        "silent": silent,
    }


def _shape(call: np.ndarray) -> np.ndarray:
    """Even out the level and fade the ends, so the cut does not click."""
    if not call.shape[1]:
        return call
    rms, peak = float(np.sqrt((call ** 2).mean())), float(np.abs(call).max())
    if rms >= QUIET_RMS:
        call = call * min(TARGET_RMS / rms, MAX_PEAK / peak)
    fade_in = min(int(FADE_IN_SECONDS * SAMPLE_RATE), call.shape[1])
    fade_out = min(int(FADE_OUT_SECONDS * SAMPLE_RATE), call.shape[1])
    call = call.copy()
    call[:, :fade_in] *= np.linspace(0.0, 1.0, fade_in, dtype=np.float32)
    call[:, call.shape[1] - fade_out:] *= np.linspace(1.0, 0.0, fade_out, dtype=np.float32)
    return call


def add_call(video: bytes, audio_path: Path, *, start: float, end: float, offset: float) -> tuple[bytes, dict[str, float]]:
    """The reel with the chosen part of the call on it, starting `offset` seconds in.
    A call that runs past the end of the reel fades out with it."""
    length = video_seconds(video)
    offset = min(max(0.0, offset), length)
    samples = _samples(audio_path)
    available = samples.shape[1] / SAMPLE_RATE
    start = min(max(0.0, start), available)
    end = min(max(start, end), available, start + (length - offset))
    track = np.zeros((2, int(length * SAMPLE_RATE)), dtype=np.float32)
    call = _shape(samples[:, int(start * SAMPLE_RATE): int(end * SAMPLE_RATE)])
    at = int(offset * SAMPLE_RATE)
    count = min(call.shape[1], track.shape[1] - at)
    track[:, at: at + count] = call[:, :count]

    # Fast start (the index at the front, as Facebook asks for) needs a real file to rewrite.
    with tempfile.TemporaryDirectory(prefix="csrn-reel-call-") as workspace:
        target = Path(workspace) / "reel.mp4"
        with av.open(io.BytesIO(video)) as source, av.open(str(target), mode="w", format="mp4", options={"movflags": "+faststart"}) as output:
            picture = source.streams.video[0]
            copied = output.add_stream_from_template(picture)
            sound = output.add_stream("aac", rate=SAMPLE_RATE, layout="stereo")
            sound.bit_rate = 160000
            pending = []
            for index in range(0, track.shape[1], 1024):
                frame = av.AudioFrame.from_ndarray(track[:, index: index + 1024], format="fltp", layout="stereo")
                frame.sample_rate, frame.pts = SAMPLE_RATE, index
                pending.extend(sound.encode(frame))
            pending.extend(sound.encode(None))
            # Picture and sound written in time order, not one after the other.
            pending.reverse()
            for packet in source.demux(picture):
                if packet.dts is None:
                    continue
                moment = float(packet.dts * picture.time_base)
                while pending and float(pending[-1].pts * pending[-1].time_base) <= moment:
                    output.mux(pending.pop())
                packet.stream = copied
                output.mux(packet)
            while pending:
                output.mux(pending.pop())
        return target.read_bytes(), {"start": round(start, 2), "end": round(end, 2), "offset": round(offset, 2), "reel_seconds": length}
