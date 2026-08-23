from __future__ import annotations

from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable

import pytest
from flask import Flask, jsonify, request

from routes.broadcast_package_routes import (
    BroadcastPackageRoutesDependencies,
    create_broadcast_package_blueprint,
)


@dataclass(frozen=True)
class StubResult:
    code: str
    data: dict[str, Any]


class StubPackageService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

    def list_packages(self) -> list[dict[str, Any]]:
        self.calls.append(("list", None))
        return [{"id": "pkg-1"}]

    def create(self, payload: dict[str, Any]) -> StubResult:
        self.calls.append(("create", payload))
        return StubResult("OK", {"package": {"id": "pkg-created", **payload}})

    def update(self, package_id: str, payload: dict[str, Any]) -> StubResult:
        self.calls.append(("update", (package_id, payload)))
        if package_id == "missing":
            return StubResult("NOT_FOUND", {})
        if package_id == "locked":
            return StubResult("PACKAGE_LOCKED", {})
        return StubResult("OK", {"package": {"id": package_id, **payload}})

    def delete(self, package_id: str) -> StubResult:
        self.calls.append(("delete", package_id))
        if package_id == "missing":
            return StubResult("NOT_FOUND", {})
        if package_id == "locked":
            return StubResult("PACKAGE_LOCKED", {})
        return StubResult("OK", {"deleted": package_id})

    def duplicate(self, package_id: str) -> StubResult:
        self.calls.append(("duplicate", package_id))
        if package_id == "missing":
            return StubResult("NOT_FOUND", {})
        return StubResult("OK", {"package": {"id": "pkg-copy"}})

    def load(self, package_id: str) -> StubResult:
        self.calls.append(("load", package_id))
        if package_id == "missing":
            return StubResult("NOT_FOUND", {})
        if package_id == "no-broadcast":
            return StubResult("BROADCAST_NOT_FOUND", {})
        return StubResult(
            "OK",
            {
                "package": {"id": package_id},
                "state": {"private": True, "score": 7},
                "health": {"ready": True},
            },
        )


@pytest.fixture
def package_client():
    service = StubPackageService()

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
        create_broadcast_package_blueprint(
            BroadcastPackageRoutesDependencies(
                require_auth=require_auth,
                get_package_service=lambda: service,
                public_state=lambda state: {"score": state["score"]},
            )
        )
    )
    with app.test_client() as client:
        yield client, app, service


def auth_headers() -> dict[str, str]:
    return {"X-Test-Auth": "yes"}


def test_package_blueprint_registers_preserved_urls(package_client) -> None:
    _, app, _ = package_client
    paths = {rule.rule for rule in app.url_map.iter_rules()}
    assert {
        "/api/packages",
        "/api/packages/<package_id>",
        "/api/packages/<package_id>/duplicate",
        "/api/packages/<package_id>/load",
    }.issubset(paths)


def test_package_routes_require_authentication(package_client) -> None:
    client, _, service = package_client
    response = client.get("/api/packages")
    assert response.status_code == 401
    assert service.calls == []


def test_package_list_and_create_delegate(package_client) -> None:
    client, _, service = package_client
    listed = client.get("/api/packages", headers=auth_headers())
    created = client.post(
        "/api/packages",
        json={"name": "Friday Night"},
        headers=auth_headers(),
    )
    assert listed.get_json() == [{"id": "pkg-1"}]
    assert created.status_code == 201
    assert created.get_json()["id"] == "pkg-created"
    assert ("create", {"name": "Friday Night"}) in service.calls


def test_package_update_maps_missing_and_locked(package_client) -> None:
    client, _, _ = package_client
    missing = client.put("/api/packages/missing", json={}, headers=auth_headers())
    locked = client.put("/api/packages/locked", json={}, headers=auth_headers())
    updated = client.put(
        "/api/packages/pkg-1",
        json={"name": "Updated"},
        headers=auth_headers(),
    )
    assert missing.status_code == 404
    assert locked.status_code == 409
    assert updated.get_json() == {"id": "pkg-1", "name": "Updated"}


def test_package_delete_and_duplicate_preserve_contracts(package_client) -> None:
    client, _, _ = package_client
    deleted = client.delete("/api/packages/pkg-1", headers=auth_headers())
    locked = client.delete("/api/packages/locked", headers=auth_headers())
    copied = client.post("/api/packages/pkg-1/duplicate", headers=auth_headers())
    missing = client.post("/api/packages/missing/duplicate", headers=auth_headers())
    assert deleted.get_json() == {"deleted": "pkg-1"}
    assert locked.status_code == 409
    assert copied.status_code == 201
    assert copied.get_json() == {"id": "pkg-copy"}
    assert missing.status_code == 404


def test_package_load_maps_errors_and_filters_state(package_client) -> None:
    client, _, _ = package_client
    missing = client.post("/api/packages/missing/load", headers=auth_headers())
    no_broadcast = client.post(
        "/api/packages/no-broadcast/load",
        headers=auth_headers(),
    )
    loaded = client.post("/api/packages/pkg-1/load", headers=auth_headers())
    assert missing.status_code == 404
    assert no_broadcast.status_code == 409
    assert loaded.get_json() == {
        "package": {"id": "pkg-1"},
        "state": {"score": 7},
        "health": {"ready": True},
    }


