from __future__ import annotations

import io
from dataclasses import dataclass
from functools import wraps
from pathlib import Path
from typing import Any, Callable

import pytest
from flask import Flask, jsonify, request

from routes.asset_routes import AssetRoutesDependencies, create_asset_blueprint


@dataclass(frozen=True)
class StubResult:
    code: str
    data: dict[str, Any]


class StubAssetService:
    def __init__(self) -> None:
        self.asset = {"id": "asset-one", "name": "Logo", "file_url": ""}
        self.list_result = StubResult("OK", {"assets": [self.asset]})
        self.create_result = StubResult("OK", {"asset": self.asset})
        self.update_result = StubResult("OK", {"asset": self.asset})
        self.delete_result = StubResult("OK", {})
        self.read_result = StubResult("OK", {"asset": self.asset})
        self.duplicate: dict[str, Any] | None = None
        self.calls: list[tuple[str, Any]] = []
        self.preserve_list_on_delete = False

    def list_records(self, **kwargs: Any) -> StubResult:
        self.calls.append(("list", kwargs))
        return self.list_result

    def create(self, payload: dict[str, Any]) -> StubResult:
        self.calls.append(("create", payload))
        return self.create_result

    def update(self, asset_id: str, payload: dict[str, Any]) -> StubResult:
        self.calls.append(("update", (asset_id, payload)))
        return self.update_result

    def delete(self, asset_id: str) -> StubResult:
        self.calls.append(("delete", asset_id))
        if self.delete_result.code == "OK" and not self.preserve_list_on_delete:
            self.list_result = StubResult("OK", {"assets": []})
        return self.delete_result

    def read(self, asset_id: str) -> StubResult:
        self.calls.append(("read", asset_id))
        return self.read_result

    def file_hash(self, path: Path) -> str:
        self.calls.append(("hash", path.name))
        return path.read_bytes().decode("utf-8")

    def duplicate_by_hash(self, sha256: str, *, exclude_id: str) -> dict[str, Any] | None:
        self.calls.append(("duplicate", (sha256, exclude_id)))
        return self.duplicate

    def reuse_duplicate(self, asset_id: str, duplicate_id: str) -> StubResult:
        self.calls.append(("reuse", (asset_id, duplicate_id)))
        return StubResult("OK", {"asset": {"id": asset_id, "file_url": "/asset-files/reused.png"}, "duplicate_asset": self.duplicate})

    def replace_duplicate(self, asset_id: str, duplicate_id: str, **kwargs: Any) -> StubResult:
        self.calls.append(("replace", (asset_id, duplicate_id, kwargs)))
        return StubResult("OK", {"asset": {"id": asset_id, "file_url": kwargs["file_url"]}, "duplicate_asset": self.duplicate})

    def attach_file(self, asset_id: str, **kwargs: Any) -> StubResult:
        self.calls.append(("attach", (asset_id, kwargs)))
        return StubResult("OK", {"asset": {"id": asset_id, **kwargs}})


