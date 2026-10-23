from __future__ import annotations

import copy
import json
import os
import tempfile
from pathlib import Path
from threading import RLock
from typing import Any, Callable, Mapping


# Fields that hold a broadcast's full game state. They live only in the
# per-broadcast detail file (Data/Broadcasts/<id>.json), never in the
# broadcast index (Data/Broadcasts/broadcasts.json). A live_state is about
# 350 KB and a final_state_archive about 1.4 MB per game; keeping them in the
# index made every per-play save rewrite ~20 MB while holding the app lock.
HEAVY_BROADCAST_FIELDS: tuple[str, ...] = ("live_state", "final_state_archive")


def has_heavy_fields(record: Mapping[str, Any]) -> bool:
    return any(field in record for field in HEAVY_BROADCAST_FIELDS)


def split_heavy_fields(
    record: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return (light index row, heavy fields) without mutating ``record``."""
    light = {
        key: copy.deepcopy(value)
        for key, value in record.items()
        if key not in HEAVY_BROADCAST_FIELDS
    }
    heavy = {
        key: copy.deepcopy(record[key])
        for key in HEAVY_BROADCAST_FIELDS
        if key in record
    }
    return light, heavy


class BroadcastDetailStore:
    """Per-broadcast detail files: the index row's fields plus the heavy
    game-state fields.

    Every write goes through one lock and merges with what is already on
    disk, so a writer that only knows the light index row (the Game Manager,
    status changes) never drops a live_state or final_state_archive that
    another writer put there. Writes are atomic (temp file + os.replace).
    """

    def __init__(self, directory: Path | Callable[[], Path]) -> None:
        # A callable lets the app resolve DATA_DIR at call time.
        self._directory = directory
        self._lock = RLock()

    @property
    def directory(self) -> Path:
        directory = self._directory
        return Path(directory() if callable(directory) else directory)

    @property
    def lock(self) -> RLock:
        """Held across every detail-file read-merge-write."""
        return self._lock

    def path(self, broadcast_id: Any) -> Path:
        return self.directory / f"{str(broadcast_id or '').strip()}.json"

    def read(self, broadcast_id: Any) -> dict[str, Any] | None:
        key = str(broadcast_id or "").strip()
        if not key:
            return None
        try:
            payload = json.loads(self.path(key).read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    def load_field(self, broadcast_id: Any, field: str) -> dict[str, Any] | None:
        detail = self.read(broadcast_id)
        if detail is None:
            return None
        value = detail.get(field)
        return value if isinstance(value, dict) else None

    def write(
        self,
        record: Mapping[str, Any],
        *,
        existing_only: bool = False,
        heavy: Mapping[str, Any] | None = None,
    ) -> bool:
        """Write ``record``'s light fields, keeping heavy fields already on
        disk unless ``record`` or ``heavy`` supplies a new value for them.

        Returns False when nothing was written (no id, or ``existing_only``
        and no file yet).
        """
        broadcast_id = str(record.get("broadcast_id", "")).strip()
        if not broadcast_id:
            return False
        light, supplied = split_heavy_fields(record)
        if heavy:
            supplied.update(copy.deepcopy(dict(heavy)))
        path = self.path(broadcast_id)
        with self._lock:
            if existing_only and not path.exists():
                return False
            existing = self.read(broadcast_id) or {}
            merged = light
            for field in HEAVY_BROADCAST_FIELDS:
                if field in supplied:
                    merged[field] = supplied[field]
                elif field in existing:
                    merged[field] = existing[field]
            self._atomic_write(path, merged)
        return True

    def delete(self, broadcast_id: Any) -> None:
        key = str(broadcast_id or "").strip()
        if not key:
            return
        with self._lock:
            path = self.path(key)
            if path.exists():
                path.unlink()

    @staticmethod
    def _atomic_write(path: Path, payload: Mapping[str, Any]) -> None:
        serialized = json.dumps(payload, indent=2)
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, raw_temp = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
        )
        temp_path = Path(raw_temp)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                handle.write(serialized)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, path)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise
