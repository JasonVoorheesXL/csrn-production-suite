"""Keeps the announcers' call for reel-worthy plays.

When the statistician records a big play, OBS saves its replay buffer. The mics
track goes in a small audio file tied to that play and the video file is removed.
All of it happens on one background thread: a live play is never held up by OBS,
and nothing that goes wrong here can fail a play.
"""

from __future__ import annotations

import json
import queue
import re
import threading
import time
from pathlib import Path
from typing import Any, Callable, Mapping

import av

from obs_client import OBSConnectionError, OBSReadOnlyClient
from postgame_story import BIG_RETURN_YARDS, LONG_PLAY_YARDS

# The call runs on after the play is entered, so give it a moment before saving.
SAVE_DELAY_SECONDS = 8.0
# OBS track 2 carries the mics only. The replay file holds tracks 1 and 2 in order.
MICS_AUDIO_STREAM = 1
SILENCE_PEAK = 0.001
FILE_WAIT_SECONDS = 20.0
ENSURE_RUNNING_EVERY_SECONDS = 60.0


class OBSReplayClient(OBSReadOnlyClient):
    """OBS client permitting only the replay buffer requests."""

    READ_ONLY_REQUESTS = OBSReadOnlyClient.READ_ONLY_REQUESTS | {
        "GetReplayBufferStatus",
        "StartReplayBuffer",
        "SaveReplayBuffer",
        "GetLastReplayBufferReplay",
    }


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def worth_saving_play(play: Mapping[str, Any]) -> bool:
    """Touchdowns, safeties, takeaways, long snaps and long returns: everything
    the reel picker can offer, decided as soon as the play is recorded."""
    if play.get("touchdown") or play.get("safety"):
        return True
    if play.get("turnover") and str(play.get("turnover_type", "")).lower() in ("interception", "fumble_recovery"):
        return True
    kind = str(play.get("play_type", "")).lower()
    if kind in ("run", "rush", "pass"):
        return _int(play.get("yards")) >= LONG_PLAY_YARDS
    return kind in ("kickoff", "punt") and _int(play.get("return_yards")) >= BIG_RETURN_YARDS


def worth_saving_event(event: Mapping[str, Any]) -> bool:
    return str(event.get("event", "")).upper() == "FG" and str(event.get("kick_outcome", "made") or "made").lower() == "made"


def extract_mics(video_path: Path, audio_path: Path) -> dict[str, Any]:
    """Copy the mics track into its own audio file, without re-encoding, and
    report how long it runs and whether anything was heard on it."""
    temporary = audio_path.with_name(audio_path.name + ".partial")
    with av.open(str(video_path)) as source:
        tracks = list(source.streams.audio)
        if not tracks:
            raise ValueError("The replay has no audio.")
        track = tracks[MICS_AUDIO_STREAM] if len(tracks) > MICS_AUDIO_STREAM else tracks[0]
        with av.open(str(temporary), "w", format="mp4") as target:
            copied = target.add_stream_from_template(track)
            first, last = None, None
            for packet in source.demux(track):
                if packet.dts is None:
                    continue
                first = packet.dts if first is None else first
                last = packet.pts + (packet.duration or 0) - first
                packet.pts -= first
                packet.dts -= first
                packet.stream = copied
                target.mux(packet)
        seconds = float((last or 0) * track.time_base)
        mics_only = len(tracks) > MICS_AUDIO_STREAM
    temporary.replace(audio_path)
    peak = 0.0
    with av.open(str(audio_path)) as written:
        for frame in written.decode(audio=0):
            peak = max(peak, float(abs(frame.to_ndarray()).max()))
    return {"seconds": round(seconds, 2), "peak": round(peak, 4), "silent": peak < SILENCE_PEAK, "mics_only": mics_only}


