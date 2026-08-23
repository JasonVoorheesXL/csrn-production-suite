from __future__ import annotations

import io
from dataclasses import dataclass
from functools import wraps
from pathlib import Path
from typing import Any, Callable

import pytest
from flask import Flask, jsonify, request

from routes.sponsor_routes import (
    SponsorRoutesDependencies,
    create_sponsor_blueprint,
)


@dataclass(frozen=True)
class StubResult:
    code: str
    data: dict[str, Any]


class StubSponsorService:
    def __init__(self) -> None:
        self.sponsor = {"id": "bank", "name": "Bank", "logo_url": "/asset-files/logo.png"}
        self.create_result = StubResult("OK", {"sponsor": self.sponsor})
        self.update_result = StubResult("OK", {"sponsor": self.sponsor})
        self.delete_result = StubResult("OK", {})
        self.link_result = StubResult("OK", {"sponsor": self.sponsor})
        self.calls: list[tuple[str, Any]] = []

    def list_payload(self) -> dict[str, Any]:
        self.calls.append(("list", None))
        return {"sponsors": [self.sponsor]}

    def create(self, payload: dict[str, Any]) -> StubResult:
        self.calls.append(("create", payload))
        return self.create_result

    def update(self, sponsor_id: str, payload: dict[str, Any]) -> StubResult:
        self.calls.append(("update", (sponsor_id, payload)))
        return self.update_result

    def delete(self, sponsor_id: str) -> StubResult:
        self.calls.append(("delete", sponsor_id))
        return self.delete_result

    def link_asset(self, sponsor_id: str, asset_id: str) -> StubResult:
        self.calls.append(("link", (sponsor_id, asset_id)))
        return self.link_result


