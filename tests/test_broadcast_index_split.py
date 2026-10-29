"""The broadcast index (broadcasts.json) is a lightweight list; each game's
live_state and final_state_archive live only in Data/Broadcasts/<id>.json.

Covers the detail store's merge rules, the repository's strip-on-save and
legacy migration (backup first, never lose a copy), the per-play writer
holding the app lock only for the small index write, and the readers that
used to find live_state on index rows.
"""

from __future__ import annotations

import copy
import json
from contextlib import nullcontext
from pathlib import Path
from typing import Any

import pytest

import app as app_module
from broadcast_detail_store import BroadcastDetailStore, split_heavy_fields
from broadcast_lifecycle_service import BroadcastLifecycleService
from broadcast_repository import BroadcastRepository
from maxpreps_export_service import MaxPrepsExportService
from persistence_engine import JsonPersistenceEngine
from social_media_preview_service import SocialMediaPreviewService


BID = "FB-2026-TEST-W01-001"


def game(revision: int, plays: int, *, broadcast_id: str = BID, status: str = "live") -> dict[str, Any]:
    return {
        "broadcast_id": broadcast_id,
        "status": status,
        "state_revision": revision,
        "events": [{"id": f"e{n}"} for n in range(plays)],
        "plays": [{"play_id": f"p{n}"} for n in range(plays)],
        "history": [],
    }


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


# -- detail store -----------------------------------------------------------


def test_split_heavy_fields_separates_without_mutating() -> None:
    row = {"broadcast_id": BID, "status": "live", "live_state": {"a": 1}, "final_state_archive": {"b": 2}}
    light, heavy = split_heavy_fields(row)
    assert light == {"broadcast_id": BID, "status": "live"}
    assert heavy == {"live_state": {"a": 1}, "final_state_archive": {"b": 2}}
    assert "live_state" in row


def test_detail_store_light_write_keeps_heavy_fields_already_on_disk(tmp_path) -> None:
    store = BroadcastDetailStore(tmp_path)
    store.write({"broadcast_id": BID, "status": "live"}, heavy={"live_state": game(5, 3), "final_state_archive": game(4, 3)})

    store.write({"broadcast_id": BID, "status": "completed", "notes": "edited in Game Manager"})

    detail = read_json(tmp_path / f"{BID}.json")
    assert detail["status"] == "completed"
    assert detail["notes"] == "edited in Game Manager"
    assert detail["live_state"] == game(5, 3)
    assert detail["final_state_archive"] == game(4, 3)
    assert not list(tmp_path.glob("*.tmp")), "atomic write must not leave temp files"


def test_detail_store_supplied_heavy_field_replaces_only_that_field(tmp_path) -> None:
    store = BroadcastDetailStore(tmp_path)
    store.write({"broadcast_id": BID}, heavy={"live_state": game(5, 3), "final_state_archive": game(4, 3)})

    store.write({"broadcast_id": BID, "live_state": game(9, 0)})

    assert store.load_field(BID, "live_state") == game(9, 0)
    assert store.load_field(BID, "final_state_archive") == game(4, 3)


def test_detail_store_existing_only_does_not_create(tmp_path) -> None:
    store = BroadcastDetailStore(tmp_path)
    assert store.write({"broadcast_id": BID}, existing_only=True) is False
    assert not (tmp_path / f"{BID}.json").exists()


def test_detail_store_resolves_a_callable_directory_at_call_time(tmp_path) -> None:
    current = {"dir": tmp_path / "one"}
    store = BroadcastDetailStore(lambda: current["dir"])
    store.write({"broadcast_id": BID})
    current["dir"] = tmp_path / "two"
    store.write({"broadcast_id": BID})
    assert (tmp_path / "one" / f"{BID}.json").exists()
    assert (tmp_path / "two" / f"{BID}.json").exists()


# -- repository -------------------------------------------------------------


def make_repository(tmp_path: Path, spilled: list, backups: list, **overrides: Any) -> BroadcastRepository:
    def spill(row: dict[str, Any], migrating: bool) -> None:
        spilled.append((copy.deepcopy(row), migrating))

    def backup(path: Path) -> None:
        backups.append(path.read_bytes())

    options: dict[str, Any] = {"spill_heavy": spill, "backup_before_migration": backup}
    options.update(overrides)
    return BroadcastRepository(
        JsonPersistenceEngine(tmp_path / "backups"),
        tmp_path / "broadcasts.json",
        **options,
    )