@pytest.fixture
def asset_client(tmp_path: Path):
    service = StubAssetService()
    upload_dir = tmp_path / "assets"

    def require_auth(view: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(view)
        def protected(*args: Any, **kwargs: Any):
            if request.headers.get("X-Test-Auth") != "yes":
                return jsonify({"error": "AUTH_REQUIRED"}), 401
            return view(*args, **kwargs)

        return protected

    app = Flask(__name__)
    app.config.update(TESTING=True)
    app.register_blueprint(
        create_asset_blueprint(
            AssetRoutesDependencies(
                require_auth=require_auth,
                get_asset_service=lambda: service,
                get_upload_dir=lambda: upload_dir,
                extension_allowed=lambda filename: Path(filename).suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif", ".mp3", ".wav", ".mp4"},
                normalize_asset_id=lambda value: value.strip().lower().replace(" ", "-"),
                clock=lambda: 123.9,
                token_hex=lambda _: "temp-token",
            )
        )
    )
    with app.test_client() as client:
        yield client, app, service, upload_dir


def auth_headers() -> dict[str, str]:
    return {"X-Test-Auth": "yes"}


def test_asset_blueprint_registers_preserved_urls(asset_client) -> None:
    _, app, *_ = asset_client
    paths = {rule.rule for rule in app.url_map.iter_rules()}
    assert {
        "/api/assets",
        "/api/assets/storage",
        "/api/assets/<asset_id>",
        "/api/assets/<asset_id>/upload",
        "/asset-files/<filename>",
    }.issubset(paths)


def test_asset_routes_require_authentication(asset_client) -> None:
    client, _, service, _ = asset_client
    response = client.get("/api/assets")
    assert response.status_code == 401
    assert service.calls == []


def test_asset_list_maps_filters(asset_client) -> None:
    client, _, service, _ = asset_client
    response = client.get(
        "/api/assets?include_inactive=false&category=Sponsor&asset_type=Logo&rights_status=Verified",
        headers=auth_headers(),
    )
    assert response.status_code == 200
    assert service.calls[-1] == (
        "list",
            {
                "include_inactive": False,
                "category": "Sponsor",
                "asset_type": "Logo",
                "rights_status": "Verified",
                "placement": "",
            },
        )


def test_asset_crud_preserves_payloads_and_error_mappings(asset_client) -> None:
    client, _, service, _ = asset_client
    assert client.post("/api/assets", json={"name": "Logo"}, headers=auth_headers()).status_code == 200
    assert client.put("/api/assets/asset-one", json={"name": "New"}, headers=auth_headers()).status_code == 200
    assert client.delete("/api/assets/asset-one", headers=auth_headers()).get_json() == {
        "media_deleted": False,
        "ok": True,
    }
    service.create_result = StubResult("ASSET_NAME_REQUIRED", {})
    assert client.post("/api/assets", json={}, headers=auth_headers()).status_code == 400
    service.update_result = StubResult("ASSET_NOT_FOUND", {})
    assert client.put("/api/assets/missing", json={}, headers=auth_headers()).status_code == 404
    service.delete_result = StubResult("ASSET_NOT_FOUND", {})
    assert client.delete("/api/assets/missing", headers=auth_headers()).status_code == 404


def test_asset_file_route_remains_public(asset_client) -> None:
    client, _, _, upload_dir = asset_client
    upload_dir.mkdir(parents=True)
    (upload_dir / "logo.txt").write_text("asset", encoding="utf-8")
    response = client.get("/asset-files/logo.txt")
    assert response.status_code == 200
    assert response.data == b"asset"


def test_asset_storage_reports_managed_and_orphan_files(asset_client) -> None:
    client, _, service, upload_dir = asset_client
    upload_dir.mkdir(parents=True)
    (upload_dir / "used.mp4").write_bytes(b"used")
    (upload_dir / "orphan.mp4").write_bytes(b"orphan")
    service.list_result = StubResult(
        "OK",
        {"assets": [{"id": "asset-one", "file_url": "/asset-files/used.mp4"}]},
    )
    payload = client.get("/api/assets/storage", headers=auth_headers()).get_json()
    assert payload == {
        "managed_bytes": 10,
        "managed_file_count": 2,
        "orphan_bytes": 6,
        "orphan_count": 1,
    }


def test_asset_delete_removes_only_unshared_managed_media(asset_client) -> None:
    client, _, service, upload_dir = asset_client
    upload_dir.mkdir(parents=True)
    managed = upload_dir / "clip.mp4"
    managed.write_bytes(b"clip")
    service.asset = {
        "id": "asset-one",
        "name": "Clip",
        "file_url": "/asset-files/clip.mp4",
    }
    service.read_result = StubResult("OK", {"asset": service.asset})
    response = client.delete("/api/assets/asset-one", headers=auth_headers())
    assert response.get_json() == {"media_deleted": True, "ok": True}
    assert not managed.exists()


def test_asset_delete_retains_external_media(asset_client) -> None:
    client, _, service, _ = asset_client
    service.asset = {
        "id": "asset-one",
        "name": "External",
        "file_url": "https://example.test/clip.mp4",
    }
    service.read_result = StubResult("OK", {"asset": service.asset})
    response = client.delete("/api/assets/asset-one", headers=auth_headers())
    assert response.get_json() == {"media_deleted": False, "ok": True}


def test_asset_delete_retains_managed_media_referenced_by_another_asset(asset_client) -> None:
    client, _, service, upload_dir = asset_client
    upload_dir.mkdir(parents=True)
    managed = upload_dir / "shared.mp4"
    managed.write_bytes(b"shared")
    service.asset = {
        "id": "asset-one",
        "name": "Shared Clip One",
        "file_url": "/asset-files/shared.mp4",
    }
    service.read_result = StubResult("OK", {"asset": service.asset})
    service.list_result = StubResult(
        "OK",
        {
            "assets": [
                service.asset,
                {
                    "id": "asset-two",
                    "name": "Shared Clip Two",
                    "file_url": "/asset-files/shared.mp4",
                },
            ]
        },
    )
    service.preserve_list_on_delete = True
    response = client.delete("/api/assets/asset-one", headers=auth_headers())
    assert response.get_json() == {"media_deleted": False, "ok": True}
    assert managed.exists()


def test_asset_upload_validates_file_and_record(asset_client) -> None:
    client, _, service, _ = asset_client
    assert client.post("/api/assets/asset-one/upload", headers=auth_headers()).status_code == 400
    unsupported = client.post(
        "/api/assets/asset-one/upload",
        data={"asset": (io.BytesIO(b"bad"), "asset.exe")},
        headers=auth_headers(),
        content_type="multipart/form-data",
    )
    assert unsupported.status_code == 400
    service.read_result = StubResult("ASSET_NOT_FOUND", {})
    missing = client.post(
        "/api/assets/missing/upload",
        data={"asset": (io.BytesIO(b"logo"), "asset.png")},
        headers=auth_headers(),
        content_type="multipart/form-data",
    )
    assert missing.status_code == 404


def test_asset_upload_attaches_new_file(asset_client) -> None:
    client, _, service, upload_dir = asset_client
    response = client.post(
        "/api/assets/Asset One/upload",
        data={"asset": (io.BytesIO(b"new"), "logo.png")},
        headers=auth_headers(),
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    assert response.get_json()["file_url"] == "/asset-files/asset-one-123.png"
    assert (upload_dir / "asset-one-123.png").read_bytes() == b"new"
    assert service.calls[-1][0] == "attach"


def test_asset_upload_duplicate_prompt_and_reuse(asset_client) -> None:
    client, _, service, upload_dir = asset_client
    service.duplicate = {"id": "existing", "file_url": "/asset-files/existing.png"}
    prompt = client.post(
        "/api/assets/asset-one/upload",
        data={"asset": (io.BytesIO(b"same"), "logo.png")},
        headers=auth_headers(),
        content_type="multipart/form-data",
    )
    assert prompt.status_code == 409
    assert list(upload_dir.glob(".upload-*")) == []
    reused = client.post(
        "/api/assets/asset-one/upload",
        data={"asset": (io.BytesIO(b"same"), "logo.png"), "duplicate_action": "reuse"},
        headers=auth_headers(),
        content_type="multipart/form-data",
    )
    assert reused.status_code == 200
    assert reused.get_json()["file_url"] == "/asset-files/reused.png"
    assert service.calls[-1] == ("reuse", ("asset-one", "existing"))


def test_asset_upload_duplicate_replace_preserves_existing_filename(asset_client) -> None:
    client, _, service, upload_dir = asset_client
    upload_dir.mkdir(parents=True)
    (upload_dir / "existing.png").write_bytes(b"old")
    service.duplicate = {"id": "existing", "file_url": "/asset-files/existing.png"}
    response = client.post(
        "/api/assets/asset-one/upload",
        data={"asset": (io.BytesIO(b"same"), "logo.png"), "duplicate_action": "replace"},
        headers=auth_headers(),
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    assert (upload_dir / "existing.png").read_bytes() == b"same"
    name, arguments = service.calls[-1]
    assert name == "replace"
    assert arguments[2]["file_url"] == "/asset-files/existing.png"
