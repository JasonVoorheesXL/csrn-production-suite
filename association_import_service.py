from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Iterable

from school_service import SchoolService


Record = dict[str, Any]
RecordLoader = Callable[[], list[Record]]
RecordSaver = Callable[[list[Record]], None]
Clock = Callable[[], datetime]

SUPPORTED_SOURCE_TYPES = {
    "manifest",
    "json",
    "csv",
    "html_table",
}

IMPORTABLE_FIELDS = {
    "official_name",
    "broadcast_name",
    "short_name",
    "preferred_scorebug_name",
    "mascot",
    "nickname",
    "city",
    "county",
    "state",
    "classification",
    "region",
    "district",
    "phone",
    "website",
    "school_address",
    "primary_color",
    "secondary_color",
    "accent_color",
    "source_data",
}


@dataclass(frozen=True)
class AssociationImportResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.code == "OK"


@dataclass(frozen=True)
class AssociationProfile:
    profile_id: str
    name: str
    association: str
    state: str
    source_type: str
    source_url: str
    field_mapping: dict[str, str]
    defaults: dict[str, Any]
    options: dict[str, Any]

    @classmethod
    def from_dict(cls, data: Record) -> AssociationProfile:
        profile_id = str(data.get("id", "")).strip()
        name = str(data.get("name", "")).strip()
        association = str(data.get("association", "")).strip()
        state = str(data.get("state", "")).strip().upper()
        source_type = str(data.get("source_type", "")).strip().lower()
        source_url = str(data.get("source_url", "")).strip()
        field_mapping = copy.deepcopy(data.get("field_mapping") or {})
        defaults = copy.deepcopy(data.get("defaults") or {})
        options = copy.deepcopy(data.get("options") or {})

        if not profile_id:
            raise ValueError("PROFILE_ID_REQUIRED")
        if not name:
            raise ValueError("PROFILE_NAME_REQUIRED")
        if not association:
            raise ValueError("ASSOCIATION_REQUIRED")
        if len(state) != 2 or not state.isalpha():
            raise ValueError("STATE_CODE_REQUIRED")
        if source_type not in SUPPORTED_SOURCE_TYPES:
            raise ValueError("UNSUPPORTED_SOURCE_TYPE")
        if not isinstance(field_mapping, dict) or not field_mapping:
            raise ValueError("FIELD_MAPPING_REQUIRED")

        mapped_targets = {str(value).strip() for value in field_mapping.values()}
        if "official_name" not in mapped_targets:
            raise ValueError("OFFICIAL_NAME_MAPPING_REQUIRED")
        invalid_targets = mapped_targets - IMPORTABLE_FIELDS
        if invalid_targets:
            raise ValueError("UNSUPPORTED_TARGET_FIELD")

        return cls(
            profile_id=profile_id,
            name=name,
            association=association,
            state=state,
            source_type=source_type,
            source_url=source_url,
            field_mapping={
                str(source).strip(): str(target).strip()
                for source, target in field_mapping.items()
                if str(source).strip() and str(target).strip()
            },
            defaults=defaults,
            options=options,
        )


