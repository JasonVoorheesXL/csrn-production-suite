from __future__ import annotations

import copy
from datetime import datetime, timezone
from typing import Any

from association_import_service import AssociationImportService
from school_service import SchoolService


class MemoryStore:
    def __init__(
        self,
        *,
        schools: list[dict[str, Any]] | None = None,
        venues: list[dict[str, Any]] | None = None,
    ) -> None:
        self.schools = copy.deepcopy(schools or [])
        self.venues = copy.deepcopy(venues or [])
        self.logos: list[dict[str, Any]] = []

    def load_schools(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self.schools)

    def save_schools(self, items: list[dict[str, Any]]) -> None:
        self.schools = copy.deepcopy(items)

    def load_venues(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self.venues)

    def save_venues(self, items: list[dict[str, Any]]) -> None:
        self.venues = copy.deepcopy(items)

    def load_logos(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self.logos)

    def save_logos(self, items: list[dict[str, Any]]) -> None:
        self.logos = copy.deepcopy(items)


def profile() -> dict[str, Any]:
    return {
        "id": "test-association-football",
        "name": "Test Association Football",
        "association": "TAHSAA",
        "state": "MS",
        "source_type": "manifest",
        "source_url": "https://association.example/schools",
        "field_mapping": {
            "school.name": "official_name",
            "school.broadcast": "broadcast_name",
            "school.city": "city",
            "class": "classification",
            "region": "region",
        },
        "defaults": {
            "state": "MS",
            "classification": "5A",
        },
        "options": {
            "create_venues": True,
            "venue_sport": "Football",
            "update_existing_fields": [
                "classification",
                "region",
                "state",
            ],
        },
    }


def make_service(
    store: MemoryStore,
) -> AssociationImportService:
    school_service = SchoolService(
        load_schools=store.load_schools,
        save_schools=store.save_schools,
        load_logos=store.load_logos,
        save_logos=store.save_logos,
    )
    return AssociationImportService(
        school_service=school_service,
        load_schools=store.load_schools,
        load_venues=store.load_venues,
        save_venues=store.save_venues,
        clock=lambda: datetime(2026, 7, 24, tzinfo=timezone.utc),
    )


def row(
    official_name: str,
    broadcast_name: str,
    *,
    city: str = "Test City",
    classification: str = "5A",
    region: str = "1",
) -> dict[str, Any]:
    return {
        "school": {
            "name": official_name,
            "broadcast": broadcast_name,
            "city": city,
        },
        "class": classification,
        "region": region,
    }


def test_profile_validation_rejects_invalid_configuration() -> None:
    service = make_service(MemoryStore())

    missing_association = profile()
    missing_association["association"] = ""
    unsupported_type = profile()
    unsupported_type["source_type"] = "screen_scrape_magic"

    assert service.load_profile(missing_association).code == "ASSOCIATION_REQUIRED"
    assert service.load_profile(unsupported_type).code == "UNSUPPORTED_SOURCE_TYPE"


def test_normalize_row_maps_nested_fields_and_audit_metadata() -> None:
    service = make_service(MemoryStore())
    loaded = service.load_profile(profile())
    assert loaded.ok

    normalized = service.normalize_row(
        loaded.data["profile"],
        row("Example High School", "Example"),
    )

    assert normalized["official_name"] == "Example High School"
    assert normalized["broadcast_name"] == "Example"
    assert normalized["short_name"] == "Example"
    assert normalized["preferred_scorebug_name"] == "Example"
    assert normalized["source_data"] == {
        "association": "TAHSAA",
        "association_profile_id": "test-association-football",
        "provider": "TAHSAA",
        "source_url": "https://association.example/schools",
        "retrieved_at": "2026-07-24",
    }


def test_analyze_classifies_existing_duplicate_new_and_invalid() -> None:
    store = MemoryStore(
        schools=[
            {
                "id": "north",
                "official_name": "North High School",
                "broadcast_name": "North",
                "city": "North City",
            },
            {
                "id": "central",
                "official_name": "Central High School",
                "broadcast_name": "Central",
                "city": "Central City",
            },
        ]
    )
    service = make_service(store)

    result = service.analyze(
        profile(),
        [
            row("North High School", "North", city="North City"),
            row("Central Academy", "Central", city="Central City"),
            row("South High School", "South", city="South City"),
            row("", "Missing"),
        ],
    )

    assert result.ok
    assert result.data["found"] == 4
    assert result.data["existing"] == 1
    assert result.data["possible_duplicates"] == 1
    assert result.data["new"] == 1
    assert result.data["invalid"] == 1


def test_apply_creates_school_and_matching_venue() -> None:
    store = MemoryStore()
    service = make_service(store)

    result = service.apply(
        profile(),
        [row("South High School", "South", city="South City")],
    )

    assert result.ok
    assert result.data["imported"] == 1
    assert result.data["created_ids"] == ["MS5A-001"]
    assert len(store.schools) == 1
    assert store.schools[0]["official_name"] == "South High School"
    assert store.schools[0]["source_data"]["association"] == "TAHSAA"
    assert len(store.venues) == 1
    assert store.venues[0]["school_id"] == store.schools[0]["id"]
    assert store.venues[0]["csrn_school_id"] == "MS5A-001"


def test_apply_enriches_existing_without_overwriting_user_override() -> None:
    store = MemoryStore(
        schools=[
            {
                "id": "north",
                "csrn_id": "MS4A-001",
                "official_name": "North High School",
                "broadcast_name": "North",
                "state": "MS",
                "classification": "4A",
                "region": "9",
                "user_overrides": {"region": True},
                "source_data": {"provider": "Manual"},
            }
        ]
    )
    service = make_service(store)

    result = service.apply(
        profile(),
        [
            row(
                "North High School",
                "North",
                classification="5A",
                region="1",
            )
        ],
    )

    assert result.ok
    assert result.data["enriched_existing"] == 1
    assert result.data["imported"] == 0
    assert store.schools[0]["classification"] == "5A"
    assert store.schools[0]["region"] == "9"
    assert store.schools[0]["source_data"]["association"] == "TAHSAA"


def test_apply_skips_possible_duplicate_by_default() -> None:
    store = MemoryStore(
        schools=[
            {
                "id": "central",
                "official_name": "Central High School",
                "broadcast_name": "Central",
                "city": "Central City",
            }
        ]
    )
    service = make_service(store)

    result = service.apply(
        profile(),
        [row("Central Academy", "Central", city="Central City")],
    )

    assert result.ok
    assert result.data["imported"] == 0
    assert len(result.data["possible_duplicates"]) == 1
    assert len(store.schools) == 1


def test_apply_can_confirm_possible_duplicate_explicitly() -> None:
    store = MemoryStore(
        schools=[
            {
                "id": "central",
                "official_name": "Central High School",
                "broadcast_name": "Central",
                "city": "Central City",
            }
        ]
    )
    service = make_service(store)

    result = service.apply(
        profile(),
        [row("Central Academy", "Central", city="Central City")],
        allow_possible_duplicates=True,
    )

    assert result.ok
    assert result.data["imported"] == 1
    assert len(store.schools) == 2