def test_repository_save_hands_heavy_fields_over_and_writes_a_light_index(tmp_path) -> None:
    spilled: list = []
    repository = make_repository(tmp_path, spilled, [])
    repository.save([{"broadcast_id": BID, "status": "live", "live_state": game(3, 1)}])

    on_disk = read_json(tmp_path / "broadcasts.json")
    assert on_disk == [{"broadcast_id": BID, "status": "live"}]
    assert spilled == [({"broadcast_id": BID, "status": "live", "live_state": game(3, 1)}, False)]
    assert repository.load() == [{"broadcast_id": BID, "status": "live"}]


def test_repository_migrates_a_legacy_heavy_index_after_backing_it_up(tmp_path) -> None:
    legacy = [
        {"broadcast_id": BID, "status": "completed", "live_state": game(9, 0), "final_state_archive": game(8, 4)},
        {"broadcast_id": "OTHER", "status": "planned"},
    ]
    raw = json.dumps(legacy).encode("utf-8")
    (tmp_path / "broadcasts.json").write_bytes(raw)
    spilled: list = []
    backups: list = []
    repository = make_repository(tmp_path, spilled, backups)

    rows = repository.load()

    assert backups == [raw], "the legacy file must be backed up before anything changes"
    assert [migrating for _, migrating in spilled] == [True]
    assert spilled[0][0]["final_state_archive"] == game(8, 4)
    assert rows == [
        {"broadcast_id": BID, "status": "completed"},
        {"broadcast_id": "OTHER", "status": "planned"},
    ]
    assert read_json(tmp_path / "broadcasts.json") == rows


@pytest.mark.parametrize("failing", ["backup", "spill"])
def test_repository_leaves_the_legacy_index_alone_when_migration_fails(tmp_path, failing) -> None:
    legacy = [{"broadcast_id": BID, "status": "completed", "final_state_archive": game(8, 4)}]
    raw = json.dumps(legacy).encode("utf-8")
    (tmp_path / "broadcasts.json").write_bytes(raw)

    def boom(*_args: Any) -> None:
        raise OSError("disk full")

    override = {"backup_before_migration": boom} if failing == "backup" else {"spill_heavy": boom}
    repository = make_repository(tmp_path, [], [], **override)

    assert repository.load() == legacy, "callers still get the full legacy rows"
    assert (tmp_path / "broadcasts.json").read_bytes() == raw


def test_repository_keeps_heavy_fields_on_a_row_without_an_id(tmp_path) -> None:
    spilled: list = []
    repository = make_repository(tmp_path, spilled, [])
    repository.save([{"status": "draft", "live_state": game(1, 0)}])
    assert spilled == []
    assert read_json(tmp_path / "broadcasts.json") == [{"status": "draft", "live_state": game(1, 0)}]


def test_repository_without_a_spill_hook_keeps_the_legacy_shape(tmp_path) -> None:
    repository = BroadcastRepository(JsonPersistenceEngine(tmp_path / "b"), tmp_path / "broadcasts.json")
    repository.save([{"broadcast_id": BID, "live_state": game(1, 0)}])
    assert read_json(tmp_path / "broadcasts.json")[0]["live_state"] == game(1, 0)


def test_validation_rejects_a_non_object_final_state_archive() -> None:
    assert BroadcastRepository.validate_items([{"broadcast_id": BID, "final_state_archive": game(1, 1)}])
    assert not BroadcastRepository.validate_items([{"broadcast_id": BID, "final_state_archive": "lost"}])
    assert not BroadcastRepository.validate_items([{"broadcast_id": BID, "live_state": []}])


# -- app wiring -------------------------------------------------------------


@pytest.fixture()
def app_data(tmp_path, monkeypatch):
    data_dir = tmp_path / "Data"
    broadcasts_dir = data_dir / "Broadcasts"
    broadcasts_dir.mkdir(parents=True)
    backup_root = tmp_path / "LocalBackups"
    monkeypatch.setattr(app_module, "DATA_DIR", data_dir)
    monkeypatch.setattr(app_module, "CORE_BACKUP_ROOT", backup_root)
    repository = BroadcastRepository(
        JsonPersistenceEngine(backup_root / "Core"),
        broadcasts_dir / "broadcasts.json",
        normalizer=app_module._normalize_broadcast_lifecycle,
        spill_heavy=app_module._spill_broadcast_heavy_fields,
        backup_before_migration=app_module._backup_broadcast_index_before_migration,
    )
    monkeypatch.setattr(app_module, "BROADCAST_REPOSITORY", repository)
    return {
        "dir": broadcasts_dir,
        "index": broadcasts_dir / "broadcasts.json",
        "migrations": backup_root / "Migrations",
        "repository": repository,
    }


def write_legacy(app_data: dict, rows: list, details: dict | None = None) -> bytes:
    for broadcast_id, detail in (details or {}).items():
        (app_data["dir"] / f"{broadcast_id}.json").write_text(json.dumps(detail), encoding="utf-8")
    raw = json.dumps(rows, indent=2).encode("utf-8")
    app_data["index"].write_bytes(raw)
    return raw


