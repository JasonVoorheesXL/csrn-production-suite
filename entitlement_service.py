from __future__ import annotations

import copy
import json
import os
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from product_paths import PRODUCT_ID, ProductPaths


Verifier = Callable[[dict[str, Any]], tuple[bool, str]]


@dataclass(frozen=True)
class EntitlementResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.code in {
            "OK",
            "INSTALLATION_READY",
            "LICENSE_INSTALLED",
            "LICENSE_REMOVED",
        }


class EntitlementService:
    """Provider-neutral licensing boundary.

    Production license payloads are accepted only after a provider verifier confirms
    their authenticity. The application never embeds a shared signing secret.
    """

    CORE_FEATURES = {
        "core_broadcast",
        "captions",
        "weather",
        "graphics",
        "statistics",
        "themes",
        "social_publish",
        "game_recap",
    }

    def __init__(
        self,
        *,
        paths: ProductPaths,
        verifier: Verifier | None = None,
        clock: Callable[[], float] = time.time,
        environment: dict[str, str] | None = None,
    ) -> None:
        self.paths = paths
        self._verifier = verifier
        self._clock = clock
        self._environment = dict(os.environ if environment is None else environment)
        self.paths.ensure()

    @staticmethod
    def _read(path: Path, default: Any) -> Any:
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return copy.deepcopy(default)

    @staticmethod
    def _write(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.tmp-{os.getpid()}")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(path)

    def _installation(self) -> dict[str, Any]:
        current = self._read(self.paths.installation_file, {})
        if isinstance(current, dict) and current.get("installation_id"):
            return current
        record = {
            "schema": 1,
            "product_id": PRODUCT_ID,
            "installation_id": secrets.token_hex(16),
            "created_at": int(self._clock()),
        }
        self._write(self.paths.installation_file, record)
        return record

    def installation_request(self) -> EntitlementResult:
        installation = self._installation()
        return EntitlementResult(
            "INSTALLATION_READY",
            {
                "activation_request": {
                    **installation,
                    "requested_at": int(self._clock()),
                    "installed_mode": self.paths.installed_mode,
                }
            },
        )

    def _development_license(self) -> dict[str, Any]:
        return {
            "schema": 1,
            "product_id": PRODUCT_ID,
            "license_id": "development-source-checkout",
            "status": "development",
            "customer": "Local development checkout",
            "expires_at": 0,
            "features": sorted(self.CORE_FEATURES),
            "sports": ["*"],
            "signature_verified": False,
            "development_only": True,
        }

    def _normalized(self, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
        if not isinstance(payload, dict):
            return None, "LICENSE_OBJECT_REQUIRED"
        if str(payload.get("product_id", "")) != PRODUCT_ID:
            return None, "PRODUCT_MISMATCH"
        license_id = str(payload.get("license_id", "")).strip()
        status = str(payload.get("status", "")).strip().lower()
        if not license_id or status not in {"active", "trial", "suspended", "revoked"}:
            return None, "LICENSE_FIELDS_INVALID"
        features = payload.get("features", [])
        sports = payload.get("sports", [])
        if not isinstance(features, list) or not isinstance(sports, list):
            return None, "ENTITLEMENTS_INVALID"
        normalized_features = sorted(
            {str(item).strip() for item in features if str(item).strip() in self.CORE_FEATURES}
        )
        normalized_sports = sorted({str(item).strip() for item in sports if str(item).strip()})
        expires_at = int(payload.get("expires_at", 0) or 0)
        return {
            "schema": 1,
            "product_id": PRODUCT_ID,
            "license_id": license_id[:160],
            "status": status,
            "customer": str(payload.get("customer", "")).strip()[:240],
            "issued_at": int(payload.get("issued_at", 0) or 0),
            "expires_at": expires_at,
            "features": normalized_features,
            "sports": normalized_sports,
            "provider": str(payload.get("provider", "")).strip()[:120],
            "provider_reference": str(payload.get("provider_reference", "")).strip()[:240],
            "signature": str(payload.get("signature", "")).strip(),
            "installed_at": int(self._clock()),
            "signature_verified": True,
        }, ""

    def install_license(self, payload: Any) -> EntitlementResult:
        if not isinstance(payload, dict):
            return EntitlementResult("LICENSE_OBJECT_REQUIRED")
        normalized, error = self._normalized(payload)
        if error:
            return EntitlementResult(error)
        if self._verifier is None:
            return EntitlementResult(
                "VERIFIER_NOT_CONFIGURED",
                {"message": "A production activation provider must verify this license payload."},
            )
        verified, reason = self._verifier(copy.deepcopy(payload))
        if not verified:
            return EntitlementResult("SIGNATURE_INVALID", {"message": str(reason)[:500]})
        assert normalized is not None
        installation = self._installation()
        bound_installation = str(payload.get("installation_id", "")).strip()
        if bound_installation and bound_installation != installation["installation_id"]:
            return EntitlementResult("INSTALLATION_MISMATCH")
        normalized["installation_id"] = installation["installation_id"]
        self._write(self.paths.license_file, normalized)
        return EntitlementResult("LICENSE_INSTALLED", {"license": self.public_license(normalized)})

    def remove_license(self, confirmation: Any) -> EntitlementResult:
        if str(confirmation or "") != "REMOVE CSRN LICENSE":
            return EntitlementResult("CONFIRMATION_REQUIRED")
        previous = self._read(self.paths.license_file, None)
        if self.paths.license_file.exists():
            self.paths.license_file.unlink()
        return EntitlementResult("LICENSE_REMOVED", {"previous": self.public_license(previous)})

    @staticmethod
    def public_license(record: Any) -> dict[str, Any] | None:
        if not isinstance(record, dict):
            return None
        return {key: copy.deepcopy(value) for key, value in record.items() if key not in {"signature"}}

    def status(self) -> EntitlementResult:
        installation = self._installation()
        if not self.paths.installed_mode:
            license_record = self._development_license()
        else:
            license_record = self._read(self.paths.license_file, None)
        now = int(self._clock())
        valid = False
        reason = "UNLICENSED"
        if isinstance(license_record, dict):
            status = str(license_record.get("status", "")).lower()
            expires_at = int(license_record.get("expires_at", 0) or 0)
            expired = bool(expires_at and expires_at <= now)
            valid = status in {"active", "trial", "development"} and not expired
            reason = "EXPIRED" if expired else status.upper() or "UNLICENSED"
        return EntitlementResult(
            "OK",
            {
                "licensing": {
                    "product_id": PRODUCT_ID,
                    "installation_id": installation["installation_id"],
                    "installed_mode": self.paths.installed_mode,
                    "valid": valid,
                    "reason": reason,
                    "license": self.public_license(license_record),
                }
            },
        )

    def allows(self, feature: str, *, sport: str = "") -> bool:
        status = self.status().data["licensing"]
        record = status.get("license") or {}
        if not status.get("valid"):
            return False
        features = set(record.get("features", []))
        sports = {str(item).casefold() for item in record.get("sports", [])}
        sport_allowed = not sport or "*" in sports or sport.casefold() in sports
        return str(feature) in features and sport_allowed
