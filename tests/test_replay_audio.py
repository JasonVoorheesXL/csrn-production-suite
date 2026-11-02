from __future__ import annotations

import json
from fractions import Fraction
from pathlib import Path

import av
import numpy as np

from replay_audio_service import ReplayAudioService, extract_mics, worth_saving_event, worth_saving_play


def _write_replay(path: Path, *, tracks: int = 2, mics_loud: bool = True) -> None:
    """A small video file shaped like an OBS replay: full mix, then mics."""
    with av.open(str(path), "w", format="matroska") as out:
        video = out.add_stream("libx264", rate=30)
        video.width, video.height, video.pix_fmt = 64, 64, "yuv420p"
        audio = [out.add_stream("aac", rate=48000, layout="stereo") for _ in range(tracks)]
        for i in range(30):
            frame = av.VideoFrame.from_ndarray(np.zeros((64, 64, 3), dtype=np.uint8), format="rgb24")
            frame.pts = i
            for packet in video.encode(frame):
                out.mux(packet)
        for index, stream in enumerate(audio):
            for block in range(47):
                level = 0.0 if index == 1 and not mics_loud else 0.25
                data = np.full((2, 1024), level, dtype=np.float32)
                frame = av.AudioFrame.from_ndarray(data, format="fltp", layout="stereo")
                frame.sample_rate, frame.pts, frame.time_base = 48000, block * 1024, Fraction(1, 48000)
                for packet in stream.encode(frame):
                    out.mux(packet)
            for packet in stream.encode(None):
                out.mux(packet)
        for packet in video.encode(None):
            out.mux(packet)


class FakeOBS:
    """Stands in for the OBS connection; a save drops a file like OBS does."""

    def __init__(self, folder: Path, *, active: bool = True):
        self.folder, self.active = folder, active
        self.requests: list[str] = []
        self.last = ""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return None

    def request(self, name, data=None):
        self.requests.append(name)
        if name == "GetReplayBufferStatus":
            return {"outputActive": self.active}
        if name == "StartReplayBuffer":
            self.active = True
        if name == "SaveReplayBuffer":
            path = self.folder / f"Replay {len(self.requests)}.mkv"
            _write_replay(path)
            self.last = str(path)
        if name == "GetLastReplayBufferReplay":
            return {"savedReplayPath": self.last}
        return {}


def _service(tmp_path: Path, obs: FakeOBS, *, enabled: bool = True, **kwargs) -> ReplayAudioService:
    config = {"obs": {"websocket_enabled": enabled, "controlled_commands": enabled}}
    return ReplayAudioService(load_config=lambda: config, output_dir=tmp_path / "audio", connect=lambda settings: obs,
                              sleep=lambda seconds: None, save_delay=0, **kwargs)


JOB = {"job": "save", "broadcast_id": "G1", "play_at": 1000, "label": "Long run", "due": 0}


def test_only_reel_worthy_plays_are_saved() -> None:
    assert worth_saving_play({"touchdown": True, "play_type": "run", "yards": 2})
    assert worth_saving_play({"play_type": "pass", "yards": 25})
    assert not worth_saving_play({"play_type": "pass", "yards": 24})
    assert worth_saving_play({"turnover": True, "turnover_type": "interception", "play_type": "pass"})
    assert not worth_saving_play({"turnover": True, "turnover_type": "downs", "play_type": "run", "yards": 1})
    assert worth_saving_play({"play_type": "punt", "return_yards": 30, "yards": 40})
    assert not worth_saving_play({"play_type": "punt", "return_yards": 5, "yards": 40})
    assert worth_saving_event({"event": "FG", "kick_outcome": "made"})
    assert not worth_saving_event({"event": "FG", "kick_outcome": "missed"})
    assert not worth_saving_event({"event": "XP"})


def test_save_keeps_the_mics_audio_tied_to_the_play_and_removes_the_video(tmp_path: Path) -> None:
    obs = FakeOBS(tmp_path)
    service = _service(tmp_path, obs)
    service.process(JOB)
    assert "SaveReplayBuffer" in obs.requests
    assert not list(tmp_path.glob("*.mkv"))
    clip = service.clips("G1")[1000]
    assert clip["label"] == "Long run" and clip["mics_only"] and not clip["silent"] and clip["seconds"] > 0.5
    audio = service.clip_file("G1", 1000)
    with av.open(str(audio)) as written:
        assert len(written.streams.audio) == 1 and not written.streams.video
    status = service.status()
    assert status["saved"] == 1 and status["buffer"] == "running" and status["problem"] == ""


def test_extract_takes_the_second_track_and_notices_silence(tmp_path: Path) -> None:
    video = tmp_path / "replay.mkv"
    _write_replay(video, mics_loud=False)
    details = extract_mics(video, tmp_path / "call.m4a")
    assert details["silent"] and details["mics_only"]


def test_one_track_replay_still_gives_audio_and_says_it_is_not_mics_only(tmp_path: Path) -> None:
    video = tmp_path / "replay.mkv"
    _write_replay(video, tracks=1)
    details = extract_mics(video, tmp_path / "call.m4a")
    assert not details["mics_only"] and not details["silent"]


def test_buffer_off_starts_it_and_reports_the_missed_play(tmp_path: Path) -> None:
    obs = FakeOBS(tmp_path, active=False)
    service = _service(tmp_path, obs)
    service.process(JOB)
    assert obs.requests == ["GetReplayBufferStatus", "StartReplayBuffer"]
    assert "No audio for: Long run" in service.status()["problem"]
    assert service.clips("G1") == {}