class ReplayAudioService:
    def __init__(
        self,
        *,
        load_config: Callable[[], Mapping[str, Any]],
        output_dir: Path,
        connect: Callable[[Mapping[str, Any]], Any] | None = None,
        extract: Callable[[Path, Path], dict[str, Any]] = extract_mics,
        now: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
        save_delay: float = SAVE_DELAY_SECONDS,
        file_wait: float = FILE_WAIT_SECONDS,
    ) -> None:
        self._load_config = load_config
        self._output_dir = Path(output_dir)
        self._connect = connect or self._open_client
        self._extract = extract
        self._now = now
        self._sleep = sleep
        self._save_delay = save_delay
        self._file_wait = file_wait
        self._queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=64)
        self._lock = threading.Lock()
        self._worker: threading.Thread | None = None
        self._seen: set[tuple[str, int]] = set()
        self._last_ensure = 0.0
        self._status: dict[str, Any] = {"buffer": "unknown", "saved": 0, "last_clip": None, "problem": "", "checked_at": 0}

    # -- called from the live routes: quick, and never raises -----------------------

    def capture_play(self, play: Mapping[str, Any]) -> None:
        """Called after every saved play. The first one of a game also starts
        the buffer if it was left off, so the big plays after it are covered."""
        try:
            if not self._enabled():
                return
            if worth_saving_play(play):
                self._enqueue(str(play.get("broadcast_id", "")), _int(play.get("created_at")), str(play.get("label") or play.get("result") or "Play"))
            elif self._now() - self._last_ensure >= ENSURE_RUNNING_EVERY_SECONDS:
                self._last_ensure = self._now()
                self._submit({"job": "ensure"})
        except Exception as exc:
            self._note(problem=f"Could not queue the audio: {exc}")

    def capture_event(self, event: Mapping[str, Any]) -> None:
        try:
            if self._enabled() and worth_saving_event(event):
                self._enqueue(str(event.get("broadcast_id", "")), _int(event.get("created_at")), str(event.get("label") or "Field goal"))
        except Exception as exc:
            self._note(problem=f"Could not queue the audio: {exc}")

    # -- the OBS Manager panel --------------------------------------------------------

    def status(self, *, check: bool = False) -> dict[str, Any]:
        settings = self._settings()
        if not self._enabled():
            return {**self._snapshot(), "enabled": False, "buffer": "off",
                    "problem": "OBS commands are turned off in Settings, so no audio is being saved."}
        if check:
            try:
                with self._connect(settings) as client:
                    self._note(buffer="running" if self._active(client) else "off", problem="")
            except Exception as exc:
                self._note(buffer="unknown", problem=f"Could not reach OBS: {exc}")
        return {**self._snapshot(), "enabled": True}

    def start_buffer(self) -> dict[str, Any]:
        settings = self._settings()
        if self._enabled():
            try:
                with self._connect(settings) as client:
                    if not self._active(client):
                        client.request("StartReplayBuffer")
                    self._note(buffer="running", problem="")
            except Exception as exc:
                self._note(buffer="unknown", problem=f"Could not start the replay buffer: {exc}")
        return self.status()

    # -- the reel picker -------------------------------------------------------------

    def clips(self, broadcast_id: str) -> dict[int, dict[str, Any]]:
        """Saved calls for one game, keyed by the play's created_at."""
        found: dict[int, dict[str, Any]] = {}
        folder = self._folder(broadcast_id)
        if folder.is_dir():
            for path in folder.glob("*.json"):
                try:
                    clip = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    continue
                found[_int(clip.get("play_at"))] = clip
        return found

    def clip_file(self, broadcast_id: str, play_at: int) -> Path | None:
        path = self._folder(broadcast_id) / f"{int(play_at)}.m4a"
        return path if path.is_file() else None

    # -- the worker ------------------------------------------------------------------

    def _enabled(self) -> bool:
        settings = self._settings()
        return bool(settings.get("websocket_enabled") and settings.get("controlled_commands"))

    def _settings(self) -> dict[str, Any]:
        config = self._load_config()
        settings = config.get("obs") if isinstance(config, Mapping) else None
        return dict(settings) if isinstance(settings, Mapping) else {}

    @staticmethod
    def _open_client(settings: Mapping[str, Any]) -> OBSReplayClient:
        return OBSReplayClient(
            host=str(settings.get("host", "127.0.0.1")),
            port=int(settings.get("port", 4455)),
            password=str(settings.get("password", "")),
            timeout=3.5,
        )

    def _folder(self, broadcast_id: str) -> Path:
        return self._output_dir / (re.sub(r"[^A-Za-z0-9_.-]+", "-", str(broadcast_id)).strip("-.") or "broadcast")

    def _snapshot(self) -> dict[str, Any]:
        with self._lock:
            return dict(self._status)

    def _note(self, **changes: Any) -> None:
        with self._lock:
            self._status.update(changes, checked_at=int(self._now()))

    def _enqueue(self, broadcast_id: str, play_at: int, label: str) -> None:
        if not broadcast_id or not play_at:
            return
        with self._lock:
            # A resent command returns the same play; it only gets one save.
            if (broadcast_id, play_at) in self._seen:
                return
            self._seen.add((broadcast_id, play_at))
        self._submit({"job": "save", "broadcast_id": broadcast_id, "play_at": play_at, "label": label, "due": self._now() + self._save_delay})

    def _submit(self, job: dict[str, Any]) -> None:
        with self._lock:
            if self._worker is None or not self._worker.is_alive():
                self._worker = threading.Thread(target=self._run, name="replay-audio", daemon=True)
                self._worker.start()
        self._queue.put_nowait(job)

    def _run(self) -> None:
        while True:
            job = self._queue.get()
            try:
                self.process(job)
            except Exception as exc:
                self._note(problem=f"Audio not saved: {exc}")
            finally:
                self._queue.task_done()

    def process(self, job: Mapping[str, Any]) -> None:
        wait = float(job.get("due", 0)) - self._now()
        if wait > 0:
            self._sleep(wait)
        with self._connect(self._settings()) as client:
            if not self._active(client):
                client.request("StartReplayBuffer")
                self._note(buffer="running", problem="The replay buffer was off, so OBS was told to start it."
                           + (f" No audio for: {job['label']}." if job["job"] == "save" else ""))
                return
            self._note(buffer="running")
            if job["job"] == "save":
                self._save(client, job)

    @staticmethod
    def _active(client: Any) -> bool:
        return bool(client.request("GetReplayBufferStatus").get("outputActive"))

    def _save(self, client: Any, job: Mapping[str, Any]) -> None:
        before = self._last_replay(client)
        saved_at = self._now()
        client.request("SaveReplayBuffer")
        video = self._wait_for_file(client, before)
        folder = self._folder(job["broadcast_id"])
        folder.mkdir(parents=True, exist_ok=True)
        audio = folder / f"{job['play_at']}.m4a"
        details = self._extract(video, audio)
        clip = {**details, "play_at": job["play_at"], "label": job["label"], "saved_at": int(saved_at), "broadcast_id": job["broadcast_id"]}
        (folder / f"{job['play_at']}.json").write_text(json.dumps(clip, indent=2), encoding="utf-8")
        # The video goes only once its audio is safely kept; a failure above leaves it.
        video.unlink(missing_ok=True)
        with self._lock:
            self._status["saved"] += 1
            self._status["last_clip"] = clip
            self._status["problem"] = "The last saved call has no sound on the mics track." if details.get("silent") else ""
            self._status["checked_at"] = int(self._now())

    @staticmethod
    def _last_replay(client: Any) -> str:
        try:
            return str(client.request("GetLastReplayBufferReplay").get("savedReplayPath", "") or "")
        except OBSConnectionError:
            return ""

    def _wait_for_file(self, client: Any, before: str) -> Path:
        deadline = self._now() + self._file_wait
        size = -1
        while self._now() < deadline:
            current = self._last_replay(client)
            if current and current != before:
                path = Path(current)
                now_size = path.stat().st_size if path.is_file() else -1
                # OBS is done writing once the file stops growing.
                if now_size > 0 and now_size == size:
                    return path
                size = now_size
            self._sleep(0.5)
        raise TimeoutError("OBS did not finish saving the replay.")
