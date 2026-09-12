from __future__ import annotations

import json
from pathlib import Path

import pytest

from persistence_engine import JsonPersistenceEngine
from sponsor_repository import (
    SponsorRepository,
    SponsorRepositoryValidationError,
)


def engine(tmp_path: Path) -> JsonPersistenceEngine:
    return JsonPersistenceEngine(
        tmp_path / "backups",
        tmp_path / "quarantine",
    )


def test_load_accepts_wrapped_payload_and_writes_canonical_list(
    tmp_path: Path,
) -> None:
    path = tmp_path / "sponsors.json"
    path.write_text(
        """
        {
          "sponsors": [
            {
              "id": "sponsor-1",
              "name": "Example Sponsor"
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    repository = SponsorRepository(engine(tmp_path), path)
    sponsors = repository.load()

    assert sponsors[0]["id"] == "sponsor-1"
    assert path.read_text(encoding="utf-8").lstrip().startswith("[")


def test_save_removes_runtime_contract_fields(tmp_path: Path) -> None:
    path = tmp_path / "sponsors.json"
    repository = SponsorRepository(engine(tmp_path), path)

    repository.save(
        [
            {
                "id": "sponsor-1",
                "name": "Example Sponsor",
                "effective_status": "Active",
                "contract_expired": False,
            }
        ]
    )

    payload = json.loads(path.read_text(encoding="utf-8"))

    assert "effective_status" not in payload[0]
    assert "contract_expired" not in payload[0]


def test_normalizer_runs_on_load_and_its_changes_are_persisted(tmp_path: Path) -> None:
    # Round 27: the SponsorRepository normalizer slot is how the sport-family
    # backfill reaches existing databases.
    path = tmp_path / "sponsors.json"
    path.write_text(json.dumps([{"id": "s1", "name": "Legacy"}]), encoding="utf-8")

    def stamp_sport(items: list[dict]) -> bool:
        changed = False
        for item in items:
            if "sport" not in item:
                item["sport"] = "football"
                changed = True
        return changed

    repository = SponsorRepository(engine(tmp_path), path, normalizer=stamp_sport)

    assert repository.load()[0]["sport"] == "football"
    # Persisted, so a plain re-read / the next process sees it too.
    assert json.loads(path.read_text(encoding="utf-8"))[0]["sport"] == "football"


def test_save_rejects_duplicate_sponsor_ids(tmp_path: Path) -> None:
    repository = SponsorRepository(
        engine(tmp_path),
        tmp_path / "sponsors.json",
    )

    with pytest.raises(SponsorRepositoryValidationError):
        repository.save(
            [
                {"id": "duplicate", "name": "Sponsor One"},
                {"id": "duplicate", "name": "Sponsor Two"},
            ]
        )


def test_save_rejects_non_list_payload(tmp_path: Path) -> None:
    repository = SponsorRepository(
        engine(tmp_path),
        tmp_path / "sponsors.json",
    )

    with pytest.raises(SponsorRepositoryValidationError):
        repository.save({"id": "not-a-list"})  # type: ignore[arg-type]


def test_get_returns_defensive_copy(tmp_path: Path) -> None:
    repository = SponsorRepository(
        engine(tmp_path),
        tmp_path / "sponsors.json",
    )

    repository.save(
        [
            {
                "id": "sponsor-1",
                "name": "Original Name",
            }
        ]
    )

    sponsor = repository.get("sponsor-1")

    assert sponsor is not None

    sponsor["name"] = "Changed Name"

    assert repository.get("sponsor-1")["name"] == "Original Name"


def test_invalid_payload_is_quarantined_and_defaulted(
    tmp_path: Path,
) -> None:
    path = tmp_path / "sponsors.json"
    path.write_text(
        '{"sponsors":"not-a-list"}',
        encoding="utf-8",
    )

    repository = SponsorRepository(engine(tmp_path), path)

    assert repository.load() == []
    assert path.read_text(encoding="utf-8").strip().startswith("[")
    assert list((tmp_path / "quarantine").glob("*.json"))


def test_cache_invalidates_when_file_changes(tmp_path: Path) -> None:
    path = tmp_path / "sponsors.json"
    repository = SponsorRepository(engine(tmp_path), path)

    repository.save(
        [
            {
                "id": "first",
                "name": "First Sponsor",
            }
        ]
    )

    assert repository.load()[0]["id"] == "first"

    path.write_text(
        '[{"id":"second","name":"Second Sponsor"}]',
        encoding="utf-8",
    )

    assert repository.load()[0]["id"] == "second"