class AssociationImportService:
    """Association-neutral school import analysis and application."""

    def __init__(
        self,
        *,
        school_service: SchoolService,
        load_schools: RecordLoader,
        load_venues: RecordLoader,
        save_venues: RecordSaver,
        clock: Clock | None = None,
    ) -> None:
        self.school_service = school_service
        self._load_schools = load_schools
        self._load_venues = load_venues
        self._save_venues = save_venues
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    @staticmethod
    def _nested_value(record: Record, path: str) -> Any:
        value: Any = record
        for segment in path.split("."):
            if not isinstance(value, dict):
                return None
            value = value.get(segment)
        return value

    def load_profile(self, data: Record) -> AssociationImportResult:
        try:
            profile = AssociationProfile.from_dict(data)
        except ValueError as exc:
            return AssociationImportResult(str(exc))
        return AssociationImportResult("OK", {"profile": profile})

    def normalize_row(
        self,
        profile: AssociationProfile,
        row: Record,
    ) -> Record:
        normalized = copy.deepcopy(profile.defaults)
        for source_field, target_field in profile.field_mapping.items():
            value = self._nested_value(row, source_field)
            if value is not None:
                normalized[target_field] = copy.deepcopy(value)

        normalized["official_name"] = str(
            normalized.get("official_name", "")
        ).strip()
        normalized["broadcast_name"] = str(
            normalized.get("broadcast_name")
            or normalized.get("official_name", "")
        ).strip()
        normalized["state"] = str(
            normalized.get("state") or profile.state
        ).strip().upper()

        for field_name in (
            "short_name",
            "preferred_scorebug_name",
        ):
            if not str(normalized.get(field_name, "")).strip():
                normalized[field_name] = normalized["broadcast_name"]

        source_data = copy.deepcopy(normalized.get("source_data") or {})
        source_data.update(
            {
                "association": profile.association,
                "association_profile_id": profile.profile_id,
                "provider": source_data.get("provider")
                or profile.association,
                "source_url": source_data.get("source_url")
                or profile.source_url,
                "retrieved_at": self._clock().date().isoformat(),
            }
        )
        normalized["source_data"] = source_data
        return normalized

    @staticmethod
    def _exact_school(
        candidate: Record,
        schools: list[Record],
    ) -> Record | None:
        official_name = str(candidate.get("official_name", "")).casefold()
        if not official_name:
            return None
        return next(
            (
                school
                for school in schools
                if str(school.get("official_name", "")).casefold()
                == official_name
            ),
            None,
        )

    def analyze(
        self,
        profile_data: Record,
        rows: Iterable[Record],
    ) -> AssociationImportResult:
        profile_result = self.load_profile(profile_data)
        if not profile_result.ok:
            return profile_result
        profile: AssociationProfile = profile_result.data["profile"]

        schools = self._load_schools()
        results: list[Record] = []
        for source_row in rows:
            if not isinstance(source_row, dict):
                continue
            candidate = self.normalize_row(profile, source_row)
            if not candidate.get("official_name"):
                results.append(
                    {
                        "status": "invalid",
                        "reason": "OFFICIAL_NAME_REQUIRED",
                        "candidate": candidate,
                        "matches": [],
                    }
                )
                continue

            exact = self._exact_school(candidate, schools)
            matches = self.school_service.duplicate_candidates(candidate)
            status = (
                "existing"
                if exact is not None
                else ("possible_duplicate" if matches else "new")
            )
            results.append(
                {
                    "status": status,
                    "candidate": candidate,
                    "matches": matches,
                    "school_id": exact.get("id", "") if exact else "",
                }
            )

        return AssociationImportResult(
            "OK",
            {
                "profile": self.profile_payload(profile),
                "found": len(results),
                "new": sum(item["status"] == "new" for item in results),
                "existing": sum(
                    item["status"] == "existing" for item in results
                ),
                "possible_duplicates": sum(
                    item["status"] == "possible_duplicate"
                    for item in results
                ),
                "invalid": sum(
                    item["status"] == "invalid" for item in results
                ),
                "schools": results,
            },
        )

    def apply(
        self,
        profile_data: Record,
        rows: Iterable[Record],
        *,
        create_venues: bool | None = None,
        allow_possible_duplicates: bool = False,
    ) -> AssociationImportResult:
        profile_result = self.load_profile(profile_data)
        if not profile_result.ok:
            return profile_result
        profile: AssociationProfile = profile_result.data["profile"]

        if create_venues is None:
            create_venues = bool(
                profile.options.get("create_venues", True)
            )

        imported = 0
        enriched_existing = 0
        skipped_existing = 0
        possible_duplicates: list[Record] = []
        invalid: list[Record] = []
        created_ids: list[str] = []

        for source_row in rows:
            if not isinstance(source_row, dict):
                continue
            candidate = self.normalize_row(profile, source_row)
            if not candidate.get("official_name"):
                invalid.append(
                    {
                        "reason": "OFFICIAL_NAME_REQUIRED",
                        "candidate": candidate,
                    }
                )
                continue

            schools = self._load_schools()
            existing = self._exact_school(candidate, schools)
            if existing is not None:
                update_fields = profile.options.get(
                    "update_existing_fields",
                    ["classification", "region", "district", "state"],
                )
                overrides = existing.get("user_overrides") or {}
                update_payload: Record = {}
                for field_name in update_fields:
                    if (
                        field_name in candidate
                        and not overrides.get(field_name)
                    ):
                        update_payload[field_name] = copy.deepcopy(
                            candidate[field_name]
                        )

                source_data = copy.deepcopy(existing.get("source_data") or {})
                source_data.update(candidate.get("source_data") or {})
                update_payload["source_data"] = source_data

                if update_payload:
                    result = self.school_service.update(
                        str(existing.get("id", "")),
                        update_payload,
                    )
                    if result.ok:
                        enriched_existing += 1
                    else:
                        skipped_existing += 1
                else:
                    skipped_existing += 1
                continue

            matches = self.school_service.duplicate_candidates(candidate)
            if matches and not allow_possible_duplicates:
                possible_duplicates.append(
                    {"candidate": candidate, "matches": matches}
                )
                continue

            payload = self._new_school_payload(
                profile,
                candidate,
                create_venues=create_venues,
            )
            payload["confirm_duplicate"] = allow_possible_duplicates
            result = self.school_service.create(payload)
            if not result.ok:
                if result.code == "LIKELY_DUPLICATE":
                    possible_duplicates.append(
                        {
                            "candidate": candidate,
                            "matches": result.data.get("matches", []),
                        }
                    )
                else:
                    invalid.append(
                        {"reason": result.code, "candidate": candidate}
                    )
                continue

            school = result.data["school"]
            imported += 1
            created_ids.append(str(school.get("csrn_id", "")))
            if create_venues:
                self._ensure_venue(profile, school)

        return AssociationImportResult(
            "OK",
            {
                "profile": self.profile_payload(profile),
                "imported": imported,
                "enriched_existing": enriched_existing,
                "skipped_existing": skipped_existing,
                "possible_duplicates": possible_duplicates,
                "invalid": invalid,
                "created_ids": created_ids,
                "total_schools": len(self._load_schools()),
            },
        )

    def _new_school_payload(
        self,
        profile: AssociationProfile,
        candidate: Record,
        *,
        create_venues: bool,
    ) -> Record:
        payload = copy.deepcopy(candidate)
        sport = str(profile.options.get("venue_sport", "Football"))
        venue_id = (
            f"{SchoolService.normalize_school_id(payload['broadcast_name'])}"
            f"-{sport.lower()}"
        )

        payload.setdefault("active", True)
        payload.setdefault("verification_status", "candidate")
        payload.setdefault("primary_color", "#808080")
        payload.setdefault("secondary_color", "#FFFFFF")
        payload.setdefault("primary_logo", "")
        payload.setdefault("alternate_logo", "")
        payload.setdefault("general_social", {})
        payload.setdefault("user_overrides", {})
        payload.setdefault(
            "notes",
            (
                f"Imported from {profile.association} as a candidate record; "
                "review identity, venue, colors, logo, and social fields."
            ),
        )

        if create_venues:
            venue_payload = self._venue_payload(
                profile,
                payload,
                venue_id,
            )
            payload["venue_id"] = venue_id
            payload["venues"] = [venue_payload]
            programs = copy.deepcopy(payload.get("programs") or {})
            programs.setdefault(sport, {})["venue_id"] = venue_id
            payload["programs"] = programs
        return payload

    def _ensure_venue(
        self,
        profile: AssociationProfile,
        school: Record,
    ) -> None:
        sport = str(profile.options.get("venue_sport", "Football"))
        venue_id = str(
            school.get("venue_id")
            or f"{school.get('id', 'school')}-{sport.lower()}"
        )
        venues = self._load_venues()
        if any(
            venue.get("id") == venue_id
            or venue.get("school_id") == school.get("id")
            for venue in venues
        ):
            return
        venues.append(self._venue_payload(profile, school, venue_id))
        self._save_venues(venues)

    @staticmethod
    def _venue_payload(
        profile: AssociationProfile,
        school: Record,
        venue_id: str,
    ) -> Record:
        sport = str(profile.options.get("venue_sport", "Football"))
        address = copy.deepcopy(school.get("school_address") or {})
        return {
            "id": venue_id,
            "school_id": school.get("id", ""),
            "csrn_school_id": school.get("csrn_id", ""),
            "sport": sport,
            "name": (
                f"{school.get('broadcast_name') or school.get('official_name')} "
                f"{sport} Venue"
            ),
            "address1": address.get("address1", ""),
            "address2": address.get("address2", ""),
            "city": address.get("city", school.get("city", "")),
            "state": address.get("state", school.get("state", profile.state)),
            "postal_code": address.get("postal_code", ""),
            "latitude": None,
            "longitude": None,
            "approval_status": "candidate",
            "broadcast_notes": "Verify venue location before broadcast use.",
        }

    @staticmethod
    def profile_payload(profile: AssociationProfile) -> Record:
        return {
            "id": profile.profile_id,
            "name": profile.name,
            "association": profile.association,
            "state": profile.state,
            "source_type": profile.source_type,
            "source_url": profile.source_url,
            "field_mapping": copy.deepcopy(profile.field_mapping),
            "defaults": copy.deepcopy(profile.defaults),
            "options": copy.deepcopy(profile.options),
        }
