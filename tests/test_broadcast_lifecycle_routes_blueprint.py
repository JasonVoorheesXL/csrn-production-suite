from __future__ import annotations

from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable

import pytest
from flask import Flask, jsonify, request

from routes.broadcast_lifecycle_routes import (
    BroadcastLifecycleRoutesDependencies,
    create_broadcast_lifecycle_blueprint,
)


@dataclass(frozen=True)
class StubResult:
    code: str
    data: dict[str, Any]


class StubLifecycleService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.load_result = StubResult(
            "OK",
            {"state": {"broadcast_id": "FB-1", "status": "planned"}},
        )
        self.initialize_result = StubResult(
            "OK",
            {"state": {"broadcast_id": "FB-1"}, "deprecated": True},
        )
        self.start_result = StubResult(
            "OK",
            {
                "state": {"broadcast_id": "FB-1", "status": "live"},
                "broadcast": {"broadcast_id": "FB-1"},
                "obs": None,
            },
        )
        self.resume_result = StubResult(
            "OK",
            {"state": {"broadcast_id": "FB-1", "status": "live"}},
        )

    def load(self, broadcast_id: str) -> StubResult:
        self.calls.append(("load", broadcast_id))
        return self.load_result

    def initialize(self) -> StubResult:
        self.calls.append(("initialize", None))
        return self.initialize_result

    def start(self) -> StubResult:
        self.calls.append(("start", None))
        return self.start_result

    def resume(self) -> StubResult:
        self.calls.append(("resume", None))
        return self.resume_result


@pytest.fixture
def lifecycle_client():
    service = StubLifecycleService()

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
        create_broadcast_lifecycle_blueprint(
            BroadcastLifecycleRoutesDependencies(
                require_auth=require_auth,
                get_lifecycle_service=lambda: service,
            )
        )
    )
    with app.test_client() as client:
        yield client, app, service


def auth_headers() -> dict[str, str]:
    return {"X-Test-Auth": "yes"}


def test_lifecycle_blueprint_registers_preserved_urls(lifecycle_client) -> None:
    _, app, _ = lifecycle_client
    paths = {rule.rule for rule in app.url_map.iter_rules()}
    assert {
        "/api/broadcasts/<broadcast_id>/load",
        "/api/initialize-broadcast",
        "/api/start-broadcast",
        "/api/resume-broadcast",
    }.issubset(paths)


def test_lifecycle_routes_require_authentication(lifecycle_client) -> None:
    client, _, service = lifecycle_client
    response = client.post("/api/start-broadcast")
    assert response.status_code == 401
    assert service.calls == []


def test_load_broadcast_delegates_and_maps_not_found(lifecycle_client) -> None:
    client, _, service = lifecycle_client
    loaded = client.post("/api/broadcasts/FB-1/load", headers=auth_headers())
    assert loaded.get_json()["broadcast_id"] == "FB-1"
    service.load_result = StubResult("NOT_FOUND", {})
    missing = client.post(
        "/api/broadcasts/missing/load",
        headers=auth_headers(),
    )
    assert missing.status_code == 404


def test_initialize_preserves_payload_and_maps_missing(lifecycle_client) -> None:
    client, _, service = lifecycle_client
    initialized = client.post("/api/initialize-broadcast", headers=auth_headers())
    assert initialized.get_json()["deprecated"] is True
    service.initialize_result = StubResult("NO_ACTIVE_BROADCAST", {})
    missing = client.post("/api/initialize-broadcast", headers=auth_headers())
    assert missing.status_code == 409


def test_start_preserves_payload_and_maps_missing(lifecycle_client) -> None:
    client, _, service = lifecycle_client
    started = client.post("/api/start-broadcast", headers=auth_headers())
    assert started.get_json()["state"]["status"] == "live"
    service.start_result = StubResult("NO_ACTIVE_BROADCAST", {})
    missing = client.post("/api/start-broadcast", headers=auth_headers())
    assert missing.status_code == 409


def test_resume_returns_state_and_maps_missing(lifecycle_client) -> None:
    client, _, service = lifecycle_client
    resumed = client.post("/api/resume-broadcast", headers=auth_headers())
    assert resumed.get_json()["status"] == "live"
    service.resume_result = StubResult("NO_ACTIVE_BROADCAST", {})
    missing = client.post("/api/resume-broadcast", headers=auth_headers())
    assert missing.status_code == 409
