from __future__ import annotations

import json
import tempfile
from pathlib import Path

from persistence_engine import DataCorruptionError, DestructiveWriteBlocked, JsonPersistenceEngine, PersistencePolicy
from roster_store import RosterStore


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="csrn-foundation-check-") as raw:
        root = Path(raw)
        data = root / "Data"
        backups = data / "Backups" / "Persistence"
        quarantine = data / "Backups" / "Quarantine"
        engine = JsonPersistenceEngine(backups, quarantine)

        sample = data / "sample.json"
        engine.save(sample, [{"id": "one"}], force=True)
        assert engine.load(sample, []) == [{"id": "one"}]

        guard = PersistencePolicy(block_empty_replacement=True, backup_count=5)
        try:
            engine.save(sample, [], policy=guard)
        except DestructiveWriteBlocked:
            pass
        else:
            raise AssertionError("Empty replacement guard did not activate")

        engine.save(sample, [{"id": "two"}], policy=guard)
        assert list((backups / "sample").glob("*.json")), "Backup was not created"

        sample.write_text("{damaged", encoding="utf-8")
        recovered = engine.load(sample, [])
        assert recovered == [{"id": "one"}], "Newest usable backup was not recovered"
        assert list(quarantine.glob("sample-corrupt-*.json")), "Damaged file was not quarantined"

        roster_file = data / "Rosters" / "rosters.json"
        store = RosterStore(engine, roster_file)
        rosters = [{
            "id": "school-football-2026-varsity-boys",
            "school_id": "school",
            "sport": "Football",
            "season": "2026",
            "level": "Varsity",
            "division": "Boys",
            "players": [{"id": "1-player", "number": "1", "first_name": "Test", "last_name": "Player"}],
        }]
        store.save(rosters, force=True)
        assert store.load() == rosters
        assert store.delete_roster(rosters[0]["id"])
        assert store.load() == []

    print("CSRN v1.13 Foundation self-check: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
