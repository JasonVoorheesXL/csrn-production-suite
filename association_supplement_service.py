from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable


Record = dict[str, Any]
RecordLoader = Callable[[], list[Record]]
RecordSaver = Callable[[list[Record]], None]


@dataclass(frozen=True)
class AssociationSupplementResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.code == "OK"


class AssociationSupplementService:
    """Apply normalized association enrichment and branding data."""

    def __init__(
        self,
        *,
        load_schools: RecordLoader,
        save_schools: RecordSaver,
        load_venues: RecordLoader,
        save_venues: RecordSaver,
    ) -> None:
        self._load_schools = load_schools
        self._save_schools = save_schools
        self._load_venues = load_venues
        self._save_venues = save_venues

    @staticmethod
    def _exact_school(
        candidate: Record,
        schools: list[Record],
    ) -> Record | None:
        official_name = str(candidate.get("official_name", "")).strip().casefold()
        if not official_name:
            return None
        return next(
            (
                school
                for school in schools
                if str(school.get("official_name", "")).strip().casefold()
                == official_name
            ),
            None,
        )

    def analyze_branding(
        self,
        rows: Iterable[Record],
        *,
        source: Record | None = None,
    ) -> AssociationSupplementResult:
        schools = self._load_schools()
        results: list[Record] = []

        for candidate in rows:
            if not isinstance(candidate, dict):
                continue
            school = self._exact_school(candidate, schools)
            if school is None:
                status = "school_missing"
            elif school.get("primary_logo") or str(
                school.get("branding_status", "")
            ).lower() in {"approved", "manual"}:
                status = "preserved"
            else:
                status = "ready"

            results.append(
                {
                    **copy.deepcopy(candidate),
                    "status": status,
                    "school_id": school.get("id", "") if school else "",
                }
            )

        return AssociationSupplementResult(
            "OK",
            {
                "found": len(results),
                "ready": sum(item["status"] == "ready" for item in results),
                "preserved": sum(
                    item["status"] == "preserved" for item in results
                ),
                "school_missing": sum(
                    item["status"] == "school_missing" for item in results
                ),
                "schools": results,
                "source": copy.deepcopy(source or {}),
            },
        )

    def apply_branding(
        self,
        rows: Iterable[Record],
        *,
        source: Record | None = None,
    ) -> AssociationSupplementResult:
        source = copy.deepcopy(source or {})
        schools = self._load_schools()
        updated = 0
        preserved = 0
        missing: list[str] = []

        for candidate in rows:
            if not isinstance(candidate, dict):
                continue
            school = self._exact_school(candidate, schools)
            if school is None:
                missing.append(str(candidate.get("official_name", "")))
                continue

            if school.get("primary_logo") or str(
                school.get("branding_status", "")
            ).lower() in {"approved", "manual"}:
                preserved += 1
                continue

            school["primary_color"] = candidate.get(
                "primary_color",
                school.get("primary_color", "#808080"),
            )
            school["secondary_color"] = candidate.get(
                "secondary_color",
                school.get("secondary_color", "#FFFFFF"),
            )
            school["accent_color"] = candidate.get("accent_color", "")
            school["branding_status"] = "candidate"
            school["branding_source"] = {
                "provider": candidate.get(
                    "source_provider",
                    source.get("provider", "Association research seed"),
                ),
                "source_url": candidate.get("source_url", ""),
                "checked_at": source.get("checked_at", ""),
                "verification_status": "candidate",
                "notes": candidate.get(
                    "notes",
                    "Candidate colors require visual approval.",
                ),
            }
            updated += 1

        self._save_schools(schools)
        return AssociationSupplementResult(
            "OK",
            {
                "updated": updated,
                "preserved": preserved,
                "missing_schools": missing,
            },
        )

    def analyze_enrichment(
        self,
        rows: Iterable[Record],
        *,
        source: Record | None = None,
        classification: str = "",
    ) -> AssociationSupplementResult:
        schools = self._load_schools()
        results: list[Record] = []

        for candidate in rows:
            if not isinstance(candidate, dict):
                continue
            school = self._exact_school(candidate, schools)
            missing: list[str] = []
            if school is None:
                status = "school_missing"
            else:
                status = "ready"
                for key in ("mascot", "phone", "website"):
                    if not candidate.get(key):
                        missing.append(key)
                address = candidate.get("school_address") or {}
                if not isinstance(address, dict) or not address.get("address1"):
                    missing.append("school_address")

            results.append(
                {
                    "official_name": candidate.get("official_name"),
                    "status": status,
                    "missing_source_fields": missing,
                }
            )

        return AssociationSupplementResult(
            "OK",
            {
                "classification": classification,
                "found": len(results),
                "ready": sum(item["status"] == "ready" for item in results),
                "school_missing": sum(
                    item["status"] == "school_missing" for item in results
                ),
                "source": copy.deepcopy(source or {}),
                "schools": results,
            },
        )

    def apply_enrichment(
        self,
        rows: Iterable[Record],
        *,
        source: Record | None = None,
        venue_sport: str = "Football",
    ) -> AssociationSupplementResult:
        source = copy.deepcopy(source or {})
        schools = self._load_schools()
        venues = self._load_venues()

        updated = 0
        missing_schools: list[str] = []
        missing_mascot = 0
        missing_address = 0
        missing_website = 0
        venue_verification_needed = 0
        logo_pending = 0

        for candidate in rows:
            if not isinstance(candidate, dict):
                continue
            school = self._exact_school(candidate, schools)
            if school is None:
                missing_schools.append(str(candidate.get("official_name", "")))
                continue

            overrides = school.get("user_overrides") or {}
            mascot = candidate.get("mascot", "")
            if mascot and not overrides.get("mascot"):
                school["mascot"] = mascot
                school["nickname"] = school.get("nickname") or mascot
            elif not mascot:
                missing_mascot += 1

            address = candidate.get("school_address") or {}
            if isinstance(address, dict) and address.get("address1"):
                school["school_address"] = copy.deepcopy(address)
                school["city"] = school.get("city") or address.get("city", "")
            else:
                missing_address += 1
                address = {}

            if candidate.get("phone") and not overrides.get("phone"):
                school["phone"] = candidate.get("phone")

            if candidate.get("website") and not overrides.get("website"):
                school["website"] = candidate.get("website")
                general_social = school.setdefault("general_social", {})
                general_social["website"] = (
                    general_social.get("website") or candidate.get("website")
                )
            elif not candidate.get("website"):
                missing_website += 1

            school.setdefault("source_data", {}).update(
                {
                    "provider": source.get(
                        "provider",
                        "Association School Directory",
                    ),
                    "directory_source_url": candidate.get(
                        "source_url",
                        source.get("url", ""),
                    ),
                    "directory_checked_at": source.get("checked_at", ""),
                }
            )
            school["verification_status"] = "candidate_enriched"
            school.setdefault("logo_metadata", {}).update(
                {
                    "source_url": candidate.get(
                        "source_url",
                        source.get("url", ""),
                    ),
                    "approval_status": "candidate",
                    "shape_standard": "round",
                    "master_canvas": "1024x1024-round",
                    "scorebug_derivative": "256x256-round",
                }
            )
            school["logo_status"] = school.get("logo_status") or "candidate"
            logo_pending += 1

            sport = str(venue_sport or "Football")
            venue_id = school.get("venue_id") or (
                f"{school.get('id')}-{sport.lower()}"
            )
            school["venue_id"] = venue_id

            venue_payload = {
                "id": venue_id,
                "school_id": school.get("id"),
                "csrn_school_id": school.get("csrn_id", ""),
                "sport": sport,
                "name": (
                    f"{school.get('broadcast_name') or candidate.get('official_name')} "
                    f"{sport} Stadium"
                ),
                **copy.deepcopy(address),
                "latitude": None,
                "longitude": None,
                "on_campus_assumed": True,
                "venue_address_source": "school_address",
                "venue_verified": False,
                "approval_status": "candidate",
                "broadcast_notes": (
                    "Defaulted to school address; verify whether the stadium "
                    "is off campus."
                ),
            }
            venue = next(
                (
                    item
                    for item in venues
                    if item.get("id") == venue_id
                    or item.get("school_id") == school.get("id")
                ),
                None,
            )
            if venue is not None:
                venue.update(
                    {
                        key: value
                        for key, value in venue_payload.items()
                        if key != "broadcast_notes" or not venue.get(key)
                    }
                )
            else:
                venues.append(venue_payload)

            school_venues = school.get("venues") or []
            school["venues"] = [
                venue_payload if item.get("id") == venue_id else item
                for item in school_venues
            ] or [venue_payload]
            school.setdefault("programs", {}).setdefault(sport, {})[
                "venue_id"
            ] = venue_id

            venue_verification_needed += 1
            updated += 1

        self._save_schools(schools)
        self._save_venues(venues)
        return AssociationSupplementResult(
            "OK",
            {
                "updated": updated,
                "missing_schools": missing_schools,
                "missing_mascot": missing_mascot,
                "missing_address": missing_address,
                "missing_website": missing_website,
                "logo_pending_approval": logo_pending,
                "venue_verification_needed": venue_verification_needed,
            },
        )
