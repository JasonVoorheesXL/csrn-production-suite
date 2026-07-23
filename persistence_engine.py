from __future__ import annotations

import copy
import json
import os
import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Any, Callable


class PersistenceError(RuntimeError):
    """Base error for persistence failures."""


class DataCorruptionError(PersistenceError):
    """Raised when a data file cannot be decoded or validated."""


class DestructiveWriteBlocked(PersistenceError):
    """Raised when a suspicious destructive replacement is rejected."""


@dataclass(frozen=True)
class PersistencePolicy:
    backup_count: int = 5
    block_empty_replacement: bool = False
    block_large_count_drop: bool = False
    max_count_drop_ratio: float = 0.75


class JsonPersistenceEngine:
    """Atomic JSON persistence with backups, validation, and recovery support."""

    def __init__(self, backup_root: Path, quarantine_root: Path | None = None) -> None:
        self.backup_root = Path(backup_root)
        self.quarantine_root = Path(quarantine_root or (self.backup_root / "Quarantine"))
        self._lock = RLock()

    def load(
        self,
        path: Path,
        default: Any,
        *,
        validator: Callable[[Any], bool] | None = None,
        create_if_missing: bool = True,
    ) -> Any:
        path = Path(path)
        with self._lock:
            if not path.exists():
                if create_if_missing:
                    self.save(path, copy.deepcopy(default), validator=validator, force=True)
                return copy.deepcopy(default)

            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                quarantined = self._quarantine(path)
                recovered = self._recover_latest(path, validator)
                if recovered is not None:
                    return recovered
                raise DataCorruptionError(
                    f"Could not read {path}. Damaged copy preserved at {quarantined}."
                ) from exc

            if validator and not validator(data):
                quarantined = self._quarantine(path)
                recovered = self._recover_latest(path, validator)
                if recovered is not None:
                    return recovered
                raise DataCorruptionError(
                    f"Validation failed for {path}. Invalid copy preserved at {quarantined}."
                )
            return data

    def save(
        self,
        path: Path,
        data: Any,
        *,
        validator: Callable[[Any], bool] | None = None,
        policy: PersistencePolicy | None = None,
        force: bool = False,
    ) -> None:
        path = Path(path)
        policy = policy or PersistencePolicy()
        with self._lock:
            if validator and not validator(data):
                raise PersistenceError(f"Refusing to save invalid data to {path}.")

            existing = self._read_existing(path)
            if not force:
                self._enforce_destructive_guard(path, existing, data, policy)

            serialized = json.dumps(data, indent=2, ensure_ascii=False)
            path.parent.mkdir(parents=True, exist_ok=True)
            self.backup_root.mkdir(parents=True, exist_ok=True)

            temp_path: Path | None = None
            try:
                fd, raw_temp = tempfile.mkstemp(
                    prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
                )
                temp_path = Path(raw_temp)
                with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                    handle.write(serialized)
                    handle.flush()
                    os.fsync(handle.fileno())

                check = json.loads(temp_path.read_text(encoding="utf-8"))
                if validator and not validator(check):
                    raise PersistenceError(f"Temporary validation failed for {path}.")

                if path.exists():
                    self._snapshot(path)
                os.replace(temp_path, path)
                temp_path = None
                self._prune_backups(path, policy.backup_count)
            except Exception:
                if temp_path is not None:
                    temp_path.unlink(missing_ok=True)
                raise

    def restore_latest(self, path: Path, *, validator: Callable[[Any], bool] | None = None) -> bool:
        path = Path(path)
        with self._lock:
            recovered = self._recover_latest(path, validator)
            if recovered is None:
                return False
            self.save(path, recovered, validator=validator, force=True)
            return True

    def _read_existing(self, path: Path) -> Any | None:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def _enforce_destructive_guard(
        self,
        path: Path,
        existing: Any | None,
        incoming: Any,
        policy: PersistencePolicy,
    ) -> None:
        if existing is None:
            return
        old_count = self._record_count(existing)
        new_count = self._record_count(incoming)

        if policy.block_empty_replacement and old_count > 0 and new_count == 0:
            raise DestructiveWriteBlocked(
                f"Blocked empty replacement of populated data file {path}. Use force=True for an intentional reset."
            )

        if policy.block_large_count_drop and old_count > 0:
            drop_ratio = (old_count - new_count) / old_count
            if drop_ratio >= policy.max_count_drop_ratio:
                raise DestructiveWriteBlocked(
                    f"Blocked suspicious record-count drop for {path}: {old_count} to {new_count}."
                )

    @staticmethod
    def _record_count(data: Any) -> int:
        if isinstance(data, list):
            return len(data)
        if isinstance(data, dict):
            for key in ("items", "records", "schools", "rosters", "broadcasts", "packages"):
                value = data.get(key)
                if isinstance(value, list):
                    return len(value)
            return 1 if data else 0
        return 0

    def _backup_dir(self, path: Path) -> Path:
        return self.backup_root / path.stem

    def _snapshot(self, path: Path) -> Path:
        backup_dir = self._backup_dir(path)
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        destination = backup_dir / f"{path.stem}-{stamp}-{time.time_ns()}.json"
        shutil.copy2(path, destination)
        return destination

    def _prune_backups(self, path: Path, keep: int) -> None:
        if keep < 1:
            return
        backups = sorted(self._backup_dir(path).glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        for old in backups[keep:]:
            old.unlink(missing_ok=True)

    def _quarantine(self, path: Path) -> Path:
        self.quarantine_root.mkdir(parents=True, exist_ok=True)
        stamp = time.strftime("%Y%m%d-%H%M%S")
        destination = self.quarantine_root / f"{path.stem}-corrupt-{stamp}-{time.time_ns()}{path.suffix}"
        try:
            shutil.copy2(path, destination)
        except OSError:
            destination.write_text("Unable to preserve original file.", encoding="utf-8")
        return destination

    def _recover_latest(
        self,
        path: Path,
        validator: Callable[[Any], bool] | None,
    ) -> Any | None:
        backups = sorted(self._backup_dir(path).glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
        for candidate in backups:
            try:
                data = json.loads(candidate.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if validator and not validator(data):
                continue
            return data
        return None
