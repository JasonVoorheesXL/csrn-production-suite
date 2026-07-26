from __future__ import annotations

from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable

import pytest
from flask import Flask, jsonify, request

from routes.broadcast_routes import (
    BroadcastRoutesDependencies,
    create_broadcast_blueprint,
)


@dataclass(frozen=True)
class StubResult:
    code: str
    data: dict[str, Any]


class StubBroadcastService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.broadcast = {"broadcast_id": "FB-1", "status": "planned"}
        self.read_result = StubResult("OK", {"broadcast": self.broadcast})
        self.update_result = StubResult(
            "OK",
            {"broadcast": self.broadcast, "warnings": []},
        )
        self.status_result = StubResult("OK", {"broadcast": self.broadcast})
        self.delete_result = StubResult("OK", {"deleted": "FB-1"})

    def create(self, payload: dict[str, Any]) -> StubResult:
        self.calls.append(("create", payload))
        return StubResult(
            "OK",
            {"broadcast": self.broadcast, "warnings": ["warning"]},
        )

    def list_records(self, *, include_archived: bool = False) -> StubResult:
        self.calls.append(("list", include_archived))
        return StubResult("OK", {"broadcasts": [self.broadcast]})

    def read(self, broadcast_id: str) -> StubResult:
        self.calls.append(("read", broadcast_id))
        return self.read_result

    def update(self, broadcast_id: str, payload: dict[str, Any]) -> StubResult:
        self.calls.append(("update", (broadcast_id, payload)))
        return self.update_result

    def set_status(self, broadcast_id: str, status: Any) -> StubResult:
        self.calls.append(("status", (broadcast_id, status)))
        return self.status_result

    def delete(self, broadcast_id: str) -> StubResult:
        self.calls.append(("delete", broadcast_id))
        return self.delete_result


@pytest.fixture
def broadcast_client():
    service = StubBroadcastService()

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
        create_broadcast_blueprint(
            BroadcastRoutesDependencies(
                require_auth=require_auth,
                get_broadcast_service=lambda: service,
            )
        )
    )
    with app.test_client() as client:
        yield client, app, service


def auth_headers() -> dict[str, str]:
    return {"X-Test-Auth": "yes"}


def test_broadcast_blueprint_registers_preserved_urls(broadcast_client) -> None:
    _, app, _ = broadcast_client
    paths = {rule.rule for rule in app.url_map.iter_rules()}
    assert {
        "/api/create-broadcast",
        "/api/broadcasts",
        "/api/broadcasts/<broadcast_id>",
        "/api/broadcasts/<broadcast_id>/status",
    }.issubset(paths)


def test_broadcast_routes_require_authentication(broadcast_client) -> None:
    client, _, service = broadcast_client
    response = client.get("/api/broadcasts")
    assert response.status_code == 401
    assert service.calls == []


def test_list_broadcasts_maps_archive_option(broadcast_client) -> None:
    client, _, service = broadcast_client
    response = client.get(
        "/api/broadcasts?include_archived=true",
        headers=auth_headers(),
    )
    assert response.get_json() == [service.broadcast]
    assert service.calls == [("list", True)]


def test_create_broadcast_preserves_payload(broadcast_client) -> None:
    client, _, service = broadcast_client
    payload = {"home_school_id": "caledonia"}
    response = client.post(
        "/api/create-broadcast",
        json=payload,
        headers=auth_headers(),
    )
    assert response.get_json() == {
        "broadcast": service.broadcast,
        "warnings": ["warning"],
    }
    assert service.calls == [("create", payload)]


def test_read_broadcast_maps_not_found(broadcast_client) -> None:
    client, _, service = broadcast_client
    found = client.get("/api/broadcasts/FB-1", headers=auth_headers())
    assert found.get_json() == service.broadcast
    service.read_result = StubResult("NOT_FOUND", {})
    missing = client.get("/api/broadcasts/missing", headers=auth_headers())
    assert missing.status_code == 404
    assert missing.get_json() == {"error": "NOT_FOUND"}


def test_update_broadcast_maps_not_found(broadcast_client) -> None:
    client, _, service = broadcast_client
    updated = client.put(
        "/api/broadcasts/FB-1",
        json={"date": "2026-08-21"},
        headers=auth_headers(),
    )
    assert updated.get_json()["warnings"] == []
    service.update_result = StubResult("NOT_FOUND", {})
    missing = client.put(
        "/api/broadcasts/missing",
        json={},
        headers=auth_headers(),
    )
    assert missing.status_code == 404


def test_broadcast_status_maps_invalid_and_missing(broadcast_client) -> None:
    client, _, service = broadcast_client
    updated = client.put(
        "/api/broadcasts/FB-1/status",
        json={"status": "live"},
        headers=auth_headers(),
    )
    assert updated.get_json() == service.broadcast
    service.status_result = StubResult("INVALID_STATUS", {})
    invalid = client.put(
        "/api/broadcasts/FB-1/status",
        json={"status": "cancelled"},
        headers=auth_headers(),
    )
    assert invalid.status_code == 400
    service.status_result = StubResult("NOT_FOUND", {})
    missing = client.put(
        "/api/broadcasts/missing/status",
        json={"status": "live"},
        headers=auth_headers(),
    )
    assert missing.status_code == 404


def test_delete_broadcast_maps_not_found(broadcast_client) -> None:
    client, _, service = broadcast_client
    deleted = client.delete("/api/broadcasts/FB-1", headers=auth_headers())
    assert deleted.get_json() == {"deleted": "FB-1"}
    service.delete_result = StubResult("NOT_FOUND", {})
    missing = client.delete("/api/broadcasts/missing", headers=auth_headers())
    assert missing.status_code == 404
