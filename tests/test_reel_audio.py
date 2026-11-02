from __future__ import annotations

import io
from fractions import Fraction
from pathlib import Path

import av
import numpy as np

import reel_audio

RATE = 48000


def _call(path: Path, levels: list[float]) -> None:
    """A call with one level per second."""
    with av.open(str(path), "w", format="mp4") as out:
        stream = out.add_stream("aac", rate=RATE, layout="stereo")
        rng = np.random.default_rng(1)
        data = np.concatenate([rng.uniform(-level, level, RATE) for level in levels]).astype(np.float32)
        for index in range(0, data.size, 1024):
            block = data[index:index + 1024]
            frame = av.AudioFrame.from_ndarray(np.stack([block, block]), format="fltp", layout="stereo")
            frame.sample_rate, frame.pts, frame.time_base = RATE, index, Fraction(1, RATE)
            for packet in stream.encode(frame):
                out.mux(packet)
        for packet in stream.encode(None):
            out.mux(packet)


def _reel(seconds: int = 6) -> bytes:
    buffer = io.BytesIO()
    with av.open(buffer, "w", format="mp4") as out:
        video = out.add_stream("libx264", rate=24)
        video.width, video.height, video.pix_fmt = 108, 192, "yuv420p"
        for index in range(seconds * 24):
            frame = av.VideoFrame.from_ndarray(np.full((192, 108, 3), index % 255, dtype=np.uint8), format="rgb24")
            frame.pts = index
            for packet in video.encode(frame):
                out.mux(packet)
        for packet in video.encode(None):
            out.mux(packet)
    return buffer.getvalue()


def _sound(video: bytes) -> tuple[np.ndarray, int]:
    pictures = 0
    with av.open(io.BytesIO(video)) as container:
        assert len(container.streams.audio) == 1 and len(container.streams.video) == 1
        for _ in container.decode(video=0):
            pictures += 1
    with av.open(io.BytesIO(video)) as container:
        blocks = [frame.to_ndarray() for frame in container.decode(audio=0)]
    return np.concatenate(blocks, axis=1), pictures


def _level(sound: np.ndarray, begin: float, end: float) -> float:
    return float(np.abs(sound[:, int(begin * RATE):int(end * RATE)]).max())


def test_waveform_starts_on_the_loudest_stretch(tmp_path: Path) -> None:
    path = tmp_path / "call.m4a"
    _call(path, [0.02] * 30 + [0.6] * 10 + [0.02] * 30)
    wave = reel_audio.waveform(path, buckets=140)
    assert 69 < wave["seconds"] < 71 and not wave["silent"] and len(wave["peaks"]) >= 140
    assert max(wave["peaks"]) == 1.0
    assert 27 <= wave["start"] <= 31 and 39 <= wave["end"] <= 44


def test_a_silent_call_says_so_and_still_offers_a_stretch(tmp_path: Path) -> None:
    path = tmp_path / "call.m4a"
    _call(path, [0.0] * 30)
    wave = reel_audio.waveform(path, buckets=60)
    assert wave["silent"] and wave["end"] > wave["start"]


def test_the_call_lands_where_it_was_put_and_the_picture_is_untouched(tmp_path: Path) -> None:
    path = tmp_path / "call.m4a"
    _call(path, [0.5] * 20)
    reel = _reel()
    with_call, used = reel_audio.add_call(reel, path, start=5, end=7, offset=2)
    sound, pictures = _sound(with_call)
    assert pictures == 6 * 24
    assert used == {"start": 5, "end": 7, "offset": 2, "reel_seconds": reel_audio.video_seconds(reel)}
    assert _level(sound, 0.2, 1.8) < 0.01  # quiet before it comes in
    assert _level(sound, 2.5, 3.5) > 0.1
    assert _level(sound, 4.5, 5.8) < 0.01  # and after it ends
    with av.open(io.BytesIO(with_call)) as container, av.open(io.BytesIO(reel)) as original:
        assert [bytes(p) for p in container.demux(container.streams.video[0]) if p.dts is not None] == [
            bytes(p) for p in original.demux(original.streams.video[0]) if p.dts is not None
        ]


def test_a_long_call_is_cut_to_the_reel_and_times_are_kept_in_range(tmp_path: Path) -> None:
    path = tmp_path / "call.m4a"
    _call(path, [0.5] * 20)
    reel = _reel()
    _, used = reel_audio.add_call(reel, path, start=2, end=19, offset=4)
    assert used["end"] - used["start"] <= reel_audio.video_seconds(reel) - 4 + 0.01
    _, wild = reel_audio.add_call(reel, path, start=-5, end=999, offset=999)
    assert wild["start"] == 0 and wild["end"] == 0 and wild["offset"] == reel_audio.video_seconds(reel)
    _, reversed_times = reel_audio.add_call(reel, path, start=9, end=3, offset=0)
    assert reversed_times["end"] == reversed_times["start"] == 9


def test_quiet_call_is_brought_up_and_a_loud_one_does_not_clip(tmp_path: Path) -> None:
    quiet, loud = tmp_path / "quiet.m4a", tmp_path / "loud.m4a"
    _call(quiet, [0.02] * 8)
    _call(loud, [1.0] * 8)
    reel = _reel()
    for path in (quiet, loud):
        with_call, _ = reel_audio.add_call(reel, path, start=0, end=5, offset=0)
        sound, _ = _sound(with_call)
        assert 0.1 < _level(sound, 1, 4) <= 1.0


def test_reel_with_call_routes(monkeypatch, tmp_path: Path) -> None:
    import app as app_module

    path = tmp_path / "1000.m4a"
    _call(path, [0.5] * 10)

    class Audio:
        def clip_file(self, broadcast_id, play_at):
            return path if play_at == 1000 else None

    service = app_module.get_social_media_preview_service()
    monkeypatch.setattr(service, "_get_replay_audio", lambda: Audio())
    monkeypatch.setattr(service, "output_dir", tmp_path)
    monkeypatch.setattr(app_module, "pin_is_configured", lambda: True)
    monkeypatch.setitem(app_module.app.config, "TESTING", True)
    monkeypatch.setitem(app_module.app.config, "SECRET_KEY", "reel-audio-test")
    client = app_module.app.test_client()
    url = "/api/broadcasts/G1/reel-call.mp4?play=p1&at=1000&start=1&end=3&offset=0"
    assert client.get(url).status_code in (401, 302)
    with client.session_transaction() as active_session:
        active_session["authenticated"] = True
    assert client.get(url).status_code == 409  # not made yet
    (tmp_path / "G1-p1-reel.mp4").write_bytes(_reel())
    response = client.get(url)
    assert response.status_code == 200 and response.mimetype == "video/mp4"
    assert response.headers["X-Reel-Call-Seconds"] == "2.0"
    sound, _ = _sound(response.data)
    assert _level(sound, 1, 1.5) > 0.1
    assert client.get(url.replace("at=1000", "at=2")).status_code == 404
    assert client.get(url.replace("start=1", "start=nope")).status_code == 400
    assert client.get(url.replace("start=1", "start=nan")).status_code == 400
