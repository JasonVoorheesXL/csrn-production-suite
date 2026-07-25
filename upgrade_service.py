from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, ContextManager


InspectCandidate = Callable[[Path], dict[str, Any]]
RunMigration = Callable[[Path, dict[str, Any], bool], dict[str, Any]]
LoadSecurity = Callable[[], dict[str, Any]]
ActivateSecretKey = Callable[[str], None]


@dataclass(frozen=True)
class UpgradeResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.code == "OK"


class UpgradeService:
    """Flask-independent upgrade inspection and migration coordination."""

    def __init__(
        self,
        *,
        current_dir: Path,
        defaults: dict[str, Any],
        inspect_candidate: InspectCandidate,
        migrate: RunMigration,
        load_security: LoadSecurity,
        activate_secret_key: ActivateSecretKey,
        report_store: dict[str, Any],
        migration_lock: ContextManager[Any],
    ) -> None:
        self._current_dir = Path(current_dir)
        self._defaults = copy.deepcopy(defaults)
        self._inspect_candidate = inspect_candidate
        self._migrate = migrate
        self._load_security = load_security
        self._activate_secret_key = activate_secret_key
        self._report_store = report_store
        self._migration_lock = migration_lock

    def candidate(self) -> UpgradeResult:
        try:
            candidate = self._inspect_candidate(self._current_dir)
        except Exception as exc:
            return UpgradeResult(
                "INSPECTION_FAILED",
                {"message": str(exc)},
            )
        if not isinstance(candidate, dict):
            return UpgradeResult(
                "INSPECTION_FAILED",
                {"message": "Upgrade inspection returned an invalid payload."},
            )
        return UpgradeResult(
            "OK",
            {"candidate": copy.deepcopy(candidate)},
        )

    def status(self) -> UpgradeResult:
        return UpgradeResult(
            "OK",
            {"report": copy.deepcopy(self._report_store)},
        )

    def run(self, include_security: Any = True) -> UpgradeResult:
        include_security_flag = bool(include_security)
        with self._migration_lock:
            try:
                report = self._migrate(
                    self._current_dir,
                    copy.deepcopy(self._defaults),
                    include_security_flag,
                )
            except Exception as exc:
                report = {
                    "status": "FAILED",
                    "source_build": "",
                    "source_path": "",
                    "backup_path": "",
                    "copied_files": 0,
                    "merged_config": False,
                    "security_migrated": False,
                    "errors": [str(exc)],
                }
            if not isinstance(report, dict):
                report = {
                    "status": "FAILED",
                    "source_build": "",
                    "source_path": "",
                    "backup_path": "",
                    "copied_files": 0,
                    "merged_config": False,
                    "security_migrated": False,
                    "errors": ["Upgrade migration returned an invalid report."],
                }
            stored = copy.deepcopy(report)
            self._report_store.clear()
            self._report_store.update(stored)

        response = copy.deepcopy(report)
        if response.get("security_migrated"):
            try:
                security = self._load_security()
                secret_key = str(security.get("secret_key", "")).strip()
                if not secret_key:
                    raise ValueError("Migrated security data has no secret key.")
                self._activate_secret_key(secret_key)
            except Exception as exc:
                errors = response.setdefault("errors", [])
                if not isinstance(errors, list):
                    errors = []
                    response["errors"] = errors
                errors.append(f"Security session refresh failed: {exc}")
                response["security_refresh_failed"] = True

        security_migrated = bool(response.get("security_migrated"))
        response["active_pin"] = (
            "PREVIOUS_PIN" if security_migrated else "CREATE_NEW_PIN"
        )
        response["pin_message"] = (
            "Migration is complete. Unlock the Production Suite with the "
            "operator PIN from the previous build."
            if security_migrated
            else "Migration is complete. Create a new 6-digit operator PIN "
            "on this screen."
        )
        return UpgradeResult("OK", {"report": response})
