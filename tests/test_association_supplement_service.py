from __future__ import annotations

import copy
from typing import Any

from association_supplement_service import AssociationSupplementService


class MemoryStore:
    def __init__(
        self,
        *,
        schools: list[dict[str, Any]] | None = None,
        venues: list[dict[str, Any]] | None = None,
    ) -> None:
        self.schools = copy.deepcopy(schools or [])
        self.venues = copy.deepcopy(venues or [])

    def load_schools(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self.schools)

    def save_schools(self, items: list[dict[str, Any]], *, force: bool = False) -> None:
        self.schools = copy.deepcopy(items)

    def load_venues(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self.venues)

    def save_venues(self, items: list[dict[str, Any]], *, force: bool = False) -> None:
        self.venues = copy.deepcopy(items)


def make_service(store: MemoryStore) -> AssociationSupplementService:
    return AssociationSupplementService(
        load_schools=store.load_schools,
        save_schools=store.save_schools,
        load_venues=store.load_venues,
        save_venues=store.save_venues,
    )


def source() -> dict[str, Any]:
    return {
        "provider": "Test Association Directory",
        "url": "https://association.example/directory",
        "checked_at": "2026-07-24",
    }


def test_analyze_branding_classifies_ready_preserved_and_missing() -> None:
    store = MemoryStore(
        schools=[
            {
                "id": "ready",
                "official_name": "Ready High School",
                "branding_status": "candidate",
            },
            {
                "id": "logo",
                "official_name": "Logo High School",
                "primary_logo": "/logos/logo.png",
            },
            {
                "id": "manual",
                "official_name": "Manual High School",
                "branding_status": "manual",
            },
        ]
    )
    result = make_service(store).analyze_branding(
        [
            {"official_name": "Ready High School"},
            {"official_name": "Logo High School"},
            {"official_name": "Manual High School"},
            {"official_name": "Missing High School"},
        ],
        source=source(),
    )

    assert result.ok
    assert result.data["found"] == 4
    assert result.data["ready"] == 1
    assert result.data["preserved"] == 2
    assert result.data["school_missing"] == 1
    assert result.data["source"] == source()


def test_apply_branding_updates_candidates_and_preserves_reviewed_data() -> None:
    store = MemoryStore(
        schools=[
            {
                "id": "ready",
                "official_name": "Ready High School",
                "primary_color": "#000000",
                "secondary_color": "#FFFFFF",
            },
            {
                "id": "approved",
                "official_name": "Approved High School",
                "branding_status": "approved",
                "primary_color": "#111111",
            },
        ]
    )
    result = make_service(store).apply_branding(
        [
            {
                "official_name": "Ready High School",
                "primary_color": "#AA0000",
                "secondary_color": "#000000",
                "accent_color": "#FFFFFF",
                "source_provider": "Research seed",
                "source_url": "https://association.example/ready",
                "notes": "Candidate colors",
            },
            {
                "official_name": "Approved High School",
                "primary_color": "#FF0000",
            },
            {"official_name": "Missing High School"},
        ],
        source=source(),
    )

    assert result.data == {
        "updated": 1,
        "preserved": 1,
        "missing_schools": ["Missing High School"],
    }
    ready = next(item for item in store.schools if item["id"] == "ready")
    approved = next(item for item in store.schools if item["id"] == "approved")
    assert ready["primary_color"] == "#AA0000"
    assert ready["branding_status"] == "candidate"
    assert ready["branding_source"]["checked_at"] == "2026-07-24"
    assert approved["primary_color"] == "#111111"


def test_analyze_enrichment_reports_source_gaps_and_missing_schools() -> None:
    store = MemoryStore(
        schools=[
            {
                "id": "north",
                "official_name": "North High School",
            }
        ]
    )
    result = make_service(store).analyze_enrichment(
        [
            {
                "official_name": "North High School",
                "mascot": "Tigers",
                "phone": "",
                "website": "",
                "school_address": {},
            },
            {
                "official_name": "Missing High School",
                "mascot": "Rams",
            },
        ],
        source=source(),
        classification="5A",
    )

    assert result.data["classification"] == "5A"
    assert result.data["ready"] == 1
    assert result.data["school_missing"] == 1
    assert result.data["schools"][0]["missing_source_fields"] == [
        "phone",
        "website",
        "school_address",
    ]