def test_app_migration_moves_state_into_detail_files_and_keeps_a_verified_backup(app_data) -> None:
    legacy = [
        {"broadcast_id": BID, "status": "completed", "updated_at": 10, "live_state": game(9, 0), "final_state_archive": game(8, 4)},
        {"broadcast_id": "FB-2026-TEST-W02-001", "status": "live", "updated_at": 11, "live_state": game(3, 2, broadcast_id="FB-2026-TEST-W02-001")},
    ]
    raw = write_legacy(app_data, legacy)

    rows = app_module.load_broadcasts()

    assert all("live_state" not in row and "final_state_archive" not in row for row in rows)
    assert all("live_state" not in row and "final_state_archive" not in row for row in read_json(app_data["index"]))
    assert app_module.load_final_state_archive(BID) == game(8, 4)
    assert app_module.load_broadcast_live_state(BID) == game(9, 0)
    assert app_module.load_broadcast_live_state("FB-2026-TEST-W02-001") == game(3, 2, broadcast_id="FB-2026-TEST-W02-001")
    backups = list(app_data["migrations"].glob("broadcasts-pre-index-split-*.json"))
    assert [path.read_bytes() for path in backups] == [raw]
    # A second load finds nothing left to migrate.
    app_module.BROADCAST_REPOSITORY.invalidate_cache()
    app_module.load_broadcasts()
    assert len(list(app_data["migrations"].glob("broadcasts-pre-index-split-*.json"))) == 1


def test_app_migration_keeps_the_newer_live_state_and_preserves_the_other(app_data) -> None:
    # The real Amory row: the index still held the pre-Final live_state (all
    # the plays) while the detail held the newer, cleared one.
    index_live = game(592, 145, status="completed")
    detail_live = game(1402, 0, status="completed")
    archive = game(592, 145, status="completed")
    write_legacy(
        app_data,
        [{"broadcast_id": BID, "status": "completed", "updated_at": 50, "live_state": index_live, "final_state_archive": archive}],
        {BID: {"broadcast_id": BID, "status": "completed", "updated_at": 50, "live_state": detail_live, "final_state_archive": archive}},
    )

    app_module.load_broadcasts()

    assert app_module.load_broadcast_live_state(BID) == detail_live
    assert app_module.load_final_state_archive(BID) == archive
    displaced = list(app_data["migrations"].glob(f"{BID}-live_state-displaced-*.json"))
    assert [read_json(path) for path in displaced] == [index_live]


def test_app_migration_never_trades_an_archive_for_one_with_fewer_plays(app_data) -> None:
    full = game(100, 120, status="completed")
    truncated = game(200, 10, status="completed")
    write_legacy(
        app_data,
        [{"broadcast_id": BID, "status": "completed", "updated_at": 5, "final_state_archive": full}],
        {BID: {"broadcast_id": BID, "status": "completed", "updated_at": 5, "final_state_archive": truncated}},
    )

    app_module.load_broadcasts()

    assert app_module.load_final_state_archive(BID) == full
    displaced = list(app_data["migrations"].glob(f"{BID}-final_state_archive-displaced-*.json"))
    assert [read_json(path) for path in displaced] == [truncated]


def test_app_migration_prefers_state_that_belongs_to_the_broadcast(app_data) -> None:
    stray = game(5000, 50, broadcast_id="SOME-OTHER-GAME")
    own = game(10, 5)
    write_legacy(
        app_data,
        [{"broadcast_id": BID, "status": "live", "updated_at": 5, "live_state": own}],
        {BID: {"broadcast_id": BID, "status": "live", "updated_at": 5, "live_state": stray}},
    )
    app_module.load_broadcasts()
    assert app_module.load_broadcast_live_state(BID) == own


def test_linked_snapshot_writes_live_state_to_the_detail_file_only(app_data) -> None:
    app_module.save_broadcasts([{"broadcast_id": BID, "status": "planned"}])
    app_module.write_broadcast_detail({"broadcast_id": BID, "status": "planned"})
    app_module.write_broadcast_detail({"broadcast_id": BID, "final_state_archive": game(1, 7)})

    app_module.persist_linked_state_snapshot(game(2, 3))

    index_row = read_json(app_data["index"])[0]
    assert index_row["status"] == "live"
    assert "live_state" not in index_row and "final_state_archive" not in index_row
    detail = read_json(app_data["dir"] / f"{BID}.json")
    assert detail["live_state"] == game(2, 3)
    assert detail["final_state_archive"] == game(1, 7), "a live snapshot must not drop an existing archive"
    assert detail["status"] == "live"


