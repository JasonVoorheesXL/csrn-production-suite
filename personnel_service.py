from __future__ import annotations

import copy
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse


Personnel = dict[str, Any]
PersonnelLoader = Callable[[], list[Personnel]]
PersonnelSaver = Callable[[list[Personnel]], None]
Clock = Callable[[], float]


PERSONNEL_CATEGORIES = (
    "Coach",
    "Broadcast Talent",
    "Administrator",
    "Official",
    "Interview Guest",
    "Production Staff",
    "Other",
)

STAFF_ROLES = (
    "Head Coach",
    "Assistant Coach",
    "Offensive Coordinator",
    "Defensive Coordinator",
    "Special Teams Coordinator",
    "Play-by-Play",
    "Color Analyst",
    "Sideline Reporter",
    "Statistician",
    "Studio Host",
    "Athletic Director",
    "Principal",
    "Superintendent",
    "Official",
    "Interview Guest",
    "Camera Operator",
    "Technical Director",
    "Audio Engineer",
    "Graphics Operator",
    "Producer",
    "Other",
)

SOCIAL_PLATFORMS = (
    "facebook",
    "x",
    "instagram",
    "youtube",
    "website",
)

BROADCAST_TALENT_ROLES = {
    "Play-by-Play",
    "Color Analyst",
    "Sideline Reporter",
    "Studio Host",
    "Statistician",
}


@dataclass(frozen=True)
class PersonnelResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.code == "OK"


