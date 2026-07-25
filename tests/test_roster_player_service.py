from __future__ import annotations

import copy
from typing import Any

from roster_service import RosterService


class MemoryStore:
    def __init__(self, rosters: list[dict[str, Any]] | None = None) -> None:
        self.rosters = copy.deepcopy(rosters or [])
        self.save_count = 0

    def load_rosters(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self.rosters)

    def save_rosters(self, items: list[dict[str, Any]]) -> None:
        self.rosters = copy.deepcopy(items)
        self.save_count += 1

    def load_schools(self) -> list[dict[str, Any]]:
        return [{"id": "caledonia", "broadcast_name": "Caledonia"}]


def make_service(store: MemoryStore) -> RosterService:
    return RosterService(
        load_rosters=store.load_rosters,
        save_rosters=store.save_rosters,
        load_schools=store.load_schools,
        clock=lambda: 1_700_000_000,
    )


def roster(players: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "id": "caledonia-football-2026-varsity-boys",
        "school_id": "caledonia",
        "sport": "Football",
        "season": "2026",
        "level": "Varsity",
        "division": "Boys",
        "players": copy.deepcopy(players or []),
        "created_at": 1_600_000_000,
        "updated_at": 1_600_000_000,
    }


def test_create_player_validates_roster_and_name() -> None:
    missing_roster = make_service(MemoryStore()).create_player(
        "missing",
        {"first_name": "Pat"},
    )
    store = MemoryStore([roster()])
    missing_name = make_service(store).create_player(
        "caledonia-football-2026-varsity-boys",
        {"number": "12"},
    )

    assert missing_roster.code == "ROSTER_NOT_FOUND"
    assert missing_name.code == "PLAYER_NAME_REQUIRED"
    assert store.save_count == 0


def test_create_player_preserves_contract_and_duplicate_warning() -> None:
    store = MemoryStore(
        [
            roster(
                [
                    {
                        "id": "12-john-doe",
                        "number": "12",
                        "first_name": "John",
                        "last_name": "Doe",
                        "status": "active",
                    }
                ]
            )
        ]
    )
    result = make_service(store).create_player(
        "caledonia-football-2026-varsity-boys",
        {
            "number": "12",
            "first_name": " John ",
            "last_name": " Doe ",
            "captain": 1,
            "status": "inactive",
            "pronunciation_verified": True,
        },
    )

    assert result.ok
    assert result.data["warning"] == "DUPLICATE_JERSEY_NUMBER"
    player = result.data["player"]
    assert player["id"] == "12-john-doe-2"
    assert player["first_name"] == "John"
    assert player["last_name"] == "Doe"
    assert player["captain"] is True
    assert player["status"] == "inactive"
    assert player["pronunciation_verified"] is True
    assert store.rosters[0]["updated_at"] == 1_700_000_000


def test_update_player_changes_supported_fields_and_warns() -> None:
    store = MemoryStore(
        [
            roster(
                [
                    {
                        "id": "7-pat-one",
                        "number": "7",
                        "first_name": "Pat",
                        "last_name": "One",
                        "status": "active",
                        "captain": False,
                        "custom": "keep",
                    },
                    {
                        "id": "8-pat-two",
                        "number": "8",
                        "first_name": "Pat",
                        "last_name": "Two",
                        "status": "active",
                    },
                ]
            )
        ]
    )
    result = make_service(store).update_player(
        "caledonia-football-2026-varsity-boys",
        "7-pat-one",
        {
            "number": "8",
            "preferred_name": " P ",
            "captain": True,
            "status": "inactive",
            "custom": "replace",
        },
    )

    assert result.ok
    assert result.data["warning"] == "DUPLICATE_JERSEY_NUMBER"
    player = result.data["player"]
    assert player["number"] == "8"
    assert player["preferred_name"] == "P"
    assert player["captain"] is True
    assert player["status"] == "inactive"
    assert player["custom"] == "keep"


def test_update_player_reports_missing_roster_or_player() -> None:
    service = make_service(MemoryStore([roster()]))

    missing_roster = service.update_player("missing", "player", {})
    missing_player = service.update_player(
        "caledonia-football-2026-varsity-boys",
        "missing",
        {},
    )

    assert missing_roster.code == "ROSTER_NOT_FOUND"
    assert missing_player.code == "PLAYER_NOT_FOUND"


def test_delete_player_reports_missing_records_and_deletes() -> None:
    store = MemoryStore(
        [roster([{"id": "12-player", "number": "12"}])]
    )
    service = make_service(store)

    assert service.delete_player("missing", "12-player").code == (
        "ROSTER_NOT_FOUND"
    )
    assert service.delete_player(
        "caledonia-football-2026-varsity-boys",
        "missing",
    ).code == "PLAYER_NOT_FOUND"

    deleted = service.delete_player(
        "caledonia-football-2026-varsity-boys",
        "12-player",
    )
    assert deleted.ok
    assert deleted.data == {"ok": True}
    assert store.rosters[0]["players"] == []
    assert store.rosters[0]["updated_at"] == 1_700_000_000


def test_import_players_validates_input_and_roster() -> None:
    service = make_service(MemoryStore([roster()]))

    invalid = service.import_players(
        "caledonia-football-2026-varsity-boys",
        {"first_name": "Pat"},
    )
    missing = service.import_players("missing", [])

    assert invalid.code == "INVALID_PLAYER_LIST"
    assert missing.code == "ROSTER_NOT_FOUND"


def test_import_players_skips_invalid_rows_and_parses_flags() -> None:
    store = MemoryStore(
        [
            roster(
                [
                    {
                        "id": "10-alex-smith",
                        "number": "10",
                        "first_name": "Alex",
                        "last_name": "Smith",
                        "status": "active",
                    }
                ]
            )
        ]
    )
    result = make_service(store).import_players(
        "caledonia-football-2026-varsity-boys",
        [
            None,
            {"number": "99"},
            {
                "number": "10",
                "first_name": " Alex ",
                "last_name": " Smith ",
                "captain": "yes",
                "starter": "1",
                "pronunciation_verified": "true",
                "status": "inactive",
            },
            {
                "number": "11",
                "first_name": "Taylor",
                "last_name": "Jones",
                "captain": "no",
            },
        ],
    )

    assert result.ok
    assert result.data["added"] == 2
    assert result.data["warnings"] == ["Duplicate jersey number 10"]
    assert result.data["roster"]["player_count"] == 3
    imported = store.rosters[0]["players"][1:]
    assert imported[0]["id"] == "10-alex-smith-2"
    assert imported[0]["captain"] is True
    assert imported[0]["starter"] is True
    assert imported[0]["pronunciation_verified"] is True
    assert imported[0]["status"] == "inactive"
    assert imported[1]["captain"] is False
