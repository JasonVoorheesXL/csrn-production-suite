from __future__ import annotations

import json
import os
import re
import shutil
import time
from contextlib import nullcontext
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, ContextManager


@dataclass(frozen=True)
class RecoveryResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.code in {
            "OK",
            "STARTUP_MARKED",
            "UNCLEAN_SHUTDOWN_DETECTED",
            "CLEAN_SHUTDOWN_MARKED",
            "UNCLEAN_MARKER_CLEARED",
            "KNOWN_GOOD_REGISTERED",
            "ROLLBACK_PLAN_READY",
            "SNAPSHOT_RESTORED",
            "RECOVERY_REHEARSAL_READY",
        }


class RecoveryService:
    """Flask-independent restore, crash detection, and rollback planning."""

    COMMIT_PATTERN = re.compile(r"^[0-9a-fA-F]{7,40}$")

    def __init__(
        self,
        *,
        safety_service: Any,
        data_dir: Path,
        backup_root: Path,
        recovery_root: Path,
        state_file: Path,
        security_file: Path,
        version_file: Path,
        load_state: Callable[[], dict[str, Any]],
        clock: Callable[[], float] = time.time,
        transaction_lock: ContextManager[Any] | None = None,
    ) -> None:
        self._safety_service = safety_service
        self._data_dir = Path(data_dir)
        self._backup_root = Path(backup_root)
        self._recovery_root = Path(recovery_root)
        self._state_file = Path(state_file)
        self._security_file = Path(security_file)
        self._version_file = Path(version_file)
        self._load_state = load_state
        self._clock = clock
        self._transaction_lock = transaction_lock
        self._session_marker = self._recovery_root / "active_session.json"
        self._last_unclean = self._recovery_root / "last_unclean_shutdown.json"
        self._last_restore = self._recovery_root / "last_restore.json"
        self._known_good = self._recovery_root / "known_good_release.json"

    @staticmethod
    def _read_json(path: Path, default: Any) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return default

    @staticmethod
    def _remove_path(path: Path) -> None:
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        elif path.exists() or path.is_symlink():
            path.unlink()

    def _write_json(self, path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
        temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        temporary.replace(path)

    def _version(self) -> str:
        try:
            return self._version_file.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeError):
            return ""

    def _lock(self) -> ContextManager[Any]:
        return self._transaction_lock or nullcontext()

    def _live_broadcast_active(self) -> bool:
        try:
            state = self._load_state()
        except Exception:
            return True
        if not isinstance(state, dict):
            return True
        return (
            str(state.get("status", "")).strip().lower() == "live"
            or bool(state.get("clock_running"))
        )

    def status(self) -> RecoveryResult:
        active = self._read_json(self._session_marker, None)
        unclean = self._read_json(self._last_unclean, None)
        last_restore = self._read_json(self._last_restore, None)
        known_good = self._read_json(self._known_good, None)
        return RecoveryResult(
            "OK",
            {
                "recovery": {
                    "active_session": active,
                    "unclean_shutdown": unclean,
                    "last_restore": last_restore,
                    "known_good_release": known_good,
                    "live_broadcast_active": self._live_broadcast_active(),
                }
            },
        )

    def mark_startup(self, *, pid: int | None = None) -> RecoveryResult:
        self._recovery_root.mkdir(parents=True, exist_ok=True)
        previous = self._read_json(self._session_marker, None)
        now = int(self._clock())
        if isinstance(previous, dict):
            unclean = {
                **previous,
                "detected_at": now,
                "detected_by_version": self._version(),
            }
            self._write_json(self._last_unclean, unclean)
        marker = {
            "started_at": now,
            "pid": int(pid if pid is not None else os.getpid()),
            "version": self._version(),
        }
        self._write_json(self._session_marker, marker)
        return RecoveryResult(
            "UNCLEAN_SHUTDOWN_DETECTED" if previous else "STARTUP_MARKED",
            {
                "session": marker,
                "previous_session": previous,
            },
        )

    def mark_clean_shutdown(self) -> RecoveryResult:
        marker = self._read_json(self._session_marker, None)
        if self._session_marker.exists():
            self._session_marker.unlink()
        return RecoveryResult(
            "CLEAN_SHUTDOWN_MARKED",
            {
                "session": marker,
                "stopped_at": int(self._clock()),
            },
        )

    def clear_unclean_shutdown(self) -> RecoveryResult:
        previous = self._read_json(self._last_unclean, None)
        if self._last_unclean.exists():
            self._last_unclean.unlink()
        return RecoveryResult(
            "UNCLEAN_MARKER_CLEARED",
            {"previous": previous},
        )

    def register_known_good(
        self,
        *,
        commit: str,
        note: str = "",
    ) -> RecoveryResult:
        normalized = str(commit or "").strip()
        if not self.COMMIT_PATTERN.fullmatch(normalized):
            return RecoveryResult("INVALID_RELEASE_COMMIT")
        record = {
            "commit": normalized.lower(),
            "version": self._version(),
            "note": str(note or "").strip()[:500],
            "marked_at": int(self._clock()),
        }
        self._write_json(self._known_good, record)
        return RecoveryResult("KNOWN_GOOD_REGISTERED", {"release": record})

    def rollback_plan(self) -> RecoveryResult:
        release = self._read_json(self._known_good, None)
        if not isinstance(release, dict):
            return RecoveryResult("KNOWN_GOOD_NOT_SET")
        commit = str(release.get("commit", ""))
        if not self.COMMIT_PATTERN.fullmatch(commit):
            return RecoveryResult("KNOWN_GOOD_INVALID")
        return RecoveryResult(
            "ROLLBACK_PLAN_READY",
            {
                "rollback": {
                    "release": release,
                    "requires_application_stopped": True,
                    "requires_clean_working_tree": True,
                    "pre_rollback_snapshot": True,
                    "command": (
                        "python tools\\rollback_to_known_good.py "
                        f"--confirm {commit}"
                    ),
                }
            },
        )

    def _validate_payload_json(self, payload_root: Path) -> list[str]:
        errors: list[str] = []
        for path in sorted(payload_root.rglob("*.json")):
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                errors.append(f"{path.relative_to(payload_root).as_posix()}: {exc}")
        return errors

    def _apply_payload(self, payload_root: Path) -> None:
        staged_data = payload_root / "Data"
        if not staged_data.is_dir():
            raise RuntimeError("Snapshot payload does not contain Data.")

        self._data_dir.mkdir(parents=True, exist_ok=True)
        for child in tuple(self._data_dir.iterdir()):
            if child.name == "Backups":
                continue
            self._remove_path(child)
        for child in staged_data.iterdir():
            destination = self._data_dir / child.name
            if child.is_dir():
                shutil.copytree(child, destination)
            else:
                shutil.copy2(child, destination)

        for target in (self._state_file, self._security_file):
            source = payload_root / target.name
            if source.is_file():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)

    def rehearse_restore(self, snapshot_id: str) -> RecoveryResult:
        verification = self._safety_service.verify_snapshot(snapshot_id)
        if verification.code != "SNAPSHOT_VERIFIED":
            return RecoveryResult(verification.code, verification.data)
        directory = self._backup_root / str(snapshot_id).strip().lower()
        payload_root = directory / "payload"
        errors = self._validate_payload_json(payload_root)
        if errors:
            return RecoveryResult(
                "RESTORE_PAYLOAD_INVALID",
                {"snapshot_id": snapshot_id, "errors": errors},
            )
        return RecoveryResult(
            "RECOVERY_REHEARSAL_READY",
            {
                "rehearsal": {
                    "snapshot_id": snapshot_id,
                    "verified": True,
                    "json_files_valid": True,
                    "would_create_pre_restore_snapshot": True,
                    "live_broadcast_active": self._live_broadcast_active(),
                }
            },
        )

    def restore_snapshot(
        self,
        snapshot_id: str,
        *,
        confirmation: str,
        note: str = "",
    ) -> RecoveryResult:
        normalized = str(snapshot_id or "").strip().lower()
        if str(confirmation or "").strip().lower() != normalized:
            return RecoveryResult("RESTORE_CONFIRMATION_REQUIRED")
        if self._live_broadcast_active():
            return RecoveryResult("LIVE_BROADCAST_ACTIVE")

        verification = self._safety_service.verify_snapshot(normalized)
        if verification.code != "SNAPSHOT_VERIFIED":
            return RecoveryResult(verification.code, verification.data)

        pre_restore = self._safety_service.create_snapshot(
            kind="pre-restore",
            note=(
                f"Automatic snapshot before restoring {normalized}. "
                f"{str(note or '').strip()}"
            ).strip(),
        )
        if pre_restore.code != "SNAPSHOT_CREATED":
            return RecoveryResult(
                "PRE_RESTORE_SNAPSHOT_FAILED",
                {"pre_restore": pre_restore.data},
            )

        pre_restore_id = str(
            pre_restore.data.get("snapshot", {}).get("snapshot_id", "")
        )
        payload_root = self._backup_root / normalized / "payload"
        errors = self._validate_payload_json(payload_root)
        if errors:
            return RecoveryResult(
                "RESTORE_PAYLOAD_INVALID",
                {
                    "snapshot_id": normalized,
                    "pre_restore_snapshot_id": pre_restore_id,
                    "errors": errors,
                },
            )

        rollback_payload = self._backup_root / pre_restore_id / "payload"
        rolled_back = False
        try:
            with self._lock():
                self._apply_payload(payload_root)
        except Exception as exc:
            try:
                with self._lock():
                    self._apply_payload(rollback_payload)
                rolled_back = True
            except Exception:
                rolled_back = False
            return RecoveryResult(
                "RESTORE_FAILED",
                {
                    "message": str(exc),
                    "snapshot_id": normalized,
                    "pre_restore_snapshot_id": pre_restore_id,
                    "rolled_back": rolled_back,
                },
            )

        record = {
            "snapshot_id": normalized,
            "pre_restore_snapshot_id": pre_restore_id,
            "restored_at": int(self._clock()),
            "note": str(note or "").strip()[:500],
            "runtime_version_retained": self._version(),
        }
        self._write_json(self._last_restore, record)
        return RecoveryResult("SNAPSHOT_RESTORED", {"restore": record})
