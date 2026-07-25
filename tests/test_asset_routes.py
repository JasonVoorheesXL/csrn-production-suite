from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pytest

import app as app_module
from asset_service import AssetResult


if not hasattr(app_module, "get_asset_service"):
    pytest.skip(
        "AssetService routes are not integrated yet.",
        allow_module_level=True,
    )


ASSET_ID = "asset-1"


class StubAssetService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.asset = {
            "id": ASSET_ID,
            "name": "CSRN Logo",
            "category": "Organization",
            "asset_type": "Logo",
            "file_url": "",
            "active": True,
        }
        self.duplicate = {
            **self.asset,
            "id": "duplicate",
            "file_url": "/asset-files/existing.png",
            "sha256": "newhash",
        }
        self.list_result = AssetResult("OK", {"assets": [self.asset]})
        self.create_result = AssetResult("OK", {"asset": self.asset})
        self.update_result = AssetResult("OK", {"asset": self.asset})
        self.delete_result = AssetResult(
            "OK",
            {"ok": True, "deleted": ASSET_ID},
        )
        self.read_result = AssetResult("OK", {"asset": self.asset})
        self.attach_result = AssetResult(
            "OK",
            {
                "asset": {
                    **self.asset,
                    "file_url": "/asset-files/asset-1-1234.png",
                }
            },
        )
        self.duplicate_result = None

    def list_records(self, **kwargs) -> AssetResult:
        self.calls.append(("list_records", kwargs))
        return self.list_result

    def create(self, incoming: dict[str, Any]) -> AssetResult:
        self.calls.append(("create", incoming))
        return self.create_result

    def update(self, asset_id: str, incoming: dict[str, Any]) -> AssetResult:
        self.calls.append(("update", (asset_id, incoming)))
        return self.update_result

    def delete(self, asset_id: str) -> AssetResult:
        self.calls.append(("delete", asset_id))
        return self.delete_result

    def read(self, asset_id: str) -> AssetResult:
        self.calls.append(("read", asset_id))
        return self.read_result

    def file_hash(self, path: Path) -> str:
        self.calls.append(("file_hash", path.name))
        return "newhash"

    def duplicate_by_hash(self, sha256: str, *, exclude_id: str = ""):
        self.calls.append(("duplicate_by_hash", (sha256, exclude_id)))
        return self.duplicate_result

    def attach_file(self, asset_id: str, **metadata) -> AssetResult:
        self.calls.append(("attach_file", (asset_id, metadata)))
        return self.attach_result

    def reuse_duplicate(
        self,
        pending_asset_id: str,
        duplicate_asset_id: str,
    ) -> AssetResult:
        self.calls.append(
            ("reuse_duplicate", (pending_asset_id, duplicate_asset_id))
        )
        return AssetResult(
            "OK",
            {
                "asset": self.duplicate,
                "duplicate_asset": self.duplicate,
                "duplicate_reused": True,
                "pending_asset_removed": True,
            },
        )

    def replace_duplicate(
        self,
        pending_asset_id: str,
        duplicate_asset_id: str,
        **metadata,
    ) -> AssetResult:
        self.calls.append(
            (
                "replace_duplicate",
                (pending_asset_id, duplicate_asset_id, metadata),
            )
        )
        replacement = {
            **self.duplicate,
            "file_url": metadata["file_url"],
        }
        return AssetResult(
            "OK",
            {
                "asset": replacement,
                "duplicate_asset": replacement,
                "duplicate_replaced": True,
                "pending_asset_removed": True,
            },
        )


