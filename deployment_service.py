from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from product_paths import PRODUCT_ID, ProductPaths


@dataclass(frozen=True)
class DeploymentResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.code in {
            "OK",
            "UPDATE_VALIDATED",
            "UPDATE_PLAN_READY",
            "SUPPORT_BUNDLE_CREATED",
        }


class DeploymentService:
    """Installer, update-package, and customer-safe diagnostics boundary."""

    VERSION_PATTERN = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:[-+]([0-9A-Za-z.-]+))?$")
    SENSITIVE_KEYS = {
        "password",
        "pin_hash",
        "secret_key",
        "signature",
        "token",
        "access_token",
        "refresh_token",
        "client_secret",
        "api_key",
    }

    def __init__(
        self,
        *,
        paths: ProductPaths,
        version_file: Path,
        entitlement_service: Any,
        create_snapshot: Callable[..., Any] | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.paths = paths
        self.version_file = Path(version_file)
        self.entitlement_service = entitlement_service
        self.create_snapshot = create_snapshot
        self._clock = clock
        self.paths.ensure()

    @staticmethod
    def _hash_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @classmethod
    def _version_key(cls, value: str) -> tuple[int, int, int, tuple[object, ...]] | None:
        match = cls.VERSION_PATTERN.fullmatch(str(value or "").strip())
        if not match:
            return None
        prerelease = match.group(4)
        pre_key: tuple[object, ...]
        if prerelease is None:
            pre_key = (1,)
        else:
            parts: list[object] = [0]
            for part in prerelease.split("."):
                parts.append(int(part) if part.isdigit() else part.casefold())
            pre_key = tuple(parts)
        return int(match.group(1)), int(match.group(2)), int(match.group(3)), pre_key

    def current_version(self) -> str:
        try:
            return self.version_file.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeError):
            return ""

    def status(self) -> DeploymentResult:
        licensing = self.entitlement_service.status().data.get("licensing", {})
        return DeploymentResult(
            "OK",
            {
                "deployment": {
                    "product_id": PRODUCT_ID,
                    "version": self.current_version(),
                    "installed_mode": self.paths.installed_mode,
                    "paths": {
                        "application": str(self.paths.base_dir),
                        "runtime": str(self.paths.runtime_root),
                        "data": str(self.paths.data_dir),
                        "logs": str(self.paths.logs_dir),
                        "exports": str(self.paths.exports_dir),
                        "updates": str(self.paths.updates_dir),
                    },
                    "licensing": licensing,
                    "update_policy": {
                        "in_process_binary_replacement": False,
                        "pre_update_snapshot": True,
                        "hash_validation_required": True,
                        "downgrade_blocked_by_default": True,
                    },
                }
            },
        )

    @staticmethod
    def _load_manifest(path: Path) -> dict[str, Any] | None:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    def validate_update(self, package_root: Path, *, allow_downgrade: bool = False) -> DeploymentResult:
        root = Path(package_root).resolve()
        manifest_path = root / "release.json"
        manifest = self._load_manifest(manifest_path)
        if manifest is None:
            return DeploymentResult("MANIFEST_INVALID")
        if str(manifest.get("product_id", "")) != PRODUCT_ID:
            return DeploymentResult("PRODUCT_MISMATCH")

        candidate_version = str(manifest.get("version", "")).strip()
        candidate_key = self._version_key(candidate_version)
        current_key = self._version_key(self.current_version())
        if candidate_key is None:
            return DeploymentResult("VERSION_INVALID")
        if current_key is not None and candidate_key < current_key and not allow_downgrade:
            return DeploymentResult(
                "DOWNGRADE_BLOCKED",
                {"current_version": self.current_version(), "candidate_version": candidate_version},
            )

        files = manifest.get("files")
        if not isinstance(files, list) or not files:
            return DeploymentResult("FILE_MANIFEST_REQUIRED")
        errors: list[dict[str, str]] = []
        validated: list[dict[str, Any]] = []
        for item in files:
            if not isinstance(item, dict):
                errors.append({"path": "", "error": "Invalid file entry."})
                continue
            relative = Path(str(item.get("path", "")))
            if relative.is_absolute() or ".." in relative.parts:
                errors.append({"path": str(relative), "error": "Unsafe path."})
                continue
            target = (root / relative).resolve()
            try:
                target.relative_to(root)
            except ValueError:
                errors.append({"path": str(relative), "error": "Unsafe path."})
                continue
            if not target.is_file():
                errors.append({"path": str(relative), "error": "Missing file."})
                continue
            expected_size = int(item.get("size", -1))
            expected_hash = str(item.get("sha256", "")).lower()
            if target.stat().st_size != expected_size:
                errors.append({"path": str(relative), "error": "Size mismatch."})
                continue
            actual_hash = self._hash_file(target)
            if actual_hash != expected_hash:
                errors.append({"path": str(relative), "error": "Hash mismatch."})
                continue
            validated.append({"path": relative.as_posix(), "size": expected_size, "sha256": actual_hash})

        if errors:
            return DeploymentResult("PACKAGE_CORRUPT", {"errors": errors})
        return DeploymentResult(
            "UPDATE_VALIDATED",
            {
                "update": {
                    "package_root": str(root),
                    "manifest": copy.deepcopy(manifest),
                    "validated_files": validated,
                    "current_version": self.current_version(),
                    "candidate_version": candidate_version,
                }
            },
        )

    def prepare_update(self, package_root: Path, *, confirmation: Any) -> DeploymentResult:
        if str(confirmation or "") != "PREPARE CSRN UPDATE":
            return DeploymentResult("CONFIRMATION_REQUIRED")
        validation = self.validate_update(package_root)
        if not validation.ok:
            return validation
        snapshot = None
        if self.create_snapshot is not None:
            snapshot_result = self.create_snapshot(kind="pre-update", note="Automatic snapshot before staged update.")
            if not getattr(snapshot_result, "ok", False):
                return DeploymentResult(
                    "SNAPSHOT_FAILED",
                    {"snapshot": getattr(snapshot_result, "data", {})},
                )
            snapshot = getattr(snapshot_result, "data", {})
        update = validation.data["update"]
        plan = {
            "status": "READY",
            "prepared_at": int(self._clock()),
            "package_root": update["package_root"],
            "current_version": update["current_version"],
            "candidate_version": update["candidate_version"],
            "snapshot": snapshot,
            "requires_application_stopped": True,
            "external_updater_required": True,
            "binary_replacement_performed": False,
        }
        plan_path = self.paths.updates_dir / "pending_update.json"
        plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
        return DeploymentResult("UPDATE_PLAN_READY", {"update_plan": plan, "path": str(plan_path)})

    @classmethod
    def _redact(cls, value: Any, key: str = "") -> Any:
        if key.casefold() in cls.SENSITIVE_KEYS:
            return "[REDACTED]"
        if isinstance(value, dict):
            return {str(k): cls._redact(v, str(k)) for k, v in value.items()}
        if isinstance(value, list):
            return [cls._redact(item) for item in value]
        return value

    def create_support_bundle(self, *, note: str = "") -> DeploymentResult:
        timestamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime(self._clock()))
        destination = self.paths.support_dir / f"csrn-support-{timestamp}.zip"
        summary = {
            "created_at": int(self._clock()),
            "note": str(note or "").strip()[:1000],
            "deployment": self.status().data["deployment"],
        }
        files_added = 0
        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("summary.json", json.dumps(self._redact(summary), indent=2))
            files_added += 1
            candidates = [
                self.paths.data_dir / "Settings" / "config.json",
                self.paths.data_dir / "Releases" / "game_day_release_manifest.json",
                self.paths.data_dir / "Rehearsals" / "rehearsals.json",
                self.paths.data_dir / "Settings" / "hardware_commissioning.json",
                self.paths.data_dir / "Weather" / "weather_state.json",
            ]
            for path in candidates:
                if not path.is_file():
                    continue
                try:
                    payload = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, UnicodeError, json.JSONDecodeError):
                    continue
                relative = f"diagnostics/{path.name}"
                archive.writestr(relative, json.dumps(self._redact(payload), indent=2))
                files_added += 1
            if self.paths.logs_dir.exists():
                for path in sorted(self.paths.logs_dir.glob("*.log"))[-10:]:
                    try:
                        archive.write(path, f"logs/{path.name}")
                        files_added += 1
                    except OSError:
                        pass
        return DeploymentResult(
            "SUPPORT_BUNDLE_CREATED",
            {"support_bundle": {"path": str(destination), "files": files_added}},
        )
