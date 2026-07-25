from __future__ import annotations

import io
from dataclasses import dataclass
from functools import wraps
from pathlib import Path
from typing import Any, Callable

import pytest
from flask import Flask, jsonify, request

from routes.personnel_routes import (
    PersonnelRoutesDependencies,
    create_personnel_blueprint,
)


@dataclass(frozen=True)
class StubResult:
    code: str
    data: dict[str, Any]

    @property
    def ok(self) -> bool:
        return self.code == "OK"


class StubPersonnelService:
    def __init__(self) -> None:
        self.list_result = StubResult("OK", {"personnel": [{"id": "jason"}]})
        self.create_result = StubResult("OK", {"personnel": {"id": "jason"}})
        self.update_result = StubResult("OK", {"personnel": {"id": "jason"}})
        self.delete_result = StubResult("OK", {})
        self.headshot_result = StubResult("OK", {"path": "/personnel-headshots/jason.png"})
        self.social_result = StubResult("OK", {"normalized": "https://example.com"})
        self.calls: list[tuple[str, Any]] = []

    def list_records(self, **kwargs: Any) -> StubResult:
        self.calls.append(("list", kwargs))
        return self.list_result

    def create(self, payload: dict[str, Any]) -> StubResult:
        self.calls.append(("create", payload))
        return self.create_result

    def update(self, personnel_id: str, payload: dict[str, Any]) -> StubResult:
        self.calls.append(("update", (personnel_id, payload)))
        return self.update_result

    def delete(self, personnel_id: str) -> StubResult:
        self.calls.append(("delete", personnel_id))
        return self.delete_result

    def attach_headshot(self, personnel_id: str, path: str) -> StubResult:
        self.calls.append(("headshot", (personnel_id, path)))
        return self.headshot_result

    def validate_social(self, platform: str, value: str) -> StubResult:
        self.calls.append(("social", (platform, value)))
        return self.social_result


@pytest.fixture
def personnel_client(tmp_path: Path):
    service = StubPersonnelService()

    def require_auth(view: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(view)
        def protected(*args: Any, **kwargs: Any):
            if request.headers.get("X-Test-Auth") != "yes":
                return jsonify({"error": "AUTH_REQUIRED"}), 401
            return view(*args, **kwargs)

        return protected

    app = Flask(__name__)
    app.config.update(TESTING=True)
    headshots = tmp_path / "headshots"
    app.register_blueprint(
        create_personnel_blueprint(
            PersonnelRoutesDependencies(
                require_auth=require_auth,
                get_personnel_service=lambda: service,
                headshots_dir=headshots,
                normalize_personnel_id=lambda value: value.strip().lower().replace(" ", "-"),
            )
        )
    )
    with app.test_client() as client:
        yield client, app, service, headshots


def auth_headers() -> dict[str, str]:
    return {"X-Test-Auth": "yes"}


def test_personnel_blueprint_registers_preserved_urls(personnel_client) -> None:
    _, app, _, _ = personnel_client
    paths = {rule.rule for rule in app.url_map.iter_rules()}
    assert {
        "/api/broadcasters",
        "/api/broadcasters/<broadcaster_id>",
        "/personnel-headshots/<filename>",
        "/api/personnel/<personnel_id>/headshot",
        "/api/validate-social",
    }.issubset(paths)


def test_personnel_routes_require_authentication(personnel_client) -> None:
    client, _, service, _ = personnel_client
    response = client.get("/api/broadcasters")
    assert response.status_code == 401
    assert response.get_json() == {"error": "AUTH_REQUIRED"}
    assert service.calls == []


def test_list_personnel_maps_query_filters(personnel_client) -> None:
    client, _, service, _ = personnel_client
    response = client.get(
        "/api/broadcasters?include_inactive=false&category=Broadcast+Talent&role=Play-by-Play&school_id=chs",
        headers=auth_headers(),
    )
    assert response.status_code == 200
    assert response.get_json() == [{"id": "jason"}]
    _, kwargs = service.calls[-1]
    assert kwargs == {
        "include_inactive": False,
        "category": "Broadcast Talent",
        "role": "Play-by-Play",
        "school_id": "chs",
    }


def test_create_personnel_preserves_success_and_validation_mappings(personnel_client) -> None:
    client, _, service, _ = personnel_client
    created = client.post("/api/broadcasters", json={"name": "Jason"}, headers=auth_headers())
    assert created.status_code == 201
    service.create_result = StubResult("STAFF_NAME_REQUIRED", {})
    assert client.post("/api/broadcasters", json={}, headers=auth_headers()).status_code == 400
    service.create_result = StubResult("INVALID_SOCIAL_URL", {"fields": {"x": "INVALID_URL"}})
    invalid = client.post("/api/broadcasters", json={}, headers=auth_headers())
    assert invalid.status_code == 400
    assert invalid.get_json()["fields"] == {"x": "INVALID_URL"}


def test_update_and_delete_personnel_preserve_status_mappings(personnel_client) -> None:
    client, _, service, _ = personnel_client
    assert client.put("/api/broadcasters/jason", json={"title": "Host"}, headers=auth_headers()).status_code == 200
    service.update_result = StubResult("BROADCASTER_NOT_FOUND", {})
    assert client.put("/api/broadcasters/missing", json={}, headers=auth_headers()).status_code == 404
    service.delete_result = StubResult("BROADCASTER_NOT_FOUND", {})
    assert client.delete("/api/broadcasters/missing", headers=auth_headers()).status_code == 404


def test_personnel_headshot_file_route_remains_public(personnel_client) -> None:
    client, _, _, headshots = personnel_client
    headshots.mkdir(parents=True)
    (headshots / "jason.txt").write_text("headshot", encoding="utf-8")
    response = client.get("/personnel-headshots/jason.txt")
    assert response.status_code == 200
    assert response.data == b"headshot"


def test_headshot_upload_rejects_missing_and_unsupported_files(personnel_client) -> None:
    client, _, _, _ = personnel_client
    missing = client.post("/api/personnel/jason/headshot", headers=auth_headers())
    assert missing.status_code == 400
    unsupported = client.post(
        "/api/personnel/jason/headshot",
        data={"file": (io.BytesIO(b"bad"), "headshot.gif")},
        headers=auth_headers(),
        content_type="multipart/form-data",
    )
    assert unsupported.status_code == 400
    assert unsupported.get_json() == {"error": "UNSUPPORTED_IMAGE"}


def test_headshot_upload_saves_and_cleans_up_missing_personnel(personnel_client) -> None:
    client, _, service, headshots = personnel_client
    response = client.post(
        "/api/personnel/Jason Chrest/headshot",
        data={"file": (io.BytesIO(b"image"), "headshot.png")},
        headers=auth_headers(),
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    assert (headshots / "jason-chrest.png").exists()
    service.headshot_result = StubResult("PERSONNEL_NOT_FOUND", {})
    missing = client.post(
        "/api/personnel/Missing/headshot",
        data={"file": (io.BytesIO(b"image"), "headshot.jpg")},
        headers=auth_headers(),
        content_type="multipart/form-data",
    )
    assert missing.status_code == 404
    assert not (headshots / "missing.jpg").exists()


def test_validate_social_delegates_payload(personnel_client) -> None:
    client, _, service, _ = personnel_client
    response = client.post(
        "/api/validate-social",
        json={"platform": "website", "value": "example.com"},
        headers=auth_headers(),
    )
    assert response.status_code == 200
    assert response.get_json() == {"normalized": "https://example.com"}
    assert service.calls[-1] == ("social", ("website", "example.com"))
