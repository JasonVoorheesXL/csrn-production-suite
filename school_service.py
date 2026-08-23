from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Callable
from urllib.parse import urlparse


School = dict[str, Any]
SchoolLoader = Callable[[], list[School]]
SchoolSaver = Callable[[list[School]], None]
LogoLoader = Callable[[], list[dict[str, Any]]]
LogoSaver = Callable[[list[dict[str, Any]]], None]


@dataclass(frozen=True)
class SchoolResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.code == "OK"


class SchoolService:
    """School-domain behavior independent of Flask routes."""

    UPDATE_FIELDS = (
        "official_name",
        "broadcast_name",
        "nickname",
        "mascot",
        "short_name",
        "city",
        "county",
        "active",
        "school_address",
        "phone",
        "website",
        "preferred_scorebug_name",
        "pronunciation_guide",
        "venue_id",
        "csrn_id",
        "primary_color",
        "secondary_color",
        "primary_logo",
        "alternate_logo",
        "general_social",
        "venues",
        "programs",
        "state",
        "classification",
        "region",
        "district",
        "mhsaa_id",
        "source_data",
        "user_overrides",
        "verification_status",
        "default_broadcast_logo_id",
        "logo_status",
        "logo_metadata",
        "notes",
    )

    def __init__(
        self,
        *,
        load_schools: SchoolLoader,
        save_schools: SchoolSaver,
        load_logos: LogoLoader,
        save_logos: LogoSaver,
    ) -> None:
        self._load_schools = load_schools
        self._save_schools = save_schools
        self._load_logos = load_logos
        self._save_logos = save_logos

    @staticmethod
    def normalize_school_id(value: str) -> str:
        cleaned = "".join(
            character.lower() if character.isalnum() else "-"
            for character in value.strip()
        )
        while "--" in cleaned:
            cleaned = cleaned.replace("--", "-")
        return cleaned.strip("-") or "school"

    @staticmethod
    def next_csrn_school_id(
        state: str,
        classification: str,
        schools: list[School],
    ) -> str:
        state_code = (state or "MS").strip().upper()
        class_code = (
            str(classification or "")
            .strip()
            .upper()
            .replace("CLASS", "")
            .strip()
        )
        prefix = (
            f"{state_code}{class_code}-"
            if class_code
            else f"{state_code}-"
        )
        used: set[int] = set()
        for school in schools:
            value = str(school.get("csrn_id", "")).upper()
            if value.startswith(prefix):
                try:
                    used.add(int(value.rsplit("-", 1)[1]))
                except (ValueError, IndexError):
                    pass

        number = 1
        while number in used:
            number += 1
        return f"{prefix}{number:03d}"

    @staticmethod
    def normalize_social_url(
        platform: str,
        value: str,
    ) -> tuple[str, bool, str]:
        value = (value or "").strip()
        if not value:
            return "", True, ""
        if value.startswith("@"):
            value = value[1:]

        if "://" not in value and "/" not in value:
            domains = {
                "facebook": "https://facebook.com/",
                "x": "https://x.com/",
                "instagram": "https://instagram.com/",
                "youtube": "https://youtube.com/@",
            }
            if platform in domains:
                value = domains[platform] + value
            elif platform == "website":
                value = "https://" + value
        elif "://" not in value:
            value = "https://" + value

        try:
            hostname = (urlparse(value).hostname or "").lower()
        except ValueError:
            hostname = ""

        valid_domains = {
            "facebook": ("facebook.com", "www.facebook.com"),
            "x": (
                "x.com",
                "twitter.com",
                "www.x.com",
                "www.twitter.com",
            ),
            "instagram": ("instagram.com", "www.instagram.com"),
            "youtube": (
                "youtube.com",
                "www.youtube.com",
                "youtu.be",
            ),
        }
        if platform == "website":
            valid = bool(hostname) and value.lower().startswith(
                ("http://", "https://")
            )
        else:
            valid = any(
                hostname == domain or hostname.endswith(f".{domain}")
                for domain in valid_domains.get(platform, ())
            )
        return (
            value,
            valid,
            "" if valid else f"Expected a valid {platform} URL",
        )

    @classmethod
    def normalize_social_block(
        cls,
        block: dict[str, Any],
    ) -> tuple[dict[str, str], dict[str, str]]:
        normalized: dict[str, str] = {}
        errors: dict[str, str] = {}
        for platform in (
            "facebook",
            "x",
            "instagram",
            "youtube",
            "website",
        ):
            value, valid, message = cls.normalize_social_url(
                platform,
                str(block.get(platform, "")),
            )
            normalized[platform] = value
            if not valid:
                errors[platform] = message
        return normalized, errors

    @staticmethod
    def display_payload(school: School) -> School:
        mascot = school.get("mascot") or school.get("nickname", "")
        return {
            "id": school.get("id", ""),
            "official_name": school.get("official_name", ""),
            "broadcast_name": school.get("broadcast_name", ""),
            "mascot": mascot,
            "nickname": mascot,
            "primary_color": school.get("primary_color", "#C9203B"),
            "secondary_color": school.get("secondary_color", "#FFFFFF"),
            "primary_logo": school.get("primary_logo", ""),
            "alternate_logo": school.get("alternate_logo", ""),
            "verification_status": school.get(
                "verification_status",
                "unverified",
            ),
            "csrn_id": school.get("csrn_id", ""),
            "classification": school.get("classification", ""),
            "region": school.get("region", ""),
            "city": school.get("city", ""),
            "active": school.get("active", True),
        }

    def _duplicate_candidates(
        self,
        incoming: School,
        schools: list[School],
        exclude_id: str = "",
    ) -> list[School]:
        official = str(incoming.get("official_name", "")).strip().casefold()
        broadcast = str(incoming.get("broadcast_name", "")).strip().casefold()
        city = str(
            incoming.get("city", "")
            or incoming.get("user_overrides", {}).get("city", "")
        ).strip().casefold()
        district = str(
            incoming.get("district", "")
            or incoming.get("source_data", {}).get("district", "")
        ).strip().casefold()

        matches: list[School] = []
        for school in schools:
            if school.get("id") == exclude_id:
                continue
            names = {
                str(school.get("official_name", "")).casefold(),
                str(school.get("broadcast_name", "")).casefold(),
            }
            score = 0
            if official and official in names:
                score += 3
            if broadcast and broadcast in names:
                score += 2

            school_city = str(
                school.get("city", "")
                or school.get("user_overrides", {}).get("city", "")
            ).casefold()
            school_district = str(
                school.get("district", "")
                or school.get("source_data", {}).get("district", "")
            ).casefold()
            if city and school_city and city == school_city:
                score += 1
            if district and school_district and district == school_district:
                score += 1
            if score >= 3:
                matches.append(
                    {
                        "id": school.get("id"),
                        "official_name": school.get("official_name"),
                        "broadcast_name": school.get("broadcast_name"),
                        "score": score,
                    }
                )
        return matches

    def duplicate_candidates(
        self,
        incoming: School,
        exclude_id: str = "",
    ) -> list[School]:
        return self._duplicate_candidates(
            incoming,
            self._load_schools(),
            exclude_id,
        )

    def list_schools(self) -> list[School]:
        return [
            self.display_payload(school)
            for school in self._load_schools()
        ]

    def read(self, school_id: str) -> SchoolResult:
        school = next(
            (
                school
                for school in self._load_schools()
                if school.get("id") == school_id
            ),
            None,
        )
        if school is None:
            return SchoolResult("SCHOOL_NOT_FOUND")
        return SchoolResult("OK", {"school": school})

    def create(self, incoming: School) -> SchoolResult:
        incoming = copy.deepcopy(incoming)
        official_name = str(incoming.get("official_name", "")).strip()
        broadcast_name = str(incoming.get("broadcast_name", "")).strip()
        if not official_name or not broadcast_name:
            return SchoolResult("SCHOOL_NAME_REQUIRED")

        schools = self._load_schools()
        duplicates = self._duplicate_candidates(incoming, schools)
        if duplicates and not bool(incoming.get("confirm_duplicate", False)):
            return SchoolResult(
                "LIKELY_DUPLICATE",
                {"matches": duplicates},
            )

        general_social, social_errors = self.normalize_social_block(
            incoming.get("general_social") or {}
        )
        if social_errors:
            return SchoolResult(
                "INVALID_SOCIAL_URL",
                {"fields": social_errors},
            )

        programs = copy.deepcopy(incoming.get("programs") or {})
        if "Football" in programs:
            football_social, football_errors = self.normalize_social_block(
                programs.get("Football") or {}
            )
            if football_errors:
                return SchoolResult(
                    "INVALID_SOCIAL_URL",
                    {"fields": football_errors},
                )
            programs["Football"].update(football_social)

        school_id = self.normalize_school_id(
            str(incoming.get("id") or broadcast_name)
        )
        base_id = school_id
        suffix = 2
        while any(school.get("id") == school_id for school in schools):
            school_id = f"{base_id}-{suffix}"
            suffix += 1

        state = str(incoming.get("state", "MS")).strip() or "MS"
        classification = str(incoming.get("classification", "")).strip()
        school = {
            "id": school_id,
            "csrn_id": str(incoming.get("csrn_id", "")).strip()
            or self.next_csrn_school_id(state, classification, schools),
            "official_name": official_name,
            "broadcast_name": broadcast_name,
            "nickname": str(incoming.get("nickname", "")).strip(),
            "short_name": str(
                incoming.get("short_name", broadcast_name)
            ).strip(),
            "city": str(incoming.get("city", "")).strip(),
            "county": str(incoming.get("county", "")).strip(),
            "active": bool(incoming.get("active", True)),
            "preferred_scorebug_name": str(
                incoming.get("preferred_scorebug_name", broadcast_name)
            ).strip(),
            "pronunciation_guide": str(
                incoming.get("pronunciation_guide", "")
            ).strip(),
            "venue_id": str(incoming.get("venue_id", "")).strip(),
            "primary_color": incoming.get("primary_color", "#C9203B"),
            "secondary_color": incoming.get("secondary_color", "#FFFFFF"),
            "primary_logo": str(incoming.get("primary_logo", "")).strip(),
            "alternate_logo": str(
                incoming.get("alternate_logo", "")
            ).strip(),
            "general_social": general_social,
            "venues": copy.deepcopy(incoming.get("venues") or []),
            "programs": programs,
            "state": state,
            "classification": classification,
            "region": str(incoming.get("region", "")).strip(),
            "district": str(incoming.get("district", "")).strip(),
            "mhsaa_id": str(incoming.get("mhsaa_id", "")).strip(),
            "source_data": copy.deepcopy(
                incoming.get("source_data")
                or {
                    "provider": "Manual",
                    "source_url": "",
                    "retrieved_at": "",
                    "district": "",
                }
            ),
            "user_overrides": copy.deepcopy(
                incoming.get("user_overrides") or {}
            ),
            "verification_status": str(
                incoming.get("verification_status", "unverified")
            ),
            "default_broadcast_logo_id": str(
                incoming.get("default_broadcast_logo_id", "")
            ).strip(),
            "logo_status": str(incoming.get("logo_status", "candidate")),
            "logo_metadata": copy.deepcopy(
                incoming.get("logo_metadata")
                or {
                    "source_url": "",
                    "transparent_background_status": "unknown",
                    "approval_status": "candidate",
                    "shape_standard": "round",
                    "master_canvas": "1024x1024-round",
                    "safe_area": "circle-90-percent",
                    "scorebug_derivative": "256x256-round",
                }
            ),
            "notes": str(incoming.get("notes", "")).strip(),
        }
        schools.append(school)
        self._save_schools(schools)
        return SchoolResult("OK", {"school": school})

    def update(self, school_id: str, incoming: School) -> SchoolResult:
        incoming = copy.deepcopy(incoming)
        schools = self._load_schools()
        index = next(
            (
                offset
                for offset, school in enumerate(schools)
                if school.get("id") == school_id
            ),
            None,
        )
        if index is None:
            return SchoolResult("SCHOOL_NOT_FOUND")

        if "general_social" in incoming:
            normalized_social, social_errors = self.normalize_social_block(
                incoming.get("general_social") or {}
            )
            if social_errors:
                return SchoolResult(
                    "INVALID_SOCIAL_URL",
                    {"fields": social_errors},
                )
            incoming["general_social"] = normalized_social

        if (
            "programs" in incoming
            and "Football" in incoming["programs"]
        ):
            normalized_football, football_errors = self.normalize_social_block(
                incoming["programs"].get("Football") or {}
            )
            if football_errors:
                return SchoolResult(
                    "INVALID_SOCIAL_URL",
                    {"fields": football_errors},
                )
            incoming["programs"]["Football"].update(normalized_football)

        school = schools[index]
        for key in self.UPDATE_FIELDS:
            if key in incoming:
                school[key] = incoming[key]

        schools[index] = school
        self._save_schools(schools)

        linked_logo_id = str(
            school.get("default_broadcast_logo_id", "") or ""
        ).strip()
        if linked_logo_id:
            logos = self._load_logos()
            linked = next(
                (
                    row
                    for row in logos
                    if str(row.get("id", "")) == linked_logo_id
                ),
                None,
            )
            if linked is not None:
                linked["approval_status"] = str(
                    school.get(
                        "logo_status",
                        linked.get("approval_status", "candidate"),
                    )
                )
                if school.get("primary_logo"):
                    linked["round_master_path"] = school.get("primary_logo")
                self._save_logos(logos)

        return SchoolResult("OK", {"school": school})

    def delete(self, school_id: str) -> SchoolResult:
        schools = self._load_schools()
        school = next(
            (
                school
                for school in schools
                if school.get("id") == school_id
            ),
            None,
        )
        if school is None:
            return SchoolResult("SCHOOL_NOT_FOUND")

        self._save_schools(
            [school for school in schools if school.get("id") != school_id]
        )
        return SchoolResult("OK", {"ok": True})
