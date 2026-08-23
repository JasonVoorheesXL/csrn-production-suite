from __future__ import annotations

import json
from pathlib import Path

import pytest

from broadcast_repository import (
    BroadcastRepository,
    BroadcastRepositoryValidationError,
)
from persistence_engine import JsonPersistenceEngine


def engine(tmp_path: Path) -> JsonPersistenceEngine:
    return JsonPersistenceEngine(
        tmp_path / "backups",
        tmp_path / "quarantine",
    )


def normalize_lifecycle(
    items: list[dict],
) -> bool:
    changed = False

    for item in items:
        if str(item.get("status", "")).lower() == "prepared":
            item["status"] = "planned"
            changed = True

        live_state = item.get("live_state")

        if (
            isinstance(live_state, dict)
            and str(live_state.get("status", "")).lower()
            == "prepared"
        ):
            live_state["status"] = "planned"
            changed = True

    return changed


def test_load_accepts_wrapped_payload_and_writes_canonical_list(
    tmp_path: Path,
) -> None:
    path = tmp_path / "broadcasts.json"
    path.write_text(
        """
        {
          "broadcasts": [
            {
              "broadcast_id": "football-2026-001",
              "status": "planned"
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    repository = BroadcastRepository(
        engine(tmp_path),
        path,
    )

    broadcasts = repository.load()

    assert broadcasts[0]["broadcast_id"] == "football-2026-001"
    assert path.read_text(
        encoding="utf-8"
    ).lstrip().startswith("[")


def test_normalizer_migrates_prepared_lifecycle_and_persists(
    tmp_path: Path,
) -> None:
    path = tmp_path / "broadcasts.json"
    path.write_text(
        """
        [
          {
            "broadcast_id": "football-2026-001",
            "status": "prepared",
            "live_state": {
              "status": "prepared"
            }
          }
        ]
        """,
        encoding="utf-8",
    )

    repository = BroadcastRepository(
        engine(tmp_path),
        path,
        normalizer=normalize_lifecycle,
    )

    broadcasts = repository.load()

    assert broadcasts[0]["status"] == "planned"
    assert broadcasts[0]["live_state"]["status"] == "planned"

    persisted = json.loads(
        path.read_text(encoding="utf-8")
    )

    assert persisted[0]["status"] == "planned"
    assert persisted[0]["live_state"]["status"] == "planned"


def test_save_rejects_duplicate_broadcast_ids(
    tmp_path: Path,
) -> None:
    repository = BroadcastRepository(
        engine(tmp_path),
        tmp_path / "broadcasts.json",
    )

    with pytest.raises(
        BroadcastRepositoryValidationError
    ):
        repository.save(
            [
                {
                    "broadcast_id": "duplicate",
                    "status": "planned",
                },
                {
                    "broadcast_id": "duplicate",
                    "status": "completed",
                },
            ]
        )


def test_save_rejects_non_list_payload(
    tmp_path: Path,
) -> None:
    repository = BroadcastRepository(
        engine(tmp_path),
        tmp_path / "broadcasts.json",
    )

    with pytest.raises(
        BroadcastRepositoryValidationError
    ):
        repository.save(  # type: ignore[arg-type]
            {"broadcast_id": "not-a-list"}
        )


def test_save_rejects_invalid_live_state(
    tmp_path: Path,
) -> None:
    repository = BroadcastRepository(
        engine(tmp_path),
        tmp_path / "broadcasts.json",
    )

    with pytest.raises(
        BroadcastRepositoryValidationError
    ):
        repository.save(
            [
                {
                    "broadcast_id": "broadcast-1",
                    "live_state": "not-an-object",
                }
            ]
        )


def test_get_returns_defensive_copy(
    tmp_path: Path,
) -> None:
    repository = BroadcastRepository(
        engine(tmp_path),
        tmp_path / "broadcasts.json",
    )

    repository.save(
        [
            {
                "broadcast_id": "broadcast-1",
                "status": "planned",
                "live_state": {
                    "home_score": 0,
                },
            }
        ]
    )

    broadcast = repository.get("broadcast-1")

    assert broadcast is not None

    broadcast["status"] = "changed"
    broadcast["live_state"]["home_score"] = 99

    stored = repository.get("broadcast-1")

    assert stored is not None
    assert stored["status"] == "planned"
    assert stored["live_state"]["home_score"] == 0


def test_invalid_payload_is_quarantined_and_defaulted(
    tmp_path: Path,
) -> None:
    path = tmp_path / "broadcasts.json"
    path.write_text(
        '{"broadcasts":"not-a-list"}',
        encoding="utf-8",
    )

    repository = BroadcastRepository(
        engine(tmp_path),
        path,
    )

    assert repository.load() == []

    assert path.read_text(
        encoding="utf-8"
    ).strip().startswith("[")

    assert list(
        (tmp_path / "quarantine").glob("*.json")
    )


def test_cache_invalidates_when_file_changes(
    tmp_path: Path,
) -> None:
    path = tmp_path / "broadcasts.json"

    repository = BroadcastRepository(
        engine(tmp_path),
        path,
    )

    repository.save(
        [
            {
                "broadcast_id": "first",
                "status": "planned",
            }
        ]
    )

    assert (
        repository.load()[0]["broadcast_id"]
        == "first"
    )

    path.write_text(
        """
        [
          {
            "broadcast_id": "second",
            "status": "planned"
          }
        ]
        """,
        encoding="utf-8",
    )

    assert (
        repository.load()[0]["broadcast_id"]
        == "second"
    )


def test_saving_empty_index_remains_allowed(
    tmp_path: Path,
) -> None:
    repository = BroadcastRepository(
        engine(tmp_path),
        tmp_path / "broadcasts.json",
    )

    repository.save(
        [
            {
                "broadcast_id": "broadcast-1",
                "status": "planned",
            }
        ]
    )

    repository.save([])

    assert repository.load() == []

