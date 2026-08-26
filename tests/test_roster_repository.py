from __future__ import annotations

from pathlib import Path

import pytest

from persistence_engine import DestructiveWriteBlocked, JsonPersistenceEngine
from roster_repository import RosterRepository, RosterRepositoryValidationError


def engine(tmp_path: Path) -> JsonPersistenceEngine:
    return JsonPersistenceEngine(tmp_path / "backups", tmp_path / "quarantine")


def test_load_accepts_wrapped_payload_and_normalizes(tmp_path: Path) -> None:
    path = tmp_path / "rosters.json"
    path.write_text('{"rosters":[{"school_id":"caledonia","players":[{"number":"7"}]}]}', encoding="utf-8")

    def normalize(items):
        changed = False
        for roster in items:
            if "id" not in roster:
                roster["id"] = "caledonia-football"
                changed = True
            for player in roster["players"]:
                if "id" not in player:
                    player["id"] = "7-player"
                    changed = True
        return changed

    repository = RosterRepository(engine(tmp_path), path, normalizer=normalize)
    rosters = repository.load()

    assert rosters[0]["id"] == "caledonia-football"
    assert rosters[0]["players"][0]["id"] == "7-player"
    assert path.read_text(encoding="utf-8").lstrip().startswith("[")


def test_save_rejects_duplicate_roster_ids(tmp_path: Path) -> None:
    repository = RosterRepository(engine(tmp_path), tmp_path / "rosters.json")
    with pytest.raises(RosterRepositoryValidationError):
        repository.save([{"id": "same", "players": []}, {"id": "same", "players": []}])


def test_save_rejects_duplicate_player_ids_within_roster(tmp_path: Path) -> None:
    repository = RosterRepository(engine(tmp_path), tmp_path / "rosters.json")
    with pytest.raises(RosterRepositoryValidationError):
        repository.save([{"id": "r1", "players": [{"id": "p1"}, {"id": "p1"}]}])


def test_save_blocks_replacing_a_populated_roster_database_with_empty(tmp_path: Path) -> None:
    repository = RosterRepository(engine(tmp_path), tmp_path / "rosters.json")
    repository.save([{"id": "r1", "players": [{"id": "p1", "number": "7"}]}])
    with pytest.raises(DestructiveWriteBlocked):
        repository.save([])
    # The populated database survives -- the blocked write never landed.
    assert len(repository.load()) == 1


def test_save_blocks_a_large_roster_entry_count_drop(tmp_path: Path) -> None:
    # The guard counts roster ENTRIES (how many team rosters exist), not
    # players within any one roster -- record_count() on this file's list
    # payload is len(list). Losing most of the roster.json's team entries
    # in one write is exactly the catastrophic case this protects against;
    # a single roster's own "players" list shrinking, with the same number
    # of roster entries before and after, does NOT trip this guard.
    repository = RosterRepository(engine(tmp_path), tmp_path / "rosters.json")
    five_rosters = [
        {"id": f"r{i}", "players": [{"id": f"r{i}-p1", "number": "1"}]}
        for i in range(5)
    ]
    repository.save(five_rosters)
    with pytest.raises(DestructiveWriteBlocked):
        repository.save(five_rosters[:1])


def test_save_force_bypasses_the_destructive_write_guard(tmp_path: Path) -> None:
    repository = RosterRepository(engine(tmp_path), tmp_path / "rosters.json")
    repository.save([{"id": "r1", "players": [{"id": "p1", "number": "7"}]}])
    repository.save([], force=True)
    assert repository.load() == []


def test_get_returns_copy(tmp_path: Path) -> None:
    repository = RosterRepository(engine(tmp_path), tmp_path / "rosters.json")
    repository.save([{"id": "r1", "players": [{"id": "p1", "first_name": "A"}]}])
    roster = repository.get("r1")
    assert roster is not None
    roster["players"][0]["first_name"] = "Changed"
    assert repository.get("r1")["players"][0]["first_name"] == "A"


def test_invalid_payload_is_quarantined_and_defaulted(tmp_path: Path) -> None:
    path = tmp_path / "rosters.json"
    path.write_text('{"rosters":"not-a-list"}', encoding="utf-8")
    repository = RosterRepository(engine(tmp_path), path)
    assert repository.load() == []
    assert path.read_text(encoding="utf-8").strip().startswith("[")
    assert list((tmp_path / "quarantine").glob("*.json"))


def test_cache_invalidates_when_file_changes(tmp_path: Path) -> None:
    path = tmp_path / "rosters.json"
    repository = RosterRepository(engine(tmp_path), path)
    repository.save([{"id": "first", "players": []}])
    assert repository.load()[0]["id"] == "first"
    path.write_text('[{"id":"second","players":[]}]', encoding="utf-8")
    assert repository.load()[0]["id"] == "second"


