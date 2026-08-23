from __future__ import annotations

from typing import Any

import pytest

import app as app_module
from broadcast_lifecycle_service import BroadcastLifecycleResult


if not hasattr(app_module, "get_broadcast_lifecycle_service"):
    pytest.skip(
        "BroadcastLifecycleService routes are not integrated yet.",
        allow_module_level=True,
    )


class StubBroadcastLifecycleService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.load_result = BroadcastLifecycleResult(
            "OK",
            {"state": {"broadcast_id": "FB-2026-01", "status": "planned"}},
        )
        self.initialize_result = BroadcastLifecycleResult(
            "OK",
            {
                "state": {"broadcast_id": "FB-2026-01"},
                "readiness": {"ready": True},
                "deprecated": True,
            },
        )
        self.start_result = BroadcastLifecycleResult(
            "OK",
            {
                "state": {"broadcast_id": "FB-2026-01", "status": "live"},
                "broadcast": {"broadcast_id": "FB-2026-01"},
                "obs": None,
            },
        )
        self.resume_result = BroadcastLifecycleResult(
            "OK",
            {"state": {"broadcast_id": "FB-2026-01", "status": "live"}},
        )

    def load(self, broadcast_id: str) -> BroadcastLifecycleResult:
        self.calls.append(("load", broadcast_id))
        return self.load_result

    def initialize(self) -> BroadcastLifecycleResult:
        self.calls.append(("initialize", None))
        return self.initialize_result

    def start(self) -> BroadcastLifecycleResult:
        self.calls.append(("start", None))
        return self.start_result

    def resume(self) -> BroadcastLifecycleResult:
        self.calls.append(("resume", None))
        return self.resume_result


@pytest.fixture
def lifecycle_client(monkeypatch: pytest.MonkeyPatch):
    service = StubBroadcastLifecycleService()
    monkeypatch.setattr(
        app_module,
        "BROADCAST_LIFECYCLE_SERVICE",
        service,
        raising=False,
    )
    monkeypatch.setattr(app_module, "pin_is_configured", lambda: True)
    monkeypatch.setitem(app_module.app.config, "TESTING", True)
    monkeypatch.setitem(
        app_module.app.config,
        "SECRET_KEY",
        "broadcast-lifecycle-route-test",
    )
    with app_module.app.test_client() as client:
        with client.session_transaction() as active_session:
            active_session["authenticated"] = True
        yield client, service


def test_load_broadcast_route_delegates(lifecycle_client) -> None:
    client, service = lifecycle_client
    response = client.post("/api/broadcasts/FB-2026-01/load")
    assert response.status_code == 200
    assert response.get_json()["broadcast_id"] == "FB-2026-01"
    assert service.calls == [("load", "FB-2026-01")]


def test_load_broadcast_route_maps_not_found(lifecycle_client) -> None:
    client, service = lifecycle_client
    service.load_result = BroadcastLifecycleResult("NOT_FOUND", {})
    response = client.post("/api/broadcasts/missing/load")
    assert response.status_code == 404
    assert response.get_json() == {"error": "NOT_FOUND"}


def test_initialize_route_maps_missing_broadcast(lifecycle_client) -> None:
    client, service = lifecycle_client
    service.initialize_result = BroadcastLifecycleResult(
        "NO_ACTIVE_BROADCAST",
        {},
    )
    response = client.post("/api/initialize-broadcast")
    assert response.status_code == 409
    assert response.get_json() == {"error": "NO_ACTIVE_BROADCAST"}


def test_initialize_route_preserves_compatibility_payload(lifecycle_client) -> None:
    client, service = lifecycle_client
    response = client.post("/api/initialize-broadcast")
    assert response.status_code == 200
    assert response.get_json()["deprecated"] is True
    assert response.get_json()["readiness"] == {"ready": True}
    assert service.calls == [("initialize", None)]


def test_start_route_delegates_and_preserves_payload(lifecycle_client) -> None:
    client, service = lifecycle_client
    response = client.post("/api/start-broadcast")
    assert response.status_code == 200
    assert response.get_json()["state"]["status"] == "live"
    assert response.get_json()["broadcast"]["broadcast_id"] == "FB-2026-01"
    assert service.calls == [("start", None)]


def test_resume_route_delegates(lifecycle_client) -> None:
    client, service = lifecycle_client
    response = client.post("/api/resume-broadcast")
    assert response.status_code == 200
    assert response.get_json()["status"] == "live"
    assert service.calls == [("resume", None)]