def test_apply_enrichment_updates_school_and_creates_candidate_venue() -> None:
    store = MemoryStore(
        schools=[
            {
                "id": "north",
                "csrn_id": "MS5A-001",
                "official_name": "North High School",
                "broadcast_name": "North",
                "state": "MS",
                "user_overrides": {},
                "general_social": {},
                "programs": {},
            }
        ]
    )
    result = make_service(store).apply_enrichment(
        [
            {
                "official_name": "North High School",
                "mascot": "Tigers",
                "phone": "555-0100",
                "website": "https://north.example",
                "school_address": {
                    "address1": "1 School Road",
                    "address2": "",
                    "city": "North City",
                    "state": "MS",
                    "postal_code": "39000",
                },
                "source_url": "https://association.example/north",
            }
        ],
        source=source(),
    )

    assert result.data["updated"] == 1
    assert result.data["logo_pending_approval"] == 1
    assert result.data["venue_verification_needed"] == 1
    school = store.schools[0]
    assert school["mascot"] == "Tigers"
    assert school["nickname"] == "Tigers"
    assert school["website"] == "https://north.example"
    assert school["general_social"]["website"] == "https://north.example"
    assert school["venue_id"] == "north-football"
    assert school["programs"]["Football"]["venue_id"] == "north-football"
    assert school["verification_status"] == "candidate_enriched"
    assert len(store.venues) == 1
    assert store.venues[0]["csrn_school_id"] == "MS5A-001"


def test_apply_enrichment_preserves_user_overrides_and_existing_venue_notes() -> None:
    store = MemoryStore(
        schools=[
            {
                "id": "north",
                "official_name": "North High School",
                "broadcast_name": "North",
                "mascot": "Wildcats",
                "phone": "555-OLD",
                "website": "https://manual.example",
                "venue_id": "north-football",
                "user_overrides": {
                    "mascot": True,
                    "phone": True,
                    "website": True,
                },
                "programs": {"Football": {}},
            }
        ],
        venues=[
            {
                "id": "north-football",
                "school_id": "north",
                "broadcast_notes": "Operator verified this venue.",
            }
        ],
    )
    result = make_service(store).apply_enrichment(
        [
            {
                "official_name": "North High School",
                "mascot": "Tigers",
                "phone": "555-NEW",
                "website": "https://source.example",
                "school_address": {
                    "address1": "1 School Road",
                    "city": "North City",
                    "state": "MS",
                    "postal_code": "39000",
                },
            }
        ],
        source=source(),
    )

    assert result.ok
    school = store.schools[0]
    assert school["mascot"] == "Wildcats"
    assert school["phone"] == "555-OLD"
    assert school["website"] == "https://manual.example"
    assert store.venues[0]["broadcast_notes"] == "Operator verified this venue."


def test_apply_enrichment_counts_missing_source_fields_and_missing_school() -> None:
    store = MemoryStore(
        schools=[
            {
                "id": "north",
                "official_name": "North High School",
                "broadcast_name": "North",
                "programs": {},
            }
        ]
    )
    result = make_service(store).apply_enrichment(
        [
            {
                "official_name": "North High School",
                "mascot": "",
                "phone": "",
                "website": "",
                "school_address": {},
            },
            {
                "official_name": "Missing High School",
                "mascot": "Rams",
            },
        ],
        source=source(),
    )

    assert result.data["updated"] == 1
    assert result.data["missing_schools"] == ["Missing High School"]
    assert result.data["missing_mascot"] == 1
    assert result.data["missing_address"] == 1
    assert result.data["missing_website"] == 1


