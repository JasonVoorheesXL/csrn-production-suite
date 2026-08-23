from __future__ import annotations

from pathlib import Path

import pytest

from persistence_engine import JsonPersistenceEngine
from venue_repository import (
    VenueRepository,
    VenueRepositoryValidationError,
)


def engine(tmp_path: Path) -> JsonPersistenceEngine:
    return JsonPersistenceEngine(
        tmp_path / "backups",
        tmp_path / "quarantine",
    )


def test_load_accepts_wrapped_payload_and_writes_canonical_list(
    tmp_path: Path,
) -> None:
    path = tmp_path / "venues.json"
    path.write_text(
        """
        {
          "venues": [
            {
              "id": "caledonia-football",
              "name": "Caledonia Football Stadium"
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    repository = VenueRepository(engine(tmp_path), path)
    venues = repository.load()

    assert venues[0]["id"] == "caledonia-football"
    assert path.read_text(encoding="utf-8").lstrip().startswith("[")


def test_save_rejects_duplicate_venue_ids(tmp_path: Path) -> None:
    repository = VenueRepository(
        engine(tmp_path),
        tmp_path / "venues.json",
    )

    with pytest.raises(VenueRepositoryValidationError):
        repository.save(
            [
                {"id": "duplicate", "name": "Venue One"},
                {"id": "duplicate", "name": "Venue Two"},
            ]
        )


def test_save_rejects_non_list_payload(tmp_path: Path) -> None:
    repository = VenueRepository(
        engine(tmp_path),
        tmp_path / "venues.json",
    )

    with pytest.raises(VenueRepositoryValidationError):
        repository.save({"id": "not-a-list"})  # type: ignore[arg-type]


def test_save_rejects_non_object_records(tmp_path: Path) -> None:
    repository = VenueRepository(
        engine(tmp_path),
        tmp_path / "venues.json",
    )

    with pytest.raises(VenueRepositoryValidationError):
        repository.save(["not-an-object"])  # type: ignore[list-item]


def test_get_returns_defensive_copy(tmp_path: Path) -> None:
    repository = VenueRepository(
        engine(tmp_path),
        tmp_path / "venues.json",
    )

    repository.save(
        [
            {
                "id": "venue-1",
                "name": "Original Name",
            }
        ]
    )

    venue = repository.get("venue-1")

    assert venue is not None

    venue["name"] = "Changed Name"

    stored = repository.get("venue-1")

    assert stored is not None
    assert stored["name"] == "Original Name"


def test_invalid_payload_is_quarantined_and_defaulted(
    tmp_path: Path,
) -> None:
    path = tmp_path / "venues.json"
    path.write_text(
        '{"venues":"not-a-list"}',
        encoding="utf-8",
    )

    repository = VenueRepository(engine(tmp_path), path)

    assert repository.load() == []
    assert path.read_text(encoding="utf-8").strip().startswith("[")
    assert list((tmp_path / "quarantine").glob("*.json"))


def test_cache_invalidates_when_file_changes(tmp_path: Path) -> None:
    path = tmp_path / "venues.json"
    repository = VenueRepository(engine(tmp_path), path)

    repository.save(
        [
            {
                "id": "first",
                "name": "First Venue",
            }
        ]
    )

    assert repository.load()[0]["id"] == "first"

    path.write_text(
        '[{"id":"second","name":"Second Venue"}]',
        encoding="utf-8",
    )

    assert repository.load()[0]["id"] == "second"

