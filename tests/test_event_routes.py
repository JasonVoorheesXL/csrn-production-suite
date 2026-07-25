from __future__ import annotations

from typing import Any

import pytest

import app as app_module
from event_service import EventResult


if not hasattr(app_module, "get_event_service"):
    pytest.skip(
        "EventService routes are not integrated yet.",
        allow_module_level=True,
    )


class StubEventService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.control_result = EventResult("OK", {"state": {"game_data_authority": "statistician"}})
        self.trigger_result = EventResult("OK", {"state": {"home_score": 6}, "trigger": {"event": "TD"}, "media_assigned": False, "message": "Touchdown (+6)"})
        self.correction_result = EventResult("OK", {"state": {"down": "2nd"}})
        self.edit_result = EventResult("OK", {"state": {"down": "2nd"}, "event": {"id": "E1"}})
        self.corrections_result = EventResult("OK", {"corrections": [{"id": "C1"}]})
        self.undo_result = EventResult("OK", {"state": {"home_score": 0}})

    def set_control_source(self, authority: Any) -> EventResult:
        self.calls.append(("control", authority))
        return self.control_result

    def trigger(self, payload: Any) -> EventResult:
        self.calls.append(("trigger", payload))
        return self.trigger_result

    def quick_correction(self, payload: Any) -> EventResult:
        self.calls.append(("correction", payload))
        return self.correction_result

    def edit(self, event_id: str, payload: Any) -> EventResult:
        self.calls.append(("edit", (event_id, payload)))
        return self.edit_result

    def corrections(self) -> EventResult:
        self.calls.append(("corrections", None))
        return self.corrections_result

    def undo(self) -> EventResult:
        self.calls.append(("undo", None))
        return self.undo_result


@pytest.fixture
def event_client(monkeypatch: pytest.MonkeyPatch):
    service = StubEventService()
    monkeypatch.setattr(app_module, "EVENT_SERVICE", service, raising=False)
    monkeypatch.setattr(app_module, "pin_is_configured", lambda: True)
    monkeypatch.setitem(app_module.app.config, "TESTING", True)
    monkeypatch.setitem(app_module.app.config, "SECRET_KEY", "event-route-test")
    with app_module.app.test_client() as client:
        with client.session_transaction() as session:
            session["authenticated"] = True
        yield client, service


def test_control_source_route_delegates(event_client) -> None:
    client, service = event_client
    response = client.post("/api/control-source", json={"authority": "statistician"})
    assert response.status_code == 200
    assert response.get_json()["game_data_authority"] == "statistician"
    assert service.calls == [("control", "statistician")]


def test_control_source_route_rejects_invalid(event_client) -> None:
    client, service = event_client
    service.control_result = EventResult("INVALID_CONTROL_SOURCE", {})
    response = client.post("/api/control-source", json={"authority": "producer"})
    assert response.status_code == 400
    assert response.get_json() == {"error": "INVALID_CONTROL_SOURCE"}


def test_event_trigger_route_delegates(event_client) -> None:
    client, service = event_client
    payload = {"team": "home", "event": "TD"}
    response = client.post("/api/event-trigger", json=payload)
    assert response.status_code == 200
    assert response.get_json()["trigger"]["event"] == "TD"
    assert service.calls == [("trigger", payload)]


def test_event_trigger_route_maps_invalid_event(event_client) -> None:
    client, service = event_client
    service.trigger_result = EventResult("INVALID_EVENT", {})
    response = client.post("/api/event-trigger", json={})
    assert response.status_code == 400
    assert response.get_json() == {"error": "INVALID_EVENT"}


def test_event_trigger_route_maps_no_active_broadcast(event_client) -> None:
    client, service = event_client
    service.trigger_result = EventResult("NO_ACTIVE_BROADCAST", {})
    response = client.post("/api/event-trigger", json={"team": "home", "event": "TD"})
    assert response.status_code == 409
    assert response.get_json() == {"error": "NO_ACTIVE_BROADCAST"}


def test_event_trigger_route_maps_control_lock(event_client) -> None:
    client, service = event_client
    service.trigger_result = EventResult("CONTROL_SOURCE_LOCKED", {"error": "CONTROL_SOURCE_LOCKED", "authority": "statistician"})
    response = client.post("/api/event-trigger", json={"team": "home", "event": "TD"})
    assert response.status_code == 409
    assert response.get_json()["authority"] == "statistician"


def test_game_correction_route_maps_validation_error(event_client) -> None:
    client, service = event_client
    service.correction_result = EventResult("INVALID_DOWN", {})
    response = client.post("/api/game-correction", json={"down": "5th"})
    assert response.status_code == 400
    assert response.get_json() == {"error": "INVALID_DOWN"}


def test_edit_event_route_maps_missing_event(event_client) -> None:
    client, service = event_client
    service.edit_result = EventResult("EVENT_NOT_FOUND", {})
    response = client.post("/api/events/missing/edit", json={})
    assert response.status_code == 404
    assert response.get_json() == {"error": "EVENT_NOT_FOUND"}


def test_corrections_route_delegates(event_client) -> None:
    client, service = event_client
    response = client.get("/api/corrections")
    assert response.status_code == 200
    assert response.get_json() == [{"id": "C1"}]
    assert service.calls == [("corrections", None)]


def test_undo_route_delegates(event_client) -> None:
    client, service = event_client
    response = client.post("/api/undo")
    assert response.status_code == 200
    assert response.get_json() == {"home_score": 0}
    assert service.calls == [("undo", None)]
