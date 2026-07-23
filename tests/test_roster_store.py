from __future__ import annotations

import json
from pathlib import Path

import pytest

from persistence_engine import DestructiveWriteBlocked
from roster_store import RosterStore, validate_rosters


def roster(roster_id: str, player_id: str = "p-1") -> dict:
    return {
        "id": roster_id,
        "school_id": "caledonia",
        "sport": "Football",
        "season": "2026",
        "level": "Varsity",
        "division": "Boys",
        "players": [{"id": player_id, "number": "1", "first_name": "Test", "last_name": "Player"}],
    }


def test_validator_rejects_duplicate_roster_ids() -> None:
    assert not validate_rosters([roster("same"), roster("same", "p-2")])


def test_validator_rejects_duplicate_player_ids_within_roster() -> None:
    item = roster("r-1")
    item["players"].append(dict(item["players"][0]))
    assert not validate_rosters([item])


def test_store_round_trip(tmp_path: Path) -> None:
    store = RosterStore(tmp_path / "Data" / "Rosters" / "rosters.json", tmp_path / "Data" / "Backups")
    store.save([roster("r-1")])
    assert store.load()[0]["id"] == "r-1"


def test_accidental_empty_replacement_is_blocked(tmp_path: Path) -> None:
    store = RosterStore(tmp_path / "rosters.json", tmp_path / "Backups")
    store.save([roster("r-1")])
    with pytest.raises(DestructiveWriteBlocked):
        store.save([])


def test_explicit_final_roster_delete_is_allowed_and_backed_up(tmp_path: Path) -> None:
    path = tmp_path / "rosters.json"
    backups = tmp_path / "Backups"
    store = RosterStore(path, backups)
    store.save([roster("r-1")])

    assert store.delete_roster("r-1") is True
    assert json.loads(path.read_text(encoding="utf-8")) == []
    backup_files = list((backups / "rosters").glob("*.json"))
    assert backup_files
    assert json.loads(backup_files[-1].read_text(encoding="utf-8"))[0]["id"] == "r-1"


def test_normalizer_only_saves_when_it_reports_a_change(tmp_path: Path) -> None:
    path = tmp_path / "rosters.json"
    backups = tmp_path / "Backups"
    store = RosterStore(path, backups)
    store.save([roster("r-1")])

    def unchanged(items: list[dict]) -> bool:
        return False

    store.load(normalizer=unchanged)
    assert not list((backups / "rosters").glob("*.json"))

    def changed(items: list[dict]) -> bool:
        items[0]["season"] = "2027"
        return True

    loaded = store.load(normalizer=changed)
    assert loaded[0]["season"] == "2027"
    assert list((backups / "rosters").glob("*.json"))
