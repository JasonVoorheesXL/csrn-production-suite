from __future__ import annotations

import json
from pathlib import Path

import pytest

from persistence_engine import (
    DataCorruptionError,
    DestructiveWriteBlocked,
    JsonPersistenceEngine,
    PersistencePolicy,
)


def is_list(value):
    return isinstance(value, list)


def test_round_trip(tmp_path: Path) -> None:
    engine = JsonPersistenceEngine(tmp_path / "Backups")
    target = tmp_path / "Data" / "Rosters" / "rosters.json"
    payload = [{"id": "caledonia-football-2026", "players": []}]

    engine.save(target, payload, validator=is_list)

    assert engine.load(target, [], validator=is_list) == payload


def test_existing_file_is_backed_up_before_replace(tmp_path: Path) -> None:
    engine = JsonPersistenceEngine(tmp_path / "Backups")
    target = tmp_path / "schools.json"
    engine.save(target, [{"id": "one"}], validator=is_list)
    engine.save(target, [{"id": "one"}, {"id": "two"}], validator=is_list)

    backups = list((tmp_path / "Backups" / "schools").glob("*.json"))
    assert len(backups) == 1
    assert json.loads(backups[0].read_text(encoding="utf-8")) == [{"id": "one"}]


def test_empty_replacement_is_blocked(tmp_path: Path) -> None:
    engine = JsonPersistenceEngine(tmp_path / "Backups")
    target = tmp_path / "rosters.json"
    policy = PersistencePolicy(block_empty_replacement=True)
    engine.save(target, [{"id": "one"}], validator=is_list)

    with pytest.raises(DestructiveWriteBlocked):
        engine.save(target, [], validator=is_list, policy=policy)

    assert engine.load(target, [], validator=is_list) == [{"id": "one"}]


def test_force_allows_intentional_reset(tmp_path: Path) -> None:
    engine = JsonPersistenceEngine(tmp_path / "Backups")
    target = tmp_path / "rosters.json"
    policy = PersistencePolicy(block_empty_replacement=True)
    engine.save(target, [{"id": "one"}], validator=is_list)

    engine.save(target, [], validator=is_list, policy=policy, force=True)

    assert engine.load(target, [], validator=is_list) == []


def test_large_record_drop_is_blocked(tmp_path: Path) -> None:
    engine = JsonPersistenceEngine(tmp_path / "Backups")
    target = tmp_path / "schools.json"
    policy = PersistencePolicy(
        block_large_count_drop=True,
        max_count_drop_ratio=0.75,
    )
    engine.save(target, [{"id": str(index)} for index in range(8)], validator=is_list)

    with pytest.raises(DestructiveWriteBlocked):
        engine.save(target, [{"id": "0"}], validator=is_list, policy=policy)


def test_corruption_is_quarantined_and_recovered(tmp_path: Path) -> None:
    engine = JsonPersistenceEngine(tmp_path / "Backups")
    target = tmp_path / "broadcasts.json"
    first = [{"broadcast_id": "one"}]
    second = first + [{"broadcast_id": "two"}]
    engine.save(target, first, validator=is_list)
    engine.save(target, second, validator=is_list)
    target.write_text("[truncated", encoding="utf-8")

    recovered = engine.load(target, [], validator=is_list)

    assert recovered == first
    assert json.loads(target.read_text(encoding="utf-8")) == first
    quarantine = tmp_path / "Backups" / "Quarantine"
    assert list(quarantine.glob("broadcasts-corrupt-*.json"))


def test_corruption_without_backup_raises(tmp_path: Path) -> None:
    engine = JsonPersistenceEngine(tmp_path / "Backups")
    target = tmp_path / "state.json"
    target.write_text("not-json", encoding="utf-8")

    with pytest.raises(DataCorruptionError):
        engine.load(target, {}, validator=lambda value: isinstance(value, dict))

    assert target.read_text(encoding="utf-8") == "not-json"
    assert list((tmp_path / "Backups" / "Quarantine").glob("state-corrupt-*.json"))


def test_backup_rotation(tmp_path: Path) -> None:
    engine = JsonPersistenceEngine(tmp_path / "Backups")
    target = tmp_path / "assets.json"
    policy = PersistencePolicy(backup_count=2)
    engine.save(target, [{"id": "0"}], validator=is_list, policy=policy)
    for index in range(1, 5):
        engine.save(target, [{"id": str(index)}], validator=is_list, policy=policy)

    assert len(list((tmp_path / "Backups" / "assets").glob("*.json"))) == 2


def test_invalid_outgoing_data_is_rejected(tmp_path: Path) -> None:
    engine = JsonPersistenceEngine(tmp_path / "Backups")
    target = tmp_path / "rosters.json"

    with pytest.raises(DataCorruptionError):
        engine.save(target, {"not": "a list"}, validator=is_list)

    assert not target.exists()
