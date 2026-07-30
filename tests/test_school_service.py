from __future__ import annotations

import copy
from typing import Any

from school_service import SchoolService


class MemoryStore:
    def __init__(self) -> None:
        self.schools: list[dict[str, Any]] = []
        self.logos: list[dict[str, Any]] = []
        self.school_saves = 0
        self.logo_saves = 0

    def load_schools(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self.schools)

    def save_schools(self, schools: list[dict[str, Any]]) -> None:
        self.schools = copy.deepcopy(schools)
        self.school_saves += 1

    def load_logos(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self.logos)

    def save_logos(self, logos: list[dict[str, Any]]) -> None:
        self.logos = copy.deepcopy(logos)
        self.logo_saves += 1


def make_service(
    store: MemoryStore | None = None,
) -> tuple[SchoolService, MemoryStore]:
    memory = store or MemoryStore()
    service = SchoolService(
        load_schools=memory.load_schools,
        save_schools=memory.save_schools,
        load_logos=memory.load_logos,
        save_logos=memory.save_logos,
    )
    return service, memory


def existing_school(**overrides: Any) -> dict[str, Any]:
    school = {
        "id": "caledonia",
        "csrn_id": "MS5A-001",
        "official_name": "Caledonia High School",
        "broadcast_name": "Caledonia",
        "nickname": "Confederates",
        "city": "Caledonia",
        "district": "Lowndes County",
        "state": "MS",
        "classification": "5A",
        "region": "1",
        "primary_color": "#C9203B",
        "secondary_color": "#FFFFFF",
        "primary_logo": "/school-logos/caledonia/round-master.png",
        "alternate_logo": "",
        "verification_status": "verified",
        "active": True,
    }
    school.update(overrides)
    return school


def test_list_and_read_preserve_school_contract() -> None:
    store = MemoryStore()
    store.schools = [existing_school()]
    service, _store = make_service(store)

    listed = service.list_schools()
    read = service.read("caledonia")
    missing = service.read("missing")

    assert listed == [
        {
            "id": "caledonia",
            "official_name": "Caledonia High School",
            "broadcast_name": "Caledonia",
            "mascot": "Confederates",
            "nickname": "Confederates",
            "primary_color": "#C9203B",
            "secondary_color": "#FFFFFF",
            "primary_logo": "/school-logos/caledonia/round-master.png",
            "alternate_logo": "",
            "verification_status": "verified",
            "csrn_id": "MS5A-001",
            "classification": "5A",
            "region": "1",
            "city": "Caledonia",
            "active": True,
        }
    ]
    assert read.ok
    assert read.data["school"]["official_name"] == "Caledonia High School"
    assert missing.code == "SCHOOL_NOT_FOUND"


def test_create_requires_names_and_detects_duplicates() -> None:
    store = MemoryStore()
    store.schools = [existing_school()]
    service, _store = make_service(store)

    missing_name = service.create({"official_name": "Caledonia High School"})
    duplicate = service.create(
        {
            "official_name": "Caledonia High School",
            "broadcast_name": "Caledonia",
        }
    )

    assert missing_name.code == "SCHOOL_NAME_REQUIRED"
    assert duplicate.code == "LIKELY_DUPLICATE"
    assert duplicate.data["matches"][0]["id"] == "caledonia"
    assert store.school_saves == 0


def test_create_normalizes_social_and_allocates_unique_ids() -> None:
    store = MemoryStore()
    store.schools = [existing_school()]
    service, _store = make_service(store)

    result = service.create(
        {
            "id": "Caledonia",
            "official_name": "Caledonia Preparatory School",
            "broadcast_name": "Caledonia Prep",
            "state": "MS",
            "classification": "5A",
            "general_social": {
                "facebook": "caledoniaprep",
                "website": "caledoniaprep.org",
            },
            "programs": {
                "Football": {
                    "x": "@caledoniaprepfootball",
                }
            },
        }
    )

    assert result.ok
    school = result.data["school"]
    assert school["id"] == "caledonia-2"
    assert school["csrn_id"] == "MS5A-002"
    assert school["general_social"]["facebook"] == (
        "https://facebook.com/caledoniaprep"
    )
    assert school["general_social"]["website"] == (
        "https://caledoniaprep.org"
    )
    assert school["programs"]["Football"]["x"] == (
        "https://x.com/caledoniaprepfootball"
    )
    assert school["logo_metadata"]["shape_standard"] == "round"
    assert store.school_saves == 1


def test_create_rejects_invalid_social_urls() -> None:
    service, store = make_service()

    result = service.create(
        {
            "official_name": "Example High School",
            "broadcast_name": "Example",
            "general_social": {
                "facebook": "https://example.com/not-facebook",
            },
        }
    )

    assert result.code == "INVALID_SOCIAL_URL"
    assert "facebook" in result.data["fields"]
    assert store.school_saves == 0


def test_update_normalizes_social_and_synchronizes_linked_logo() -> None:
    store = MemoryStore()
    store.schools = [
        existing_school(default_broadcast_logo_id="logo-caledonia")
    ]
    store.logos = [
        {
            "id": "logo-caledonia",
            "approval_status": "candidate",
            "round_master_path": "",
        }
    ]
    service, _store = make_service(store)

    result = service.update(
        "caledonia",
        {
            "mascot": "Warriors",
            "logo_status": "approved",
            "primary_logo": "/logos/caledonia-round.png",
            "general_social": {"instagram": "caledoniawarriors"},
        },
    )

    assert result.ok
    school = result.data["school"]
    assert school["mascot"] == "Warriors"
    assert school["general_social"]["instagram"] == (
        "https://instagram.com/caledoniawarriors"
    )
    assert store.logos[0]["approval_status"] == "approved"
    assert store.logos[0]["round_master_path"] == (
        "/logos/caledonia-round.png"
    )
    assert store.school_saves == 1
    assert store.logo_saves == 1


def test_update_delete_and_duplicate_check_map_domain_results() -> None:
    store = MemoryStore()
    store.schools = [existing_school()]
    service, _store = make_service(store)

    missing_update = service.update("missing", {"city": "Columbus"})
    duplicate_matches = service.duplicate_candidates(
        {
            "official_name": "Caledonia High School",
            "broadcast_name": "Caledonia",
        }
    )
    excluded_matches = service.duplicate_candidates(
        {
            "official_name": "Caledonia High School",
            "broadcast_name": "Caledonia",
        },
        "caledonia",
    )
    deleted = service.delete("caledonia")
    missing_delete = service.delete("caledonia")

    assert missing_update.code == "SCHOOL_NOT_FOUND"
    assert duplicate_matches[0]["score"] == 5
    assert excluded_matches == []
    assert deleted.ok
    assert deleted.data == {"ok": True}
    assert missing_delete.code == "SCHOOL_NOT_FOUND"
    assert store.schools == []