@pytest.fixture
def sponsor_client(tmp_path: Path):
    service = StubSponsorService()
    sponsors = [service.sponsor]
    assets: list[dict[str, Any]] = []
    saved: list[list[dict[str, Any]]] = []
    asset_dir = tmp_path / "assets"
    sponsor_dir = tmp_path / "sponsor-logos"
    tokens = iter(["temp-token", "asset-token", "next-temp", "next-asset"])

    def require_auth(view: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(view)
        def protected(*args: Any, **kwargs: Any):
            if request.headers.get("X-Test-Auth") != "yes":
                return jsonify({"error": "AUTH_REQUIRED"}), 401
            return view(*args, **kwargs)

        return protected

    def save_assets(items: list[dict[str, Any]]) -> None:
        saved.append([dict(item) for item in items])

    def clean_asset_record(payload: dict[str, Any], asset_id: str) -> dict[str, Any]:
        return {**payload, "id": asset_id, "cleaned": True}

    app = Flask(__name__)
    app.config.update(TESTING=True)
    app.register_blueprint(
        create_sponsor_blueprint(
            SponsorRoutesDependencies(
                require_auth=require_auth,
                get_sponsor_service=lambda: service,
                load_sponsors=lambda: sponsors,
                load_assets=lambda: assets,
                save_assets=save_assets,
                clean_asset_record=clean_asset_record,
                asset_file_hash=lambda path: path.read_bytes().decode("utf-8"),
                get_asset_upload_dir=lambda: asset_dir,
                get_sponsor_upload_dir=lambda: sponsor_dir,
                clock=lambda: 123.456,
                token_hex=lambda _: next(tokens),
            )
        )
    )
    with app.test_client() as client:
        yield client, app, service, sponsors, assets, saved, asset_dir, sponsor_dir


def auth_headers() -> dict[str, str]:
    return {"X-Test-Auth": "yes"}


def test_sponsor_blueprint_registers_preserved_urls(sponsor_client) -> None:
    _, app, *_ = sponsor_client
    paths = {rule.rule for rule in app.url_map.iter_rules()}
    assert {
        "/api/sponsors",
        "/api/sponsors/<sponsor_id>",
        "/api/sponsors/<sponsor_id>/logo",
        "/api/sponsors/<sponsor_id>/asset",
        "/sponsor-logos/<filename>",
    }.issubset(paths)


def test_sponsor_routes_require_authentication(sponsor_client) -> None:
    client, _, service, *_ = sponsor_client
    response = client.get("/api/sponsors")
    assert response.status_code == 401
    assert service.calls == []


def test_sponsor_crud_preserves_payloads_and_statuses(sponsor_client) -> None:
    client, _, service, *_ = sponsor_client
    assert client.get("/api/sponsors", headers=auth_headers()).get_json()["sponsors"][0]["id"] == "bank"
    created = client.post("/api/sponsors", json={"name": "Bank"}, headers=auth_headers())
    assert created.status_code == 200
    assert created.get_json()["sponsor"]["id"] == "bank"
    updated = client.put("/api/sponsors/bank", json={"name": "New Bank"}, headers=auth_headers())
    assert updated.status_code == 200
    assert client.delete("/api/sponsors/bank", headers=auth_headers()).get_json() == {"ok": True}


def test_sponsor_crud_preserves_error_mappings(sponsor_client) -> None:
    client, _, service, *_ = sponsor_client
    service.create_result = StubResult("SPONSOR_NAME_REQUIRED", {})
    assert client.post("/api/sponsors", json={}, headers=auth_headers()).status_code == 400
    service.create_result = StubResult("DUPLICATE_SPONSOR", {"duplicate_sponsor": {"id": "bank"}})
    assert client.post("/api/sponsors", json={"name": "Bank"}, headers=auth_headers()).status_code == 409
    service.update_result = StubResult("SPONSOR_NOT_FOUND", {})
    assert client.put("/api/sponsors/missing", json={}, headers=auth_headers()).status_code == 404
    service.delete_result = StubResult("SPONSOR_NOT_FOUND", {})
    assert client.delete("/api/sponsors/missing", headers=auth_headers()).status_code == 404


def test_sponsor_logo_file_route_remains_public(sponsor_client) -> None:
    client, *_, sponsor_dir = sponsor_client
    sponsor_dir.mkdir(parents=True)
    (sponsor_dir / "bank.txt").write_text("logo", encoding="utf-8")
    response = client.get("/sponsor-logos/bank.txt")
    assert response.status_code == 200
    assert response.data == b"logo"


def test_sponsor_logo_upload_validates_file_and_sponsor(sponsor_client) -> None:
    client, _, _, sponsors, *_ = sponsor_client
    assert client.post("/api/sponsors/bank/logo", headers=auth_headers()).status_code == 400
    unsupported = client.post(
        "/api/sponsors/bank/logo",
        data={"logo": (io.BytesIO(b"bad"), "logo.txt")},
        headers=auth_headers(),
        content_type="multipart/form-data",
    )
    assert unsupported.status_code == 400
    sponsors.clear()
    missing = client.post(
        "/api/sponsors/missing/logo",
        data={"logo": (io.BytesIO(b"logo"), "logo.png")},
        headers=auth_headers(),
        content_type="multipart/form-data",
    )
    assert missing.status_code == 404


def test_sponsor_logo_upload_creates_asset_and_links_it(sponsor_client) -> None:
    client, _, service, _, assets, saved, asset_dir, _ = sponsor_client
    response = client.post(
        "/api/sponsors/bank/logo",
        data={"logo": (io.BytesIO(b"new-logo"), "logo.png")},
        headers=auth_headers(),
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["asset"]["id"] == "asset-123456-asset-token"
    assert payload["asset"]["cleaned"] is True
    assert assets[0]["sha256"] == "new-logo"
    assert saved[-1][0]["id"] == assets[0]["id"]
    assert (asset_dir / f"{assets[0]['id']}.png").read_bytes() == b"new-logo"
    assert service.calls[-1] == ("link", ("bank", assets[0]["id"]))


def test_sponsor_logo_duplicate_prompt_and_reuse(sponsor_client) -> None:
    client, _, service, _, assets, _, asset_dir, _ = sponsor_client
    existing = {"id": "existing", "sha256": "same", "active": True, "file_url": "/asset-files/existing.png"}
    assets.append(existing)
    prompt = client.post(
        "/api/sponsors/bank/logo",
        data={"logo": (io.BytesIO(b"same"), "logo.png")},
        headers=auth_headers(),
        content_type="multipart/form-data",
    )
    assert prompt.status_code == 409
    assert list(asset_dir.glob(".upload-*")) == []
    reused = client.post(
        "/api/sponsors/bank/logo",
        data={"logo": (io.BytesIO(b"same"), "logo.png"), "duplicate_action": "reuse"},
        headers=auth_headers(),
        content_type="multipart/form-data",
    )
    assert reused.status_code == 200
    assert reused.get_json()["duplicate_reused"] is True
    assert service.calls[-1] == ("link", ("bank", "existing"))


def test_sponsor_logo_duplicate_replace_updates_asset(sponsor_client) -> None:
    client, _, _, _, assets, saved, asset_dir, _ = sponsor_client
    asset_dir.mkdir(parents=True)
    (asset_dir / "existing.png").write_bytes(b"old")
    assets.append({"id": "existing", "sha256": "same", "active": True, "file_url": "/asset-files/existing.png"})
    response = client.post(
        "/api/sponsors/bank/logo",
        data={"logo": (io.BytesIO(b"same"), "logo.png"), "duplicate_action": "replace"},
        headers=auth_headers(),
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    assert (asset_dir / "existing.png").read_bytes() == b"same"
    assert assets[0]["updated_at"] == 123
    assert saved[-1][0]["original_filename"] == "logo.png"


def test_sponsor_asset_link_preserves_error_mappings(sponsor_client) -> None:
    client, _, service, *_ = sponsor_client
    service.link_result = StubResult("INVALID_SPONSOR_LOGO_ASSET", {})
    assert client.put("/api/sponsors/bank/asset", json={"asset_id": "bad"}, headers=auth_headers()).status_code == 400
    service.link_result = StubResult("SPONSOR_NOT_FOUND", {})
    assert client.put("/api/sponsors/missing/asset", json={"asset_id": "a"}, headers=auth_headers()).status_code == 404
    service.link_result = StubResult("OK", {"sponsor": service.sponsor})
    assert client.put("/api/sponsors/bank/asset", json={"asset_id": " a "}, headers=auth_headers()).status_code == 200
    assert service.calls[-1] == ("link", ("bank", "a"))