def test_failed_extract_leaves_the_video_in_place(tmp_path: Path) -> None:
    def broken(video, audio):
        raise ValueError("bad file")

    obs = FakeOBS(tmp_path)
    service = _service(tmp_path, obs, extract=broken)
    try:
        service.process(JOB)
    except ValueError:
        pass
    assert len(list(tmp_path.glob("*.mkv"))) == 1
    assert service.clips("G1") == {}


def test_turned_off_in_settings_never_talks_to_obs(tmp_path: Path) -> None:
    obs = FakeOBS(tmp_path)
    service = _service(tmp_path, obs, enabled=False)
    service.capture_play({"touchdown": True, "broadcast_id": "G1", "created_at": 5})
    assert obs.requests == [] and service._worker is None
    status = service.status(check=True)
    assert status["enabled"] is False and obs.requests == []


def test_a_resent_play_is_saved_once(tmp_path: Path) -> None:
    obs = FakeOBS(tmp_path)
    service = _service(tmp_path, obs)
    service._submit = lambda job: jobs.append(job)
    jobs: list = []
    play = {"touchdown": True, "broadcast_id": "G1", "created_at": 5, "label": "TD"}
    service.capture_play(play)
    service.capture_play(play)
    assert len(jobs) == 1 and jobs[0]["play_at"] == 5


def test_capture_never_raises_into_a_live_play(tmp_path: Path) -> None:
    def broken():
        raise RuntimeError("config gone")

    service = ReplayAudioService(load_config=broken, output_dir=tmp_path)
    service.capture_play({"touchdown": True})
    service.capture_event({"event": "FG"})


def test_a_broken_clip_file_does_not_break_the_list(tmp_path: Path) -> None:
    service = _service(tmp_path, FakeOBS(tmp_path))
    folder = tmp_path / "audio" / "G1"
    folder.mkdir(parents=True)
    (folder / "1.json").write_text("{nope", encoding="utf-8")
    (folder / "2.json").write_text(json.dumps({"play_at": 2}), encoding="utf-8")
    assert list(service.clips("G1")) == [2]
    assert service.clip_file("../..", 2) is None


def test_a_real_touchdown_and_a_real_field_goal_queue_a_save_for_their_game(tmp_path: Path) -> None:
    from test_edit_play_reentry import Game

    game = Game(ball_spot="RIGHT 5")
    jobs: list = []
    service = _service(tmp_path, FakeOBS(tmp_path))
    service._submit = jobs.append
    played = game.rules.play({"team": "home", "play_type": "run", "end_spot": "RIGHT 0", "player_number": "1", "source": "statistician"})
    assert played.code == "OK", played.data
    play = played.data["play"]
    assert play["touchdown"]
    service.capture_play(play)
    assert jobs[0]["broadcast_id"] == "B1" and jobs[0]["play_at"] == play["created_at"] and jobs[0]["label"]

    kicked = Game().events.trigger({"team": "home", "event": "FG", "kick_outcome": "made", "source": "statistician"})
    assert kicked.code == "OK", kicked.data
    trigger = kicked.data["trigger"]
    service.capture_event({**trigger, "broadcast_id": kicked.data["state"]["broadcast_id"]})
    assert jobs[-1]["play_at"] == trigger["created_at"] and jobs[-1]["broadcast_id"] == "B1"


class _BrokenAudio:
    def capture_play(self, play):
        raise RuntimeError("boom")


def test_routes_answer_the_play_even_if_capture_blows_up(monkeypatch) -> None:
    import app as app_module
    from rules_service import RulesResult

    class Rules:
        def play(self, payload):
            return RulesResult("OK", {"state": {}, "play": {"touchdown": True}})

    monkeypatch.setattr(app_module, "RULES_SERVICE", Rules(), raising=False)
    monkeypatch.setattr(app_module, "REPLAY_AUDIO_SERVICE", _BrokenAudio(), raising=False)
    monkeypatch.setattr(app_module, "pin_is_configured", lambda: True)
    monkeypatch.setitem(app_module.app.config, "TESTING", True)
    monkeypatch.setitem(app_module.app.config, "SECRET_KEY", "replay-audio-test")
    client = app_module.app.test_client()
    with client.session_transaction() as active_session:
        active_session["authenticated"] = True
    response = client.post("/api/rules-play", json={"team": "home", "play_type": "run"})
    assert response.status_code == 200


def test_panel_routes_need_login_and_serve_the_clip(monkeypatch, tmp_path: Path) -> None:
    import app as app_module

    service = _service(tmp_path, FakeOBS(tmp_path))
    service.process(JOB)
    monkeypatch.setattr(app_module, "REPLAY_AUDIO_SERVICE", service, raising=False)
    monkeypatch.setattr(app_module, "pin_is_configured", lambda: True)
    monkeypatch.setitem(app_module.app.config, "TESTING", True)
    monkeypatch.setitem(app_module.app.config, "SECRET_KEY", "replay-audio-test")
    client = app_module.app.test_client()
    assert client.get("/api/obs/replay-audio").status_code in (401, 302)
    with client.session_transaction() as active_session:
        active_session["authenticated"] = True
    status = client.get("/api/obs/replay-audio").get_json()
    assert status["buffer"] == "running" and status["saved"] == 1 and "password" not in str(status)
    clip = client.get("/api/broadcasts/G1/replay-audio/1000.m4a")
    assert clip.status_code == 200 and clip.mimetype == "audio/mp4" and clip.data
    clip.close()
    assert client.get("/api/broadcasts/G1/replay-audio/9.m4a").status_code == 404
