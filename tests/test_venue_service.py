from __future__ import annotations

import copy
from typing import Any

from venue_service import VenueService


class MemoryStore:
    def __init__(
        self,
        venues: list[dict[str, Any]] | None = None,
        schools: list[dict[str, Any]] | None = None,
        broadcasts: list[dict[str, Any]] | None = None,
    ) -> None:
        self.venues = copy.deepcopy(venues or [])
        self.schools = copy.deepcopy(schools or [])
        self.broadcasts = copy.deepcopy(broadcasts or [])
        self.saved: list[list[dict[str, Any]]] = []

    def load_venues(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self.venues)

    def save_venues(self, venues: list[dict[str, Any]]) -> None:
        self.venues = copy.deepcopy(venues)
        self.saved.append(copy.deepcopy(venues))

    def load_schools(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self.schools)

    def load_broadcasts(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self.broadcasts)


def service_for(store: MemoryStore) -> VenueService:
    return VenueService(
        load_venues=store.load_venues,
        save_venues=store.save_venues,
        load_schools=store.load_schools,
        load_broadcasts=store.load_broadcasts,
        clock=lambda: 5000,
        token_factory=lambda: "abcd",
    )


def venue(
    venue_id: str = "caledonia-football",
    *,
    school_id: str = "caledonia",
    sport: str = "Football",
    name: str = "Caledonia HS Football Field",
    active: bool = True,
) -> dict[str, Any]:
    return {
        "id": venue_id,
        "school_id": school_id,
        "csrn_school_id": "MS5A-001",
        "sport": sport,
        "name": name,
        "address1": "105 Cavalier Drive",
        "address2": "",
        "city": "Caledonia",
        "state": "MS",
        "postal_code": "39740",
        "latitude": 33.68,
        "longitude": -88.32,
        "approval_status": "approved",
        "broadcast_notes": "Press box access through home gate.",
        "on_campus_assumed": True,
        "venue_address_source": "verified",
        "venue_verified": True,
        "active": active,
        "created_at": 100,
        "updated_at": 200,
    }


def test_clean_record_normalizes_fields_and_preserves_created_at() -> None:
    store = MemoryStore()
    service = service_for(store)

    record = service.clean_record(
        {
            "school_id": " caledonia ",
            "sport": "Football",
            "name": "  Cavalier Stadium  ",
            "state": "ms",
            "latitude": "33.68",
            "longitude": "bad",
            "on_campus_assumed": "yes",
            "venue_verified": "1",
            "created_at": 77,
        }
    )

    assert record["id"] == "caledonia-football-abcd"
    assert record["name"] == "Cavalier Stadium"
    assert record["state"] == "MS"
    assert record["latitude"] == 33.68
    assert record["longitude"] is None
    assert record["on_campus_assumed"] is True
    assert record["venue_verified"] is True
    assert record["created_at"] == 77
    assert record["updated_at"] == 5000


def test_list_and_read_return_filtered_copies() -> None:
    store = MemoryStore(
        [
            venue(),
            venue(
                "caledonia-basketball",
                sport="Basketball",
                name="Caledonia Gymnasium",
            ),
            venue(
                "new-hope-football",
                school_id="new-hope",
                name="New Hope HS Football Field",
                active=False,
            ),
        ]
    )
    service = service_for(store)

    result = service.list_venues(
        school_id="caledonia",
        sport="football",
        include_inactive=False,
    )
    assert [row["id"] for row in result.data["venues"]] == [
        "caledonia-football"
    ]

    result.data["venues"][0]["name"] = "Changed"
    assert store.venues[0]["name"] == "Caledonia HS Football Field"

    read = service.read("caledonia-football")
    assert read.ok
    assert read.data["venue"]["city"] == "Caledonia"
    assert service.read("missing").code == "VENUE_NOT_FOUND"


def test_create_requires_name_and_controls_duplicates() -> None:
    store = MemoryStore([venue()])
    service = service_for(store)

    assert service.create({"school_id": "new-hope"}).code == "VENUE_NAME_REQUIRED"

    duplicate = service.create(
        {
            "school_id": "caledonia",
            "sport": "Football",
            "name": "Another Caledonia Field",
        }
    )
    assert duplicate.code == "DUPLICATE_VENUE"
    assert duplicate.data["duplicate_venue"]["id"] == "caledonia-football"

    confirmed = service.create(
        {
            "school_id": "caledonia",
            "sport": "Football",
            "name": "Another Caledonia Field",
            "confirm_duplicate": True,
        }
    )
    assert confirmed.ok
    assert confirmed.data["venue"]["id"] == "caledonia-football-abcd"
    assert len(store.venues) == 2


