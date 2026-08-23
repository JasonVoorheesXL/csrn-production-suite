from __future__ import annotations

from typing import Any

from association_import_service import AssociationImportService
from school_service import SchoolService


class MemoryStore:
    def __init__(self) -> None:
        self.schools: list[dict[str, Any]] = []
        self.venues: list[dict[str, Any]] = []
        self.logos: list[dict[str, Any]] = []

    def load_schools(self) -> list[dict[str, Any]]:
        return list(self.schools)

    def save_schools(self, items: list[dict[str, Any]]) -> None:
        self.schools = list(items)

    def load_venues(self) -> list[dict[str, Any]]:
        return list(self.venues)

    def save_venues(self, items: list[dict[str, Any]]) -> None:
        self.venues = list(items)

    def load_logos(self) -> list[dict[str, Any]]:
        return list(self.logos)

    def save_logos(self, items: list[dict[str, Any]]) -> None:
        self.logos = list(items)


def test_official_name_mapping_can_supply_broadcast_name_fallback() -> None:
    store = MemoryStore()
    school_service = SchoolService(
        load_schools=store.load_schools,
        save_schools=store.save_schools,
        load_logos=store.load_logos,
        save_logos=store.save_logos,
    )
    service = AssociationImportService(
        school_service=school_service,
        load_schools=store.load_schools,
        load_venues=store.load_venues,
        save_venues=store.save_venues,
    )
    profile = {
        "id": "single-name-column",
        "name": "Single Name Column",
        "association": "TAHSAA",
        "state": "MS",
        "source_type": "csv",
        "source_url": "https://association.example/schools.csv",
        "field_mapping": {"School": "official_name"},
        "defaults": {"state": "MS"},
        "options": {},
    }

    loaded = service.load_profile(profile)

    assert loaded.ok
    normalized = service.normalize_row(
        loaded.data["profile"],
        {"School": "North High School"},
    )
    assert normalized["official_name"] == "North High School"
    assert normalized["broadcast_name"] == "North High School"


