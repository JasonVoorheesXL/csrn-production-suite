from __future__ import annotations

import copy
from typing import Any

from roster_service import RosterService


class MemoryStore:
    def __init__(
        self,
        *,
        rosters: list[dict[str, Any]] | None = None,
        schools: list[dict[str, Any]] | None = None,
    ) -> None:
        self.rosters = copy.deepcopy(rosters or [])
        self.schools = copy.deepcopy(schools or [])
        self.save_count = 0

    def load_rosters(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self.rosters)

    def save_rosters(self, items: list[dict[str, Any]]) -> None:
        self.rosters = copy.deepcopy(items)
        self.save_count += 1

    def load_schools(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self.schools)


def make_service(store: MemoryStore) -> RosterService:
    return RosterService(
        load_rosters=store.load_rosters,
        save_rosters=store.save_rosters,
        load_schools=store.load_schools,
        clock=lambda: 1_700_000_000,
    )


def roster_record(**overrides: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "id": "caledonia-football-2026-varsity-boys",
        "school_id": "caledonia",
        "sport": "Football",
        "season": "2026",
        "level": "Varsity",
        "division": "Boys",
        "players": [],
        "created_at": 1_600_000_000,
        "updated_at": 1_600_000_000,
    }
    record.update(overrides)
    return record


def test_list_rosters_adds_school_name_and_player_counts() -> None:
    store = MemoryStore(
        schools=[
            {
                "id": "caledonia",
                "official_name": "Caledonia High School",
                "broadcast_name": "Caledonia",
            }
        ],
        rosters=[
            roster_record(
                players=[
                    {"id": "1-a", "status": "active"},
                    {"id": "2-b", "status": "inactive"},
                    {"id": "3-c"},
                ]
            )
        ],
    )

    rosters = make_service(store).list_rosters()

    assert len(rosters) == 1
    assert rosters[0]["school_name"] == "Caledonia"
    assert rosters[0]["player_count"] == 3
    assert rosters[0]["active_count"] == 2
    assert rosters[0]["inactive_count"] == 1


def test_read_returns_summary_or_not_found() -> None:
    store = MemoryStore(
        rosters=[roster_record()],
        schools=[
            {
                "id": "caledonia",
                "official_name": "Caledonia High School",
            }
        ],
    )
    service = make_service(store)

    found = service.read("caledonia-football-2026-varsity-boys")
    missing = service.read("missing")

    assert found.ok
    assert found.data["roster"]["school_name"] == "Caledonia High School"
    assert missing.code == "ROSTER_NOT_FOUND"


def test_create_requires_school_and_season() -> None:
    service = make_service(MemoryStore())

    no_school = service.create({"season": "2026"})
    no_season = service.create({"school_id": "caledonia"})

    assert no_school.code == "SCHOOL_AND_SEASON_REQUIRED"
    assert no_season.code == "SCHOOL_AND_SEASON_REQUIRED"


def test_create_rejects_case_insensitive_duplicate() -> None:
    store = MemoryStore(rosters=[roster_record()])
    result = make_service(store).create(
        {
            "school_id": "caledonia",
            "sport": "football",
            "season": "2026",
            "level": "varsity",
            "division": "boys",
        }
    )

    assert result.code == "ROSTER_ALREADY_EXISTS"
    assert result.data["roster"]["id"] == (
        "caledonia-football-2026-varsity-boys"
    )
    assert store.save_count == 0


def test_create_applies_defaults_unique_id_and_timestamps() -> None:
    store = MemoryStore(
        rosters=[
            roster_record(
                id="caledonia-football-2027-varsity-boys",
                season="2025",
            )
        ],
        schools=[
            {
                "id": "caledonia",
                "broadcast_name": "Caledonia",
            }
        ],
    )

    result = make_service(store).create(
        {
            "school_id": "caledonia",
            "season": "2027",
        }
    )

    assert result.ok
    created = result.data["roster"]
    assert created["id"] == "caledonia-football-2027-varsity-boys-2"
    assert created["sport"] == "Football"
    assert created["level"] == "Varsity"
    assert created["division"] == "Boys"
    assert created["players"] == []
    assert created["created_at"] == 1_700_000_000
    assert created["updated_at"] == 1_700_000_000
    assert created["school_name"] == "Caledonia"
    assert store.save_count == 1


def test_update_trims_supported_fields_and_preserves_other_data() -> None:
    store = MemoryStore(
        rosters=[
            roster_record(
                players=[{"id": "12-player", "first_name": "Pat"}],
                custom_field="preserve-me",
            )
        ]
    )

    result = make_service(store).update(
        "caledonia-football-2026-varsity-boys",
        {
            "school_id": " new-hope ",
            "sport": " Basketball ",
            "season": " 2027 ",
            "level": " JV ",
            "division": " Girls ",
            "players": [],
            "custom_field": "replace-me",
        },
    )

    assert result.ok
    updated = result.data["roster"]
    assert updated["school_id"] == "new-hope"
    assert updated["sport"] == "Basketball"
    assert updated["season"] == "2027"
    assert updated["level"] == "JV"
    assert updated["division"] == "Girls"
    assert updated["updated_at"] == 1_700_000_000
    assert updated["players"] == [
        {"id": "12-player", "first_name": "Pat"}
    ]
    assert updated["custom_field"] == "preserve-me"


def test_update_and_delete_report_missing_roster() -> None:
    store = MemoryStore(rosters=[roster_record()])
    service = make_service(store)

    missing_update = service.update("missing", {"season": "2027"})
    missing_delete = service.delete("missing")
    deleted = service.delete("caledonia-football-2026-varsity-boys")

    assert missing_update.code == "ROSTER_NOT_FOUND"
    assert missing_delete.code == "ROSTER_NOT_FOUND"
    assert deleted.ok
    assert deleted.data == {"ok": True}
    assert store.rosters == []