def test_linked_snapshot_holds_the_app_lock_only_for_the_index_write(app_data, monkeypatch) -> None:
    app_module.save_broadcasts([{"broadcast_id": BID, "status": "planned"}])
    seen: dict[str, bool] = {}
    real_save = app_module.save_broadcasts
    real_detail = app_module.write_broadcast_detail

    def save(items, **kwargs):
        seen["index_under_lock"] = app_module.lock.locked()
        return real_save(items, **kwargs)

    def detail(record, existing_only=False):
        seen["detail_under_lock"] = app_module.lock.locked()
        return real_detail(record, existing_only)

    monkeypatch.setattr(app_module, "save_broadcasts", save)
    monkeypatch.setattr(app_module, "write_broadcast_detail", detail)

    app_module.persist_linked_state_snapshot(game(2, 3))

    assert seen == {"index_under_lock": True, "detail_under_lock": False}


def test_final_archive_then_cleared_live_snapshot_keeps_the_archive(app_data) -> None:
    app_module.save_broadcasts([{"broadcast_id": BID, "status": "live"}])
    final = game(40, 12, status="completed")

    with app_module.lock:
        assert app_module.write_broadcast_final_archive(final) is True
    cleared = game(41, 0, status="completed")
    app_module.persist_linked_state_snapshot(cleared)
    # Game Manager edit afterwards writes only the light row.
    app_module.write_broadcast_detail({"broadcast_id": BID, "status": "completed", "notes": "x"})

    index_row = read_json(app_data["index"])[0]
    assert "final_state_archive" not in index_row and "live_state" not in index_row
    assert index_row["final_state_archived_at"]
    assert app_module.load_final_state_archive(BID) == final
    assert app_module.load_broadcast_live_state(BID) == cleared


def test_index_stays_light_after_many_snapshots(app_data) -> None:
    app_module.save_broadcasts([{"broadcast_id": BID, "status": "planned"}])
    for revision in range(1, 6):
        app_module.persist_linked_state_snapshot(game(revision, 200))
    assert app_data["index"].stat().st_size < 1_000
    assert app_module.load_broadcast_live_state(BID)["state_revision"] == 5


# -- readers ----------------------------------------------------------------


def test_lifecycle_load_resumes_from_the_detail_file_live_state() -> None:
    saved: list = []
    snapshot = game(77, 4)
    service = BroadcastLifecycleService(
        load_broadcasts=lambda: [{"broadcast_id": BID, "status": "live"}],
        load_packages=lambda: [],
        load_state=lambda: {"broadcast_id": ""},
        save_state=lambda state: saved.append(copy.deepcopy(dict(state))),
        normalize_state=lambda state: dict(state),
        default_state=lambda: {"broadcast_id": ""},
        get_school=lambda _sid: None,
        build_identity=lambda _school, _sport: {},
        readiness=lambda: {},
        update_linked_status=lambda *_args: None,
        load_config=lambda: {},
        command_scorebug_visibility=lambda _visible: {},
        public_state=lambda state: state,
        resume_record=lambda _bid: None,
        transaction_lock=nullcontext(),
        load_live_state=lambda broadcast_id: snapshot if broadcast_id == BID else None,
    )

    result = service.load(BID)

    assert result.ok
    assert result.data["state"]["state_revision"] == 77
    assert len(result.data["state"]["plays"]) == 4
    assert saved[-1]["state_revision"] == 77


def test_maxpreps_and_social_use_the_detail_live_state_when_the_row_has_none() -> None:
    mirror = game(30, 6)
    row = {"broadcast_id": BID}
    maxpreps = MaxPrepsExportService(
        load_broadcasts=lambda: [row],
        load_state=lambda: {"broadcast_id": "SOMETHING-ELSE"},
        load_final_state_archive=lambda _bid: None,
        load_live_state=lambda broadcast_id: mirror if broadcast_id == BID else None,
        get_statistics_service=lambda: None,
    )
    assert maxpreps._resolve_game_state(row) == mirror

    social = SocialMediaPreviewService(
        load_broadcasts=lambda: [row],
        load_state=lambda: {"broadcast_id": "SOMETHING-ELSE"},
        load_final_state_archive=lambda _bid: None,
        load_live_state=lambda broadcast_id: mirror if broadcast_id == BID else None,
        get_school_logo_file=lambda *_args: Path("missing"),
        get_asset_upload_dir=lambda: Path("missing"),
        get_sponsor_service=lambda: None,
        get_theme_service=lambda: None,
        build_statistics=lambda _state: {},
        load_config=lambda: {},
        get_storylines=lambda _bid: [],
        get_static_dir=lambda: Path("missing"),
        output_dir=Path("missing"),
    )
    assert social._resolve_game_state(row) == mirror
