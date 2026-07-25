from __future__ import annotations

import copy
from pathlib import Path

from asset_service import AssetService


class Store:
    def __init__(self, rows=None) -> None:
        self.rows = copy.deepcopy(rows or [])
        self.saved: list[list[dict]] = []

    def load(self):
        return copy.deepcopy(self.rows)

    def save(self, rows):
        self.rows = copy.deepcopy(rows)
        self.saved.append(copy.deepcopy(rows))


def service(store: Store, *, now: float = 1000.0) -> AssetService:
    return AssetService(
        load_assets=store.load,
        save_assets=store.save,
        clock=lambda: now,
    )


def asset(asset_id: str = "logo-1") -> dict:
    return {
        "id": asset_id,
        "name": "Primary Logo",
        "category": "School",
        "asset_type": "Logo",
        "file_url": "/asset-files/logo.png",
        "source_url": "",
        "rights_status": "Verified",
        "rights_owner": "Caledonia",
        "notes": "",
        "active": True,
        "sha256": "abc123",
        "original_filename": "logo.png",
        "created_at": 900,
        "updated_at": 900,
    }


def test_normalize_id_extension_and_hash(tmp_path: Path) -> None:
    assert AssetService.normalize_id(" Primary Logo! ") == "Primary-Logo"
    assert AssetService.normalize_id("") == "asset"
    assert AssetService.extension_allowed("clip.MP4") is True
    assert AssetService.extension_allowed("script.exe") is False

    payload = tmp_path / "asset.bin"
    payload.write_bytes(b"csrn")
    assert AssetService.file_hash(payload) == (
        "e0985b9974f69f123986e42e45125fff64baa8d298c2ef219e0b369016b25e09"
    )


def test_migrate_legacy_record_adds_canonical_defaults() -> None:
    migrated = AssetService.migrate_record(
        {
            "id": "legacy",
            "name": "Legacy",
            "active": "false",
        }
    )
    assert migrated["id"] == "legacy"
    assert migrated["category"] == "Other"
    assert migrated["asset_type"] == "Other"
    assert migrated["rights_status"] == "Unverified"
    assert migrated["active"] is False


def test_list_records_filters_and_sorts() -> None:
    inactive = asset("z")
    inactive.update(
        {
            "name": "Zed",
            "active": False,
            "category": "Sponsor",
            "rights_status": "Unverified",
        }
    )
    active = asset("a")
    active["name"] = "Alpha"
    store = Store([inactive, active])

    visible = service(store).list_records(include_inactive=False)
    assert [row["id"] for row in visible.data["assets"]] == ["a"]

    filtered = service(store).list_records(
        category="Sponsor",
        asset_type="Logo",
        rights_status="Unverified",
    )
    assert [row["id"] for row in filtered.data["assets"]] == ["z"]


def test_create_requires_name_and_generates_unique_id() -> None:
    store = Store([asset("asset-1000000")])
    subject = service(store)
    assert subject.create({}).code == "ASSET_NAME_REQUIRED"

    created = subject.create(
        {
            "name": "Second Asset",
            "category": "Sponsor",
            "asset_type": "Logo",
        }
    )
    assert created.ok
    assert created.data["asset"]["id"] == "asset-1000000-2"
    assert created.data["asset"]["created_at"] == 1000
    assert len(store.rows) == 2


def test_create_preserves_explicit_id_when_available() -> None:
    store = Store()
    result = service(store).create(
        {
            "id": "custom-id",
            "name": "Custom",
        }
    )
    assert result.data["asset"]["id"] == "custom-id"


def test_read_update_and_missing_contracts() -> None:
    store = Store([asset()])
    subject = service(store, now=1100)
    assert subject.read("missing").code == "ASSET_NOT_FOUND"
    assert subject.update("missing", {"name": "Missing"}).code == "ASSET_NOT_FOUND"

    updated = subject.update(
        "logo-1",
        {
            "name": "Updated Logo",
            "rights_status": "Approved",
        },
    )
    assert updated.ok
    assert updated.data["asset"]["id"] == "logo-1"
    assert updated.data["asset"]["created_at"] == 900
    assert updated.data["asset"]["updated_at"] == 1100
    assert store.rows[0]["name"] == "Updated Logo"


def test_update_rejects_empty_name() -> None:
    result = service(Store([asset()])).update("logo-1", {"name": ""})
    assert result.code == "ASSET_NAME_REQUIRED"


def test_delete_existing_and_missing_asset() -> None:
    store = Store([asset()])
    subject = service(store)
    deleted = subject.delete("logo-1")
    assert deleted.data == {"ok": True, "deleted": "logo-1"}
    assert store.rows == []
    assert subject.delete("logo-1").code == "ASSET_NOT_FOUND"


def test_duplicate_by_hash_ignores_excluded_and_inactive_records() -> None:
    current = asset("current")
    duplicate = asset("duplicate")
    inactive = asset("inactive")
    inactive["active"] = False
    subject = service(Store([current, duplicate, inactive]))

    found = subject.duplicate_by_hash("ABC123", exclude_id="current")
    assert found is not None
    assert found["id"] == "duplicate"
    assert subject.duplicate_by_hash("missing") is None


def test_attach_file_updates_metadata() -> None:
    store = Store([asset()])
    result = service(store, now=1200).attach_file(
        "logo-1",
        file_url="/asset-files/logo-new.png",
        sha256="newhash",
        original_filename="new.png",
    )
    assert result.ok
    assert result.data["asset"]["file_url"] == "/asset-files/logo-new.png"
    assert store.rows[0]["updated_at"] == 1200
    assert service(store).attach_file(
        "missing",
        file_url="/asset-files/x.png",
        sha256="x",
        original_filename="x.png",
    ).code == "ASSET_NOT_FOUND"


def test_reuse_duplicate_removes_pending_record() -> None:
    pending = asset("pending")
    duplicate = asset("duplicate")
    store = Store([pending, duplicate])
    result = service(store).reuse_duplicate("pending", "duplicate")
    assert result.ok
    assert result.data["asset"]["id"] == "duplicate"
    assert result.data["duplicate_reused"] is True
    assert [row["id"] for row in store.rows] == ["duplicate"]


def test_replace_duplicate_updates_existing_and_removes_pending() -> None:
    pending = asset("pending")
    duplicate = asset("duplicate")
    store = Store([pending, duplicate])
    result = service(store, now=1300).replace_duplicate(
        "pending",
        "duplicate",
        file_url="/asset-files/replaced.png",
        sha256="replacement",
        original_filename="replacement.png",
    )
    assert result.ok
    assert result.data["duplicate_replaced"] is True
    assert [row["id"] for row in store.rows] == ["duplicate"]
    assert store.rows[0]["sha256"] == "replacement"
    assert store.rows[0]["updated_at"] == 1300


def test_duplicate_operations_report_missing_records() -> None:
    subject = service(Store([asset("duplicate")]))
    assert subject.reuse_duplicate("missing", "duplicate").code == "ASSET_NOT_FOUND"
    assert subject.reuse_duplicate("duplicate", "missing").code == "DUPLICATE_ASSET_NOT_FOUND"
    assert subject.replace_duplicate(
        "missing",
        "duplicate",
        file_url="",
        sha256="",
        original_filename="",
    ).code == "ASSET_NOT_FOUND"