def test_create_resolves_id_collisions() -> None:
    store = MemoryStore(
        [
            venue("new-hope-football-abcd", school_id="other", name="Other Field"),
        ]
    )
    service = service_for(store)

    result = service.create(
        {
            "school_id": "new-hope",
            "sport": "Football",
            "name": "New Hope Field",
        }
    )

    assert result.ok
    assert result.data["venue"]["id"] == "new-hope-football-abcd-2"


def test_update_preserves_id_and_checks_duplicates() -> None:
    store = MemoryStore(
        [
            venue(),
            venue(
                "new-hope-football",
                school_id="new-hope",
                name="New Hope HS Football Field",
            ),
        ]
    )
    service = service_for(store)

    missing = service.update("missing", {"name": "Unknown"})
    assert missing.code == "VENUE_NOT_FOUND"

    duplicate = service.update(
        "caledonia-football",
        {
            "school_id": "new-hope",
            "sport": "Football",
            "name": "Replacement Field",
        },
    )
    assert duplicate.code == "DUPLICATE_VENUE"

    updated = service.update(
        "caledonia-football",
        {"name": "Cavalier Stadium", "venue_verified": False},
    )
    assert updated.ok
    assert updated.data["venue"]["id"] == "caledonia-football"
    assert updated.data["venue"]["name"] == "Cavalier Stadium"
    assert updated.data["venue"]["created_at"] == 100
    assert updated.data["venue"]["updated_at"] == 5000


def test_delete_blocks_referenced_venues_and_removes_unreferenced() -> None:
    store = MemoryStore(
        [venue(), venue("unused", school_id="", name="Neutral Site")],
        schools=[
            {
                "id": "caledonia",
                "broadcast_name": "Caledonia",
                "venue_id": "caledonia-football",
            }
        ],
        broadcasts=[
            {
                "broadcast_id": "FB-1",
                "home_team": "Caledonia",
                "visitor_team": "New Hope",
                "venue_id": "caledonia-football",
            }
        ],
    )
    service = service_for(store)

    blocked = service.delete("caledonia-football")
    assert blocked.code == "VENUE_IN_USE"
    assert blocked.data["schools"][0]["id"] == "caledonia"
    assert blocked.data["broadcasts"][0]["id"] == "FB-1"

    deleted = service.delete("unused")
    assert deleted.ok
    assert deleted.data == {"ok": True, "deleted": "unused"}
    assert [row["id"] for row in store.venues] == ["caledonia-football"]
    assert service.delete("missing").code == "VENUE_NOT_FOUND"


def test_for_school_prefers_explicit_then_matching_sport() -> None:
    store = MemoryStore(
        [
            venue(),
            venue(
                "caledonia-basketball",
                sport="Basketball",
                name="Caledonia Gymnasium",
            ),
        ]
    )
    service = service_for(store)

    explicit = service.for_school(
        {"id": "caledonia", "venue_id": "caledonia-basketball"},
        "Football",
    )
    assert explicit and explicit["id"] == "caledonia-basketball"

    football = service.for_school({"id": "caledonia"}, "Football")
    assert football and football["id"] == "caledonia-football"

    fallback = service.for_school({"id": "caledonia"}, "Soccer")
    assert fallback and fallback["id"] == "caledonia-football"
    assert service.for_school(None, "Football") is None


def test_migrate_legacy_names_is_idempotent() -> None:
    store = MemoryStore(
        [
            venue(name="Caledonia Football Venue"),
            venue(
                "new-hope-football",
                school_id="new-hope",
                name="New Hope Football Stadium",
            ),
            venue("neutral", school_id="", name="Davis Wade Stadium"),
        ]
    )
    service = service_for(store)

    first = service.migrate_legacy_names()
    assert first.data["migrated"] == 2
    assert store.venues[0]["name"] == "Caledonia HS Football Field"
    assert store.venues[1]["name"] == "New Hope HS Football Field"

    second = service.migrate_legacy_names()
    assert second.data["migrated"] == 0
    assert len(store.saved) == 1


