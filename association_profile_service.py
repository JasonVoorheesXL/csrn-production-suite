from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from association_import_service import AssociationImportService, AssociationProfile


Record = dict[str, Any]
Clock = Callable[[], datetime]


@dataclass(frozen=True)
class AssociationProfileResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.code == "OK"


class AssociationProfileService:
    """Manage validated association source profiles stored as JSON files."""

    PROFILE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,79}$")

    def __init__(
        self,
        profile_directory: Path,
        *,
        protected_ids: Iterable[str] | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._profile_directory = Path(profile_directory)
        self._protected_ids = {
            str(value).strip().lower()
            for value in (protected_ids or [])
            if str(value).strip()
        }
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    @classmethod
    def normalize_profile_id(cls, value: str) -> str:
        normalized = "".join(
            character.lower() if character.isalnum() else "-"
            for character in str(value or "").strip()
        )
        while "--" in normalized:
            normalized = normalized.replace("--", "-")
        return normalized.strip("-")[:80]

    def list_profiles(self) -> AssociationProfileResult:
        self._ensure_directory()
        profiles: list[Record] = []
        invalid_profiles: list[Record] = []

        for path in sorted(self._profile_directory.glob("*.json")):
            result = self._read_path(path)
            if result.ok:
                profiles.append(result.data["profile"])
            else:
                invalid_profiles.append(
                    {
                        "filename": path.name,
                        "error": result.code,
                    }
                )

        profiles.sort(
            key=lambda item: (
                str(item.get("state", "")),
                str(item.get("association", "")).casefold(),
                str(item.get("name", "")).casefold(),
            )
        )
        return AssociationProfileResult(
            "OK",
            {
                "profiles": profiles,
                "invalid_profiles": invalid_profiles,
            },
        )

    def read(self, profile_id: str) -> AssociationProfileResult:
        normalized = self._validated_requested_id(profile_id)
        if not normalized:
            return AssociationProfileResult("INVALID_PROFILE_ID")
        path = self._profile_path(normalized)
        if not path.exists():
            return AssociationProfileResult("PROFILE_NOT_FOUND")
        return self._read_path(path)

    def create(self, incoming: Record) -> AssociationProfileResult:
        prepared = self._prepare(incoming)
        if not prepared.ok:
            return prepared
        profile = prepared.data["profile"]
        path = self._profile_path(str(profile["id"]))
        if path.exists():
            return AssociationProfileResult("PROFILE_ALREADY_EXISTS")
        return self._write(path, profile, created_at="")

    def update(
        self,
        profile_id: str,
        incoming: Record,
    ) -> AssociationProfileResult:
        requested_id = self._validated_requested_id(profile_id)
        if not requested_id:
            return AssociationProfileResult("INVALID_PROFILE_ID")
        path = self._profile_path(requested_id)
        if not path.exists():
            return AssociationProfileResult("PROFILE_NOT_FOUND")

        prepared = self._prepare(incoming, fallback_id=requested_id)
        if not prepared.ok:
            return prepared
        profile = prepared.data["profile"]
        if profile["id"] != requested_id:
            return AssociationProfileResult("PROFILE_ID_CONFLICT")

        existing_created_at = ""
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(existing, dict):
                existing_created_at = str(existing.get("created_at", ""))
        except (OSError, json.JSONDecodeError):
            pass
        return self._write(path, profile, created_at=existing_created_at)

    def delete(self, profile_id: str) -> AssociationProfileResult:
        normalized = self._validated_requested_id(profile_id)
        if not normalized:
            return AssociationProfileResult("INVALID_PROFILE_ID")
        if normalized in self._protected_ids:
            return AssociationProfileResult("PROFILE_PROTECTED")
        path = self._profile_path(normalized)
        if not path.exists():
            return AssociationProfileResult("PROFILE_NOT_FOUND")
        try:
            path.unlink()
        except OSError:
            return AssociationProfileResult("PROFILE_DELETE_FAILED")
        return AssociationProfileResult("OK", {"deleted": True, "id": normalized})

    def _prepare(
        self,
        incoming: Record,
        *,
        fallback_id: str = "",
    ) -> AssociationProfileResult:
        if not isinstance(incoming, dict):
            return AssociationProfileResult("INVALID_PROFILE_PAYLOAD")
        data = copy.deepcopy(incoming)
        supplied_id = str(data.get("id", "")).strip()
        if supplied_id:
            normalized_id = self.normalize_profile_id(supplied_id)
            if supplied_id != normalized_id:
                return AssociationProfileResult("INVALID_PROFILE_ID")
        else:
            normalized_id = fallback_id or self.normalize_profile_id(
                str(data.get("name", ""))
            )
        if not normalized_id or not self.PROFILE_ID_PATTERN.fullmatch(normalized_id):
            return AssociationProfileResult("INVALID_PROFILE_ID")
        data["id"] = normalized_id

        try:
            profile = AssociationProfile.from_dict(data)
        except ValueError as exc:
            return AssociationProfileResult(str(exc))

        payload = AssociationImportService.profile_payload(profile)
        return AssociationProfileResult("OK", {"profile": payload})

    def _read_path(self, path: Path) -> AssociationProfileResult:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except OSError:
            return AssociationProfileResult("PROFILE_READ_FAILED")
        except json.JSONDecodeError:
            return AssociationProfileResult("PROFILE_JSON_INVALID")
        if not isinstance(data, dict):
            return AssociationProfileResult("INVALID_PROFILE_PAYLOAD")

        prepared = self._prepare(data)
        if not prepared.ok:
            return prepared
        profile = prepared.data["profile"]
        if path.stem != profile["id"]:
            return AssociationProfileResult("PROFILE_FILENAME_MISMATCH")
        profile["created_at"] = str(data.get("created_at", ""))
        profile["updated_at"] = str(data.get("updated_at", ""))
        profile["protected"] = profile["id"] in self._protected_ids
        return AssociationProfileResult("OK", {"profile": profile})

    def _write(
        self,
        path: Path,
        profile: Record,
        *,
        created_at: str,
    ) -> AssociationProfileResult:
        self._ensure_directory()
        now = self._clock().isoformat()
        stored = copy.deepcopy(profile)
        stored["created_at"] = created_at or now
        stored["updated_at"] = now

        temporary = path.with_suffix(path.suffix + ".tmp")
        try:
            temporary.write_text(
                json.dumps(stored, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            temporary.replace(path)
        except OSError:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            return AssociationProfileResult("PROFILE_SAVE_FAILED")

        result = copy.deepcopy(stored)
        result["protected"] = result["id"] in self._protected_ids
        return AssociationProfileResult(
            "OK",
            {
                "profile": result,
                "created": not bool(created_at),
            },
        )

    def _validated_requested_id(self, value: str) -> str:
        supplied = str(value or "").strip()
        normalized = self.normalize_profile_id(supplied)
        if supplied != normalized:
            return ""
        if not self.PROFILE_ID_PATTERN.fullmatch(normalized):
            return ""
        return normalized

    def _profile_path(self, profile_id: str) -> Path:
        return self._profile_directory / f"{profile_id}.json"

    def _ensure_directory(self) -> None:
        self._profile_directory.mkdir(parents=True, exist_ok=True)
