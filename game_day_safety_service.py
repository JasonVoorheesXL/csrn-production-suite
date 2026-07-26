from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class GameDaySafetyResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.code in {
            "OK",
            "SNAPSHOT_CREATED",
            "SNAPSHOT_CURRENT",
            "SNAPSHOT_VERIFIED",
        }


class GameDaySafetyService:
    """Flask-independent preflight and recoverable snapshot behavior."""

    SNAPSHOT_SCHEMA = 1
    SNAPSHOT_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,95}$")
    AUTOMATIC_KINDS = {"startup", "preflight"}

    def __init__(
        self,
        *,
        base_dir: Path,
        data_dir: Path,
        backup_root: Path,
        state_file: Path,
        security_file: Path,
        config_file: Path,
        version_file: Path,
        clock: Callable[[], float] = time.time,
        minimum_free_bytes: int = 512 * 1024 * 1024,
        automatic_retention: int = 10,
    ) -> None:
        self._base_dir = Path(base_dir)
        self._data_dir = Path(data_dir)
        self._backup_root = Path(backup_root)
        self._state_file = Path(state_file)
        self._security_file = Path(security_file)
        self._config_file = Path(config_file)
        self._version_file = Path(version_file)
        self._clock = clock
        self._minimum_free_bytes = max(0, int(minimum_free_bytes))
        self._automatic_retention = max(1, int(automatic_retention))

    @staticmethod
    def _hash_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _json_status(path: Path) -> tuple[bool, str]:
        if not path.exists():
            return False, "File is missing."
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            return False, f"JSON is not readable: {exc}"
        return True, "JSON is readable."

    def _write_status(self, directory: Path) -> tuple[bool, str]:
        try:
            directory.mkdir(parents=True, exist_ok=True)
            probe = directory / (
                f".csrn-write-test-{os.getpid()}-{int(self._clock() * 1000)}"
            )
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
        except OSError as exc:
            return False, f"Directory is not writable: {exc}"
        return True, "Directory is writable."

    def preflight(self) -> GameDaySafetyResult:
        checks: list[dict[str, Any]] = []

        def add(
            key: str,
            label: str,
            ok: bool,
            note: str,
            *,
            required: bool = True,
        ) -> None:
            checks.append(
                {
                    "key": key,
                    "label": label,
                    "ok": bool(ok),
                    "required": bool(required),
                    "note": str(note),
                }
            )

        add(
            "base_dir",
            "Application folder",
            self._base_dir.is_dir(),
            str(self._base_dir),
        )
        add(
            "data_dir",
            "Data folder",
            self._data_dir.is_dir(),
            str(self._data_dir),
        )
        for key, label, path in (
            ("configuration", "Configuration", self._config_file),
            ("state", "Live state", self._state_file),
            ("security", "Security state", self._security_file),
        ):
            ok, note = self._json_status(path)
            add(key, label, ok, note)

        version_ok = self._version_file.exists()
        version = ""
        if version_ok:
            try:
                version = self._version_file.read_text(encoding="utf-8").strip()
                version_ok = bool(version)
            except (OSError, UnicodeError):
                version_ok = False
        add(
            "version",
            "Runtime version",
            version_ok,
            version or "VERSION.txt is missing or empty.",
        )

        data_writable, data_note = self._write_status(self._data_dir)
        add("data_writable", "Data storage writable", data_writable, data_note)
        backup_writable, backup_note = self._write_status(self._backup_root)
        add(
            "backup_writable",
            "Game-day backup storage writable",
            backup_writable,
            backup_note,
        )

        try:
            free_bytes = int(shutil.disk_usage(self._base_dir).free)
            disk_ok = free_bytes >= self._minimum_free_bytes
            disk_note = (
                f"{free_bytes} bytes free; "
                f"minimum {self._minimum_free_bytes} bytes."
            )
        except OSError as exc:
            free_bytes = 0
            disk_ok = False
            disk_note = f"Disk space could not be read: {exc}"
        add("disk_space", "Free disk space", disk_ok, disk_note)

        snapshots = self.list_snapshots().data.get("snapshots", [])
        recent = snapshots[0] if snapshots else None
        recent_ok = bool(
            recent
            and int(self._clock()) - int(recent.get("created_at", 0))
            <= 24 * 60 * 60
        )
        add(
            "recent_snapshot",
            "Recent safety snapshot",
            recent_ok,
            (
                f"Latest snapshot: {recent.get('snapshot_id', '')}"
                if recent
                else "No game-day safety snapshot exists yet."
            ),
            required=False,
        )

        ready = all(
            check["ok"] for check in checks if check.get("required", True)
        )
        return GameDaySafetyResult(
            "OK" if ready else "PREFLIGHT_FAILED",
            {
                "preflight": {
                    "ready": ready,
                    "version": version,
                    "checked_at": int(self._clock()),
                    "free_bytes": free_bytes,
                    "checks": checks,
                }
            },
        )

    def _snapshot_path(self, snapshot_id: str) -> Path | None:
        normalized = str(snapshot_id or "").strip().lower()
        if not self.SNAPSHOT_ID_PATTERN.fullmatch(normalized):
            return None
        return self._backup_root / normalized

    def _manifest(self, directory: Path) -> dict[str, Any] | None:
        path = directory / "manifest.json"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    def list_snapshots(self) -> GameDaySafetyResult:
        snapshots: list[dict[str, Any]] = []
        if self._backup_root.exists():
            for directory in self._backup_root.iterdir():
                if not directory.is_dir() or directory.name.startswith(".tmp-"):
                    continue
                manifest = self._manifest(directory)
                if not manifest:
                    continue
                snapshots.append(
                    {
                        "snapshot_id": str(
                            manifest.get("snapshot_id", directory.name)
                        ),
                        "kind": str(manifest.get("kind", "manual")),
                        "note": str(manifest.get("note", "")),
                        "created_at": int(manifest.get("created_at", 0) or 0),
                        "version": str(manifest.get("version", "")),
                        "file_count": int(manifest.get("file_count", 0) or 0),
                        "total_bytes": int(manifest.get("total_bytes", 0) or 0),
                    }
                )
        snapshots.sort(
            key=lambda item: (item["created_at"], item["snapshot_id"]),
            reverse=True,
        )
        return GameDaySafetyResult("OK", {"snapshots": snapshots})

    def _next_snapshot_id(self, kind: str) -> str:
        timestamp = datetime.fromtimestamp(
            self._clock(),
            tz=timezone.utc,
        ).strftime("%Y%m%d-%H%M%S")
        base = f"{timestamp}-{kind}"
        candidate = base
        sequence = 2
        while (self._backup_root / candidate).exists() or (
            self._backup_root / f".tmp-{candidate}"
        ).exists():
            candidate = f"{base}-{sequence}"
            sequence += 1
        return candidate

    def _payload_files(self, payload_root: Path) -> list[dict[str, Any]]:
        files: list[dict[str, Any]] = []
        for path in sorted(payload_root.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(payload_root).as_posix()
            files.append(
                {
                    "path": relative,
                    "size": path.stat().st_size,
                    "sha256": self._hash_file(path),
                }
            )
        return files

    def create_snapshot(
        self,
        *,
        kind: str = "manual",
        note: str = "",
    ) -> GameDaySafetyResult:
        kind = re.sub(r"[^a-z0-9_-]+", "-", str(kind).strip().lower())
        kind = kind.strip("-") or "manual"
        preflight = self.preflight()
        if preflight.code == "PREFLIGHT_FAILED":
            return GameDaySafetyResult(
                "PREFLIGHT_FAILED",
                preflight.data,
            )

        self._backup_root.mkdir(parents=True, exist_ok=True)
        snapshot_id = self._next_snapshot_id(kind)
        final_path = self._backup_root / snapshot_id
        temporary_path = self._backup_root / f".tmp-{snapshot_id}"
        payload_root = temporary_path / "payload"

        try:
            if temporary_path.exists():
                shutil.rmtree(temporary_path)
            payload_root.mkdir(parents=True)
            shutil.copytree(
                self._data_dir,
                payload_root / "Data",
                ignore=shutil.ignore_patterns("Backups"),
            )
            for source in (
                self._state_file,
                self._security_file,
                self._version_file,
            ):
                if source.exists():
                    shutil.copy2(source, payload_root / source.name)

            files = self._payload_files(payload_root)
            manifest = {
                "schema": self.SNAPSHOT_SCHEMA,
                "snapshot_id": snapshot_id,
                "kind": kind,
                "note": str(note).strip()[:500],
                "created_at": int(self._clock()),
                "version": self._version_file.read_text(
                    encoding="utf-8"
                ).strip(),
                "file_count": len(files),
                "total_bytes": sum(int(item["size"]) for item in files),
                "files": files,
            }
            (temporary_path / "manifest.json").write_text(
                json.dumps(manifest, indent=2),
                encoding="utf-8",
            )
            temporary_path.replace(final_path)
            self._prune_automatic_snapshots()
        except Exception as exc:
            shutil.rmtree(temporary_path, ignore_errors=True)
            return GameDaySafetyResult(
                "SNAPSHOT_FAILED",
                {"message": str(exc), "snapshot_id": snapshot_id},
            )

        return GameDaySafetyResult(
            "SNAPSHOT_CREATED",
            {"snapshot": manifest, "path": str(final_path)},
        )

    def _prune_automatic_snapshots(self) -> None:
        snapshots = self.list_snapshots().data["snapshots"]
        automatic = [
            item
            for item in snapshots
            if item.get("kind") in self.AUTOMATIC_KINDS
        ]
        for item in automatic[self._automatic_retention :]:
            path = self._snapshot_path(str(item.get("snapshot_id", "")))
            if path and path.exists():
                shutil.rmtree(path, ignore_errors=True)

    def verify_snapshot(self, snapshot_id: str) -> GameDaySafetyResult:
        directory = self._snapshot_path(snapshot_id)
        if directory is None:
            return GameDaySafetyResult("INVALID_SNAPSHOT_ID")
        if not directory.is_dir():
            return GameDaySafetyResult("SNAPSHOT_NOT_FOUND")
        manifest = self._manifest(directory)
        if not manifest or manifest.get("schema") != self.SNAPSHOT_SCHEMA:
            return GameDaySafetyResult("SNAPSHOT_INVALID")

        payload_root = directory / "payload"
        errors: list[dict[str, str]] = []
        files = manifest.get("files", [])
        if not isinstance(files, list):
            return GameDaySafetyResult("SNAPSHOT_INVALID")
        for item in files:
            if not isinstance(item, dict):
                errors.append({"path": "", "error": "Invalid manifest entry."})
                continue
            relative = str(item.get("path", ""))
            target = payload_root / Path(relative)
            try:
                target.relative_to(payload_root)
            except ValueError:
                errors.append({"path": relative, "error": "Unsafe path."})
                continue
            if not target.is_file():
                errors.append({"path": relative, "error": "File is missing."})
                continue
            if target.stat().st_size != int(item.get("size", -1)):
                errors.append({"path": relative, "error": "Size mismatch."})
                continue
            if self._hash_file(target) != str(item.get("sha256", "")):
                errors.append({"path": relative, "error": "Hash mismatch."})

        verified = not errors
        return GameDaySafetyResult(
            "SNAPSHOT_VERIFIED" if verified else "SNAPSHOT_CORRUPT",
            {
                "verification": {
                    "snapshot_id": str(manifest.get("snapshot_id", snapshot_id)),
                    "verified": verified,
                    "checked_at": int(self._clock()),
                    "file_count": len(files),
                    "errors": errors,
                }
            },
        )

    def ensure_startup_snapshot(
        self,
        *,
        max_age_seconds: int = 12 * 60 * 60,
    ) -> GameDaySafetyResult:
        preflight = self.preflight()
        if preflight.code == "PREFLIGHT_FAILED":
            return preflight

        now = int(self._clock())
        snapshots = self.list_snapshots().data["snapshots"]
        latest = next(
            (item for item in snapshots if item.get("kind") == "startup"),
            None,
        )
        if latest and now - int(latest.get("created_at", 0)) <= max(
            0,
            int(max_age_seconds),
        ):
            verification = self.verify_snapshot(str(latest["snapshot_id"]))
            if verification.code == "SNAPSHOT_VERIFIED":
                return GameDaySafetyResult(
                    "SNAPSHOT_CURRENT",
                    {
                        "snapshot": latest,
                        "verification": verification.data["verification"],
                        "preflight": preflight.data["preflight"],
                    },
                )

        result = self.create_snapshot(
            kind="startup",
            note="Automatic startup safety snapshot.",
        )
        if result.code == "SNAPSHOT_CREATED":
            result.data["preflight"] = preflight.data["preflight"]
        return result
