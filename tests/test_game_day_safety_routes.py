from __future__ import annotations

from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable

import pytest
from flask import Flask, jsonify, request

from routes.game_day_safety_routes import (
    GameDaySafetyRoutesDependencies,
    create_game_day_safety_blueprint,
)


@dataclass(frozen=True)
class StubResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)


class StubSafetyService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.preflight_result = StubResult(
            "OK",
            {"preflight": {"ready": True, "checks": []}},
        )
        self.list_result = StubResult("OK", {"snapshots": []})
        self.create_result = StubResult(
            "SNAPSHOT_CREATED",
            {"snapshot": {"snapshot_id": "snapshot-1"}},
        )
        self.verify_result = StubResult(
            "SNAPSHOT_VERIFIED",
            {"verification": {"verified": True}},
        )

    def preflight(self) -> StubResult:
        self.calls.append(("preflight", None))
        return self.preflight_result

    def list_snapshots(self) -> StubResult:
        self.calls.append(("list", None))
        return self.list_result

    def create_snapshot(self, *, kind: str, note: str) -> StubResult:
        self.calls.append(("create", {"kind": kind, "note": note}))
        return self.create_result

    def verify_snapshot(self, snapshot_id: str) -> StubResult:
        self.calls.append(("verify", snapshot_id))
        return self.verify_result


@pytest.fixture
def safety_client():
    service = StubSafetyService()

    def require_auth(view: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(view)
        def protected(*args: Any, **kwargs: Any):
            if request.headers.get("X-Test-Auth") != "yes":
                return jsonify({"error": "AUTH_REQUIRED"}), 401
            return view(*args, **kwargs)

        return protected

    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="safety-route-test")
    app.register_blueprint(
        create_game_day_safety_blueprint(
            GameDaySafetyRoutesDependencies(
                require_auth=require_auth,
                get_safety_service=lambda: service,
            )
        )
    )
    with app.test_client() as client:
        yield client, app, service


def auth_headers() -> dict[str, str]:
    return {"X-Test-Auth": "yes"}


def test_game_day_safety_blueprint_registers_urls(safety_client) -> None:
    _, app, _ = safety_client
    rules = {
        (rule.rule, tuple(sorted(rule.methods - {"HEAD", "OPTIONS"})))
        for rule in app.url_map.iter_rules()
    }
    assert ("/api/game-day/preflight", ("GET",)) in rules
    assert ("/api/game-day/snapshots", ("GET",)) in rules
    assert ("/api/game-day/snapshots", ("POST",)) in rules
    assert (
        "/api/game-day/snapshots/<snapshot_id>/verify",
        ("POST",),
    ) in rules


def test_game_day_safety_routes_require_authentication(safety_client) -> None:
    client, _, service = safety_client
    response = client.get("/api/game-day/preflight")
    assert response.status_code == 401
    assert service.calls == []


def test_preflight_maps_ready_and_failure(safety_client) -> None:
    client, _, service = safety_client
    ready = client.get("/api/game-day/preflight", headers=auth_headers())
    assert ready.status_code == 200
    assert ready.get_json()["code"] == "OK"

    service.preflight_result = StubResult(
        "PREFLIGHT_FAILED",
        {"preflight": {"ready": False, "checks": []}},
    )
    failed = client.get("/api/game-day/preflight", headers=auth_headers())
    assert failed.status_code == 409
    assert failed.get_json()["code"] == "PREFLIGHT_FAILED"


def test_snapshot_creation_delegates_payload(safety_client) -> None:
    client, _, service = safety_client
    response = client.post(
        "/api/game-day/snapshots",
        json={"kind": "manual", "note": "Pregame"},
        headers=auth_headers(),
    )
    assert response.status_code == 201
    assert response.get_json()["snapshot"]["snapshot_id"] == "snapshot-1"
    assert service.calls == [
        ("create", {"kind": "manual", "note": "Pregame"})
    ]


def test_snapshot_creation_maps_preflight_and_storage_failures(
    safety_client,
) -> None:
    client, _, service = safety_client
    service.create_result = StubResult(
        "PREFLIGHT_FAILED",
        {"preflight": {"ready": False}},
    )
    preflight = client.post(
        "/api/game-day/snapshots",
        json={},
        headers=auth_headers(),
    )
    assert preflight.status_code == 409

    service.create_result = StubResult(
        "SNAPSHOT_FAILED",
        {"message": "disk error"},
    )
    storage = client.post(
        "/api/game-day/snapshots",
        json={},
        headers=auth_headers(),
    )
    assert storage.status_code == 500
    assert storage.get_json()["message"] == "disk error"


def test_snapshot_list_delegates(safety_client) -> None:
    client, _, service = safety_client
    service.list_result = StubResult(
        "OK",
        {"snapshots": [{"snapshot_id": "one"}]},
    )
    response = client.get(
        "/api/game-day/snapshots",
        headers=auth_headers(),
    )
    assert response.status_code == 200
    assert response.get_json() == {"snapshots": [{"snapshot_id": "one"}]}


def test_snapshot_verification_maps_result_codes(safety_client) -> None:
    client, _, service = safety_client
    expected = {
        "INVALID_SNAPSHOT_ID": 400,
        "SNAPSHOT_NOT_FOUND": 404,
        "SNAPSHOT_INVALID": 409,
        "SNAPSHOT_CORRUPT": 409,
        "SNAPSHOT_VERIFIED": 200,
    }
    for code, status in expected.items():
        service.verify_result = StubResult(code)
        response = client.post(
            "/api/game-day/snapshots/example/verify",
            headers=auth_headers(),
        )
        assert response.status_code == status
        assert response.get_json()["code"] == code