@pytest.fixture
def asset_client(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    service = StubAssetService()
    monkeypatch.setattr(app_module, "ASSET_SERVICE", service, raising=False)
    monkeypatch.setattr(app_module, "pin_is_configured", lambda: True)
    monkeypatch.setattr(app_module, "ASSET_UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(app_module.time, "time", lambda: 1234)
    monkeypatch.setitem(app_module.app.config, "TESTING", True)
    monkeypatch.setitem(app_module.app.config, "SECRET_KEY", "asset-route-test")

    with app_module.app.test_client() as client:
        with client.session_transaction() as active_session:
            active_session["authenticated"] = True
        yield client, service, tmp_path


def test_list_assets_preserves_object_contract_and_filters(asset_client) -> None:
    client, service, _ = asset_client
    response = client.get(
        "/api/assets?include_inactive=false&category=Organization"
        "&asset_type=Logo&rights_status=Verified"
    )
    assert response.status_code == 200
    assert response.get_json() == {"assets": [service.asset]}
    assert service.calls == [
        (
            "list_records",
            {
                "include_inactive": False,
                "category": "Organization",
                "asset_type": "Logo",
                "rights_status": "Verified",
            },
        )
    ]


def test_create_asset_preserves_success_and_validation_contracts(asset_client) -> None:
    client, service, _ = asset_client
    payload = {"name": "CSRN Logo"}
    created = client.post("/api/assets", json=payload)
    assert created.status_code == 200
    assert created.get_json() == {"asset": service.asset}

    service.create_result = AssetResult("ASSET_NAME_REQUIRED")
    missing = client.post("/api/assets", json={})
    assert missing.status_code == 400
    assert missing.get_json() == {"error": "Asset name is required."}


def test_update_and_delete_preserve_missing_contracts(asset_client) -> None:
    client, service, _ = asset_client
    updated = client.put(f"/api/assets/{ASSET_ID}", json={"name": "Updated"})
    assert updated.status_code == 200
    assert updated.get_json() == {"asset": service.asset}

    service.update_result = AssetResult("ASSET_NOT_FOUND")
    missing_update = client.put("/api/assets/missing", json={"name": "Missing"})
    assert missing_update.status_code == 404
    assert missing_update.get_json() == {"error": "Asset not found."}

    deleted = client.delete(f"/api/assets/{ASSET_ID}")
    assert deleted.status_code == 200
    assert deleted.get_json() == {"ok": True}

    service.delete_result = AssetResult("ASSET_NOT_FOUND")
    missing_delete = client.delete("/api/assets/missing")
    assert missing_delete.status_code == 404
    assert missing_delete.get_json() == {"error": "Asset not found."}


def test_upload_validates_file_type_and_saved_record(asset_client) -> None:
    client, service, directory = asset_client
    no_file = client.post(f"/api/assets/{ASSET_ID}/upload", data={})
    assert no_file.status_code == 400
    assert no_file.get_json() == {"error": "Choose a file to upload."}

    unsupported = client.post(
        f"/api/assets/{ASSET_ID}/upload",
        data={"asset": (io.BytesIO(b"bad"), "asset.exe")},
        content_type="multipart/form-data",
    )
    assert unsupported.status_code == 400
    assert unsupported.get_json() == {"error": "Unsupported asset file type."}

    service.read_result = AssetResult("ASSET_NOT_FOUND")
    missing = client.post(
        "/api/assets/missing/upload",
        data={"asset": (io.BytesIO(b"image"), "asset.png")},
        content_type="multipart/form-data",
    )
    assert missing.status_code == 404
    assert missing.get_json() == {
        "error": "Save the asset record before uploading."
    }
    assert list(directory.iterdir()) == []


def test_upload_new_file_links_metadata_through_service(asset_client) -> None:
    client, service, directory = asset_client
    response = client.post(
        f"/api/assets/{ASSET_ID}/upload",
        data={"asset": (io.BytesIO(b"image"), "asset.png")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    assert response.get_json() == {
        "file_url": "/asset-files/asset-1-1234.png",
        "duplicate_asset": None,
        "duplicate_kept": False,
    }
    assert (directory / "asset-1-1234.png").read_bytes() == b"image"
    assert any(call[0] == "attach_file" for call in service.calls)


def test_upload_duplicate_prompt_and_reuse_contracts(asset_client) -> None:
    client, service, directory = asset_client
    service.duplicate_result = service.duplicate

    prompt = client.post(
        f"/api/assets/{ASSET_ID}/upload",
        data={"asset": (io.BytesIO(b"image"), "asset.png")},
        content_type="multipart/form-data",
    )
    assert prompt.status_code == 409
    assert prompt.get_json() == {
        "error": "DUPLICATE_ASSET",
        "duplicate_asset": service.duplicate,
    }
    assert list(directory.iterdir()) == []

    reuse = client.post(
        f"/api/assets/{ASSET_ID}/upload",
        data={
            "asset": (io.BytesIO(b"image"), "asset.png"),
            "duplicate_action": "reuse",
        },
        content_type="multipart/form-data",
    )
    assert reuse.status_code == 200
    assert reuse.get_json()["duplicate_reused"] is True
    assert reuse.get_json()["pending_asset_removed"] is True
    assert list(directory.iterdir()) == []


def test_upload_duplicate_replace_preserves_existing_filename(asset_client) -> None:
    client, service, directory = asset_client
    service.duplicate_result = service.duplicate
    (directory / "existing.png").write_bytes(b"old")

    response = client.post(
        f"/api/assets/{ASSET_ID}/upload",
        data={
            "asset": (io.BytesIO(b"replacement"), "replacement.png"),
            "duplicate_action": "replace",
        },
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    assert response.get_json()["duplicate_replaced"] is True
    assert response.get_json()["file_url"] == "/asset-files/existing.png"
    assert (directory / "existing.png").read_bytes() == b"replacement"
    assert any(call[0] == "replace_duplicate" for call in service.calls)
