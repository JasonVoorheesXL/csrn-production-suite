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


def list_validator(value):
    return isinstance(value, list)


def test_save_and_load_round_trip(tmp_path: Path) -> None:
    engine = JsonPersistenceEngine(tmp_path / "backups")
    target = tmp_path / "Data" / "Rosters" / "rosters.json"
    payload = [{"id": "caledonia-football-2026", "players": []}]

    engine.save(target, payload, validator=list_validator)

    assert engine.load(target, [], validator=list_validator) == payload


def test_existing_file_is_snapshotted_before_replacement(tmp_path: Path) -> None:
    engine = JsonPersistenceEngine(tmp_path / "backups")
    target = tmp_path / "rosters.json"
    engine.save(target, [{"id": "one"}], validator=list_validator)
    engine.save(target, [{"id": "one"}, {"id": "two"}], validator=list_validator)

    backups = list((tmp_path / "backups" / "rosters").glob("*.json"))
    assert backups
    assert json.loads(backups[0].read_text(encoding="utf-8")) == [{"id": "one"}]


def test_empty_replacement_is_blocked_for_protected_store(tmp_path: Path) -> None:
    engine = JsonPersistenceEngine(tmp_path / "backups")
    target = tmp_path / "rosters.json"
    policy = PersistencePolicy(block_empty_replacement=True)
    engine.save(target, [{"id": "one"}], validator=list_validator)

    with pytest.raises(DestructiveWriteBlocked):
        engine.save(target, [], validator=list_validator, policy=policy)

    assert engine.load(target, [], validator=list_validator) == [{"id": "one"}]


def test_intentional_empty_reset_requires_force(tmp_path: Path) -> None:
    engine = JsonPersistenceEngine(tmp_path / "backups")
    target = tmp_path / "rosters.json"
    policy = PersistencePolicy(block_empty_replacement=True)
    engine.save(target, [{"id": "one"}], validator=list_validator)

    engine.save(target, [], validator=list_validator, policy=policy, force=True)

    assert engine.load(target, [], validator=list_validator) == []


def test_corruption_is_quarantined_and_latest_backup_is_loaded(tmp_path: Path) -> None:
    engine = JsonPersistenceEngine(tmp_path / "backups")
    target = tmp_path / "rosters.json"
    original = [{"id": "one"}]
    engine.save(target, original, validator=list_validator)
    engine.save(target, original + [{"id": "two"}], validator=list_validator)
    target.write_text("[truncated", encoding="utf-8")

    recovered = engine.load(target, [], validator=list_validator)

    assert recovered == original
    assert list((tmp_path / "backups" / "Quarantine").glob("rosters-corrupt-*.json"))
    assert target.read_text(encoding="utf-8") == "[truncated"


def test_corruption_without_backup_raises_and_preserves_evidence(tmp_path: Path) -> None:
    engine = JsonPersistenceEngine(tmp_path / "backups")
    target = tmp_path / "rosters.json"
    target.write_text("not-json", encoding="utf-8")

    with pytest.raises(DataCorruptionError):
        engine.load(target, [], validator=list_validator)

    assert target.read_text(encoding="utf-8") == "not-json"
    assert list((tmp_path / "backups" / "Quarantine").glob("rosters-corrupt-*.json"))


def test_large_record_drop_can_be_blocked(tmp_path: Path) -> None:
    engine = JsonPersistenceEngine(tmp_path / "backups")
    target = tmp_path / "rosters.json"
    policy = PersistencePolicy(block_large_count_drop=True, max_count_drop_ratio=0.75)
    engine.save(target, [{"id": str(i)} for i in range(8)], validator=list_validator)

    with pytest.raises(DestructiveWriteBlocked):
        engine.save(target, [{"id": "0"}], validator=list_validator, policy=policy)
