from __future__ import annotations

import atexit
import copy
import json
import os
import queue
import tempfile
import threading
import time
import uuid
import zipfile
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


DEFAULT_RING_LIMIT = 1200
DEFAULT_LOG_LIMIT_BYTES = 5 * 1024 * 1024
DEFAULT_MAX_LOG_FILES = 5


def utc_timestamp_ms() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def default_log_dir() -> Path:
    root = os.environ.get("LOCALAPPDATA")
    if not root:
        root = str(Path.home() / "AppData" / "Local")
    return Path(root) / "CSRN" / "Logs"


def safe_count(value: Any) -> int:
    return len(value) if isinstance(value, list) else 0


def latest_id(items: Any, key: str) -> str:
    if not isinstance(items, list):
        return ""
    for item in reversed(items):
        if isinstance(item, Mapping) and not item.get("undone"):
            return str(item.get(key) or "")
    return ""


class RuntimeDiagnosticsService:
    def __init__(
        self,
        *,
        log_dir: Path | None = None,
        ring_limit: int = DEFAULT_RING_LIMIT,
        log_limit_bytes: int = DEFAULT_LOG_LIMIT_BYTES,
        max_log_files: int = DEFAULT_MAX_LOG_FILES,
        writer: Any | None = None,
        enabled: bool = True,
    ) -> None:
        self.log_dir = Path(log_dir or default_log_dir())
        self.ring_limit = max(100, int(ring_limit or DEFAULT_RING_LIMIT))
        self.log_limit_bytes = max(64 * 1024, int(log_limit_bytes or DEFAULT_LOG_LIMIT_BYTES))
        self.max_log_files = max(1, int(max_log_files or DEFAULT_MAX_LOG_FILES))
        self.enabled = enabled
        self._ring: deque[dict[str, Any]] = deque(maxlen=self.ring_limit)
        self._lock = threading.Lock()
        self._queue: queue.Queue[dict[str, Any] | None] = queue.Queue(maxsize=self.ring_limit * 2)
        self._writer = writer
        self._thread: threading.Thread | None = None
        self._dropped = 0
        if self.enabled and self._writer is None:
            self._start_writer()

    def _start_writer(self) -> None:
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            fallback = Path(tempfile.gettempdir()) / "CSRN" / "Logs"
            fallback.mkdir(parents=True, exist_ok=True)
            self.log_dir = fallback
        self._thread = threading.Thread(target=self._writer_loop, name="csrn-runtime-diagnostics", daemon=True)
        self._thread.start()

    def close(self) -> None:
        try:
            self._queue.put_nowait(None)
        except Exception:
            pass

    def record(self, event_type: str, **fields: Any) -> dict[str, Any]:
        record = {
            "timestamp": utc_timestamp_ms(),
            "event_type": str(event_type),
            **self._clean(fields),
        }
        with self._lock:
            self._ring.append(copy.deepcopy(record))
        if not self.enabled:
            return record
        try:
            if self._writer is not None:
                self._writer(copy.deepcopy(record))
            else:
                self._queue.put_nowait(copy.deepcopy(record))
        except Exception:
            with self._lock:
                self._dropped += 1
        return record

    def snapshot(self, limit: int = 200) -> dict[str, Any]:
        with self._lock:
            events = list(self._ring)[-max(1, min(int(limit or 200), self.ring_limit)) :]
            dropped = self._dropped
        return {
            "log_dir": str(self.log_dir),
            "ring_limit": self.ring_limit,
            "dropped": dropped,
            "events": copy.deepcopy(events),
        }

    def _writer_loop(self) -> None:
        while True:
            record = self._queue.get()
            if record is None:
                return
            try:
                self._write_record(record)
            except Exception:
                with self._lock:
                    self._dropped += 1

    def _active_log_path(self) -> Path:
        return self.log_dir / "runtime-diagnostics.jsonl"

    def _write_record(self, record: Mapping[str, Any]) -> None:
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._rotate_if_needed()
        with self._active_log_path().open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, separators=(",", ":"), ensure_ascii=True) + "\n")

    def _rotate_if_needed(self) -> None:
        active = self._active_log_path()
        if not active.exists() or active.stat().st_size < self.log_limit_bytes:
            return
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        active.replace(self.log_dir / f"runtime-diagnostics-{stamp}.jsonl")
        rotated = sorted(self.log_dir.glob("runtime-diagnostics-*.jsonl"), key=lambda p: p.stat().st_mtime)
        for path in rotated[: max(0, len(rotated) - self.max_log_files)]:
            try:
                path.unlink()
            except OSError:
                pass

    def export_bundle(
        self,
        *,
        load_state: Any,
        runtime_state: Any,
        overlay_health: Mapping[str, Any] | None = None,
        output_dir: Path | None = None,
    ) -> Path:
        target_dir = Path(output_dir or self.log_dir / "IncidentBundles")
        target_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        bundle_path = target_dir / f"CSRN-Incident-Bundle-{stamp}.zip"
        state = copy.deepcopy(dict(load_state()))
        runtime = copy.deepcopy(dict(runtime_state(state)))
        recent = self.snapshot(limit=self.ring_limit)
        summary = {
            "generated_at": utc_timestamp_ms(),
            "log_dir": str(self.log_dir),
            "broadcast_id": state.get("broadcast_id", ""),
            "state_revision": state.get("state_revision", 0),
            "play_count": safe_count(state.get("plays")),
            "event_count": safe_count(state.get("events")),
            "latest_play_id": latest_id(state.get("plays"), "play_id"),
            "latest_event_id": latest_id(state.get("events"), "id"),
            "overlay_health": copy.deepcopy(dict(overlay_health or {})),
            "diagnostic_events": len(recent["events"]),
        }
        with zipfile.ZipFile(bundle_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("metadata.json", json.dumps(summary, indent=2, ensure_ascii=True))
            zf.writestr("recent-diagnostics.json", json.dumps(recent, indent=2, ensure_ascii=True))
            zf.writestr("state-snapshot.json", json.dumps(self._state_snapshot(state), indent=2, ensure_ascii=True))
            zf.writestr("runtime-state-snapshot.json", json.dumps(runtime, indent=2, ensure_ascii=True))
            log_path = self._active_log_path()
            if log_path.exists():
                zf.write(log_path, "runtime-diagnostics.jsonl")
        self.record("INCIDENT_BUNDLE_EXPORTED", bundle_path=str(bundle_path), broadcast_id=summary["broadcast_id"])
        return bundle_path

    def _state_snapshot(self, state: Mapping[str, Any]) -> dict[str, Any]:
        snapshot = copy.deepcopy(dict(state))
        for key in ("home_roster", "visitor_roster", "schools", "personnel", "assets"):
            snapshot.pop(key, None)
        snapshot["play_register_summary"] = {
            "play_count": safe_count(snapshot.get("plays")),
            "latest_play_id": latest_id(snapshot.get("plays"), "play_id"),
            "event_count": safe_count(snapshot.get("events")),
            "latest_event_id": latest_id(snapshot.get("events"), "id"),
        }
        return snapshot

    def _clean(self, value: Any) -> Any:
        if isinstance(value, Mapping):
            cleaned: dict[str, Any] = {}
            for key, item in value.items():
                key_str = str(key)
                if any(token in key_str.lower() for token in ("name", "note", "contact", "phone", "email", "address")):
                    continue
                cleaned[key_str] = self._clean(item)
            return cleaned
        if isinstance(value, list):
            return [self._clean(item) for item in value[:20]]
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        return str(value)


_RUNTIME_DIAGNOSTICS = RuntimeDiagnosticsService()
atexit.register(_RUNTIME_DIAGNOSTICS.close)


def get_runtime_diagnostics() -> RuntimeDiagnosticsService:
    return _RUNTIME_DIAGNOSTICS


def new_request_id() -> str:
    return uuid.uuid4().hex[:16]


def monotonic_ms() -> float:
    return time.perf_counter() * 1000.0