class PersonnelService:
    """Personnel-domain behavior independent of Flask and file storage."""

    def __init__(
        self,
        *,
        load_personnel: PersonnelLoader,
        save_personnel: PersonnelSaver,
        clock: Clock | None = None,
    ) -> None:
        self._load_personnel = load_personnel
        self._save_personnel = save_personnel
        self._clock = clock or time.time

    @staticmethod
    def normalize_id(value: Any) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9]+", "-", str(value or "").strip())
        return cleaned.strip("-").lower() or "staff-member"

    @staticmethod
    def normalize_headshot_url(value: Any) -> str:
        raw = str(value or "").strip().replace("\\", "/")
        if not raw:
            return ""
        filename = Path(raw).name
        if raw.startswith("/data/Personnel/Headshots/") or raw.startswith(
            "data/Personnel/Headshots/"
        ):
            return f"/personnel-headshots/{filename}"
        return raw

    @staticmethod
    def _boolean(value: Any, default: bool = False) -> bool:
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}

    @classmethod
    def normalize_social_url(
        cls,
        platform: str,
        value: Any,
    ) -> tuple[str, bool, str]:
        key = str(platform or "").strip().lower()
        text = str(value or "").strip()
        if not text:
            return "", True, ""
        if text.startswith("@"):
            text = text[1:]
        if "://" not in text and "/" not in text:
            domains = {
                "facebook": "https://facebook.com/",
                "x": "https://x.com/",
                "instagram": "https://instagram.com/",
                "youtube": "https://youtube.com/@",
            }
            if key in domains:
                text = domains[key] + text
            elif key == "website":
                text = "https://" + text
        elif "://" not in text:
            text = "https://" + text

        try:
            hostname = (urlparse(text).hostname or "").lower()
        except ValueError:
            hostname = ""

        valid_domains = {
            "facebook": ("facebook.com", "www.facebook.com"),
            "x": ("x.com", "twitter.com", "www.x.com", "www.twitter.com"),
            "instagram": ("instagram.com", "www.instagram.com"),
            "youtube": ("youtube.com", "www.youtube.com", "youtu.be"),
        }
        if key == "website":
            valid = bool(hostname) and text.lower().startswith(("http://", "https://"))
        else:
            valid = any(
                hostname == domain or hostname.endswith(f".{domain}")
                for domain in valid_domains.get(key, ())
            )
        return text, valid, "" if valid else f"Expected a valid {key} URL"

    @classmethod
    def normalize_social_block(
        cls,
        block: Any,
    ) -> tuple[dict[str, str], dict[str, str]]:
        source = block if isinstance(block, dict) else {}
        normalized: dict[str, str] = {}
        errors: dict[str, str] = {}
        for platform in SOCIAL_PLATFORMS:
            value, valid, message = cls.normalize_social_url(
                platform,
                source.get(platform, ""),
            )
            normalized[platform] = value
            if not valid:
                errors[platform] = message
        return normalized, errors

    @classmethod
    def migrate_record(cls, item: Personnel) -> Personnel:
        source = copy.deepcopy(item if isinstance(item, dict) else {})
        full_name = str(source.get("full_name") or source.get("name") or "").strip()
        role = str(source.get("role") or source.get("primary_role") or "Other")
        if role not in STAFF_ROLES:
            role = "Other"
        category = str(
            source.get("category")
            or (
                "Broadcast Talent"
                if role in BROADCAST_TALENT_ROLES
                else "Production Staff"
            )
        )
        if category not in PERSONNEL_CATEGORIES:
            category = "Other"
        social, _errors = cls.normalize_social_block(source.get("social") or {})
        status = (
            "inactive"
            if str(source.get("status", "active")).strip().lower() == "inactive"
            else "active"
        )
        return {
            "id": str(source.get("id") or cls.normalize_id(full_name or "personnel-member")),
            "full_name": full_name,
            "name": full_name,
            "preferred_name": str(source.get("preferred_name", "")).strip(),
            "pronunciation": str(source.get("pronunciation", "")).strip(),
            "pronunciation_verified": cls._boolean(
                source.get("pronunciation_verified"),
                False,
            ),
            "category": category,
            "role": role,
            "primary_role": role,
            "title": str(source.get("title") or role).strip(),
            "organization": str(source.get("organization", "")).strip(),
            "school_id": str(source.get("school_id", "")).strip(),
            "bio": str(source.get("bio", "")).strip(),
            "headshot": cls.normalize_headshot_url(source.get("headshot", "")),
            "status": status,
            "producer": cls._boolean(source.get("producer"), False),
            "social": social,
            **(
                {"created_at": int(source["created_at"])}
                if source.get("created_at") not in (None, "")
                else {}
            ),
            **(
                {"updated_at": int(source["updated_at"])}
                if source.get("updated_at") not in (None, "")
                else {}
            ),
        }

    def _records(self) -> list[Personnel]:
        source = self._load_personnel()
        records = [self.migrate_record(item) for item in source if isinstance(item, dict)]
        if records != source:
            self._save_personnel(records)
        return records

    @staticmethod
    def _find(records: list[Personnel], personnel_id: str) -> Personnel | None:
        target = str(personnel_id or "").strip()
        return next(
            (
                record
                for record in records
                if str(record.get("id", "")).strip() == target
            ),
            None,
        )

    def list_records(
        self,
        *,
        include_inactive: bool = True,
        category: str = "",
        role: str = "",
        school_id: str = "",
    ) -> PersonnelResult:
        category_key = str(category or "").strip().casefold()
        role_key = str(role or "").strip().casefold()
        school_key = str(school_id or "").strip()
        records: list[Personnel] = []
        for record in self._records():
            if not include_inactive and record.get("status") == "inactive":
                continue
            if category_key and str(record.get("category", "")).casefold() != category_key:
                continue
            if role_key and str(record.get("role", "")).casefold() != role_key:
                continue
            if school_key and str(record.get("school_id", "")) != school_key:
                continue
            records.append(copy.deepcopy(record))
        records.sort(
            key=lambda record: (
                str(record.get("full_name", "")).casefold(),
                str(record.get("id", "")),
            )
        )
        return PersonnelResult("OK", {"personnel": records})

    def read(self, personnel_id: str) -> PersonnelResult:
        record = self._find(self._records(), personnel_id)
        if record is None:
            return PersonnelResult("BROADCASTER_NOT_FOUND")
        return PersonnelResult("OK", {"personnel": copy.deepcopy(record)})

    def _record(
        self,
        incoming: Personnel,
        *,
        existing: Personnel | None = None,
        personnel_id: str | None = None,
    ) -> PersonnelResult:
        source = copy.deepcopy(existing or {})
        source.update(copy.deepcopy(incoming or {}))
        name = str(source.get("full_name") or source.get("name") or "").strip()
        if not name:
            return PersonnelResult("STAFF_NAME_REQUIRED")

        role = str(source.get("role") or source.get("primary_role") or "Other")
        if role not in STAFF_ROLES:
            return PersonnelResult("INVALID_STAFF_ROLE")

        social, errors = self.normalize_social_block(source.get("social") or {})
        if errors:
            return PersonnelResult("INVALID_SOCIAL_URL", {"fields": errors})

        now = int(self._clock())
        category = str(source.get("category", "Other") or "Other")
        if category not in PERSONNEL_CATEGORIES:
            category = "Other"
        status = (
            "inactive"
            if str(source.get("status", "active")).strip().lower() == "inactive"
            else "active"
        )
        record = {
            "id": str(personnel_id or source.get("id") or self.normalize_id(name)),
            "full_name": name,
            "name": name,
            "preferred_name": str(source.get("preferred_name", "")).strip(),
            "pronunciation": str(source.get("pronunciation", "")).strip(),
            "pronunciation_verified": self._boolean(
                source.get("pronunciation_verified"),
                False,
            ),
            "category": category,
            "role": role,
            "primary_role": role,
            "title": str(source.get("title") or role).strip(),
            "organization": str(source.get("organization", "")).strip(),
            "school_id": str(source.get("school_id", "")).strip(),
            "bio": str(source.get("bio", "")).strip(),
            "headshot": self.normalize_headshot_url(source.get("headshot", "")),
            "status": status,
            "producer": self._boolean(source.get("producer"), False),
            "social": social,
            "created_at": int(source.get("created_at", now) or now),
            "updated_at": now,
        }
        return PersonnelResult("OK", {"personnel": record})

    def create(self, incoming: Personnel) -> PersonnelResult:
        result = self._record(incoming)
        if not result.ok:
            return result
        record = result.data["personnel"]
        records = self._records()
        base_id = self.normalize_id(record["id"])
        candidate = base_id
        suffix = 2
        while self._find(records, candidate) is not None:
            candidate = f"{base_id}-{suffix}"
            suffix += 1
        record["id"] = candidate
        records.append(record)
        self._save_personnel(records)
        return PersonnelResult("OK", {"personnel": copy.deepcopy(record)})

    def update(self, personnel_id: str, incoming: Personnel) -> PersonnelResult:
        records = self._records()
        current = self._find(records, personnel_id)
        if current is None:
            return PersonnelResult("BROADCASTER_NOT_FOUND")
        result = self._record(
            incoming,
            existing=current,
            personnel_id=str(personnel_id),
        )
        if not result.ok:
            return result
        replacement = result.data["personnel"]
        for index, record in enumerate(records):
            if str(record.get("id", "")) == str(personnel_id):
                records[index] = replacement
                break
        self._save_personnel(records)
        return PersonnelResult("OK", {"personnel": copy.deepcopy(replacement)})

    def delete(self, personnel_id: str) -> PersonnelResult:
        records = self._records()
        if self._find(records, personnel_id) is None:
            return PersonnelResult("BROADCASTER_NOT_FOUND")
        remaining = [
            record
            for record in records
            if str(record.get("id", "")) != str(personnel_id)
        ]
        self._save_personnel(remaining)
        return PersonnelResult("OK", {"ok": True, "deleted": str(personnel_id)})

    def attach_headshot(self, personnel_id: str, headshot_url: str) -> PersonnelResult:
        records = self._records()
        record = self._find(records, personnel_id)
        if record is None:
            return PersonnelResult("PERSONNEL_NOT_FOUND")
        record["headshot"] = self.normalize_headshot_url(headshot_url)
        record["updated_at"] = int(self._clock())
        self._save_personnel(records)
        return PersonnelResult(
            "OK",
            {
                "personnel": copy.deepcopy(record),
                "path": record["headshot"],
            },
        )

    def validate_social(self, platform: str, value: Any) -> PersonnelResult:
        normalized, valid, message = self.normalize_social_url(platform, value)
        return PersonnelResult(
            "OK",
            {
                "normalized": normalized,
                "valid": valid,
                "message": message,
            },
        )
