from __future__ import annotations

from typing import Any

import pytest

import app as app_module
from rules_service import RulesResult


if not hasattr(app_module, "get_rules_service"):
    pytest.skip(
        "RulesService routes are not integrated yet.",
        allow_module_level=True,
    )


class StubRulesService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.clock_result = RulesResult(
            "OK",
            {"state": {"clock_seconds": 600, "clock_running": True}},
        )
        self.direction_result = RulesResult(
            "OK",
            {
                "state": {
                    "home_direction": "left",
                    "visitor_direction": "right",
                }
            },
        )
        self.play_result = RulesResult(
            "OK",
            {
                "state": {"status": "live", "home_score": 6},
                "play": {"play_id": "GAME-0001", "touchdown": True},
            },
        )

    def clock_control(self, payload: Any) -> RulesResult:
        self.calls.append(("clock", payload))
        return self.clock_result

    def field_direction(self, payload: Any) -> RulesResult:
        self.calls.append(("direction", payload))
        return self.direction_result

    def play(self, payload: Any) -> RulesResult:
        self.calls.append(("play", payload))
        return self.play_result


@pytest.fixture
def rules_client(monkeypatch: pytest.MonkeyPatch):
    service = StubRulesService()
    monkeypatch.setattr(app_module, "RULES_SERVICE", service, raising=False)
    monkeypatch.setattr(app_module, "pin_is_configured", lambda: True)
    monkeypatch.setitem(app_module.app.config, "TESTING", True)
    monkeypatch.setitem(app_module.app.config, "SECRET_KEY", "rules-route-test")
    with app_module.app.test_client() as client:
        with client.session_transaction() as active_session:
            active_session["authenticated"] = True
        yield client, service


def test_clock_control_route_delegates(rules_client) -> None:
    client, service = rules_client
    payload = {"action": "set", "seconds": 600}
    response = client.post("/api/clock-control", json=payload)
    assert response.status_code == 200
    assert response.get_json()["clock_seconds"] == 600
    assert service.calls == [("clock", payload)]


def test_field_direction_route_delegates(rules_client) -> None:
    client, service = rules_client
    payload = {"team": "home", "direction": "left"}
    response = client.post("/api/field-direction", json=payload)
    assert response.status_code == 200
    assert response.get_json()["home_direction"] == "left"
    assert service.calls == [("direction", payload)]


def test_field_direction_route_maps_invalid_direction(rules_client) -> None:
    client, service = rules_client
    service.direction_result = RulesResult("INVALID_DIRECTION", {})
    response = client.post(
        "/api/field-direction",
        json={"team": "home", "direction": "up"},
    )
    assert response.status_code == 400
    assert response.get_json() == {"error": "INVALID_DIRECTION"}


def test_rules_play_route_delegates(rules_client) -> None:
    client, service = rules_client
    payload = {"team": "home", "play_type": "run"}
    response = client.post("/api/rules-play", json=payload)
    assert response.status_code == 200
    assert response.get_json()["play"]["play_id"] == "GAME-0001"
    assert service.calls == [("play", payload)]


def test_rules_play_route_maps_invalid_play(rules_client) -> None:
    client, service = rules_client
    service.play_result = RulesResult("INVALID_PLAY", {})
    response = client.post(
        "/api/rules-play",
        json={"team": "home", "play_type": "field_goal"},
    )
    assert response.status_code == 400
    assert response.get_json() == {"error": "INVALID_PLAY"}


def test_rules_play_route_maps_missing_broadcast(rules_client) -> None:
    client, service = rules_client
    service.play_result = RulesResult("NO_ACTIVE_BROADCAST", {})
    response = client.post(
        "/api/rules-play",
        json={"team": "home", "play_type": "run"},
    )
    assert response.status_code == 409
    assert response.get_json() == {"error": "NO_ACTIVE_BROADCAST"}


def test_rules_play_route_maps_control_lock(rules_client) -> None:
    client, service = rules_client
    service.play_result = RulesResult(
        "CONTROL_SOURCE_LOCKED",
        {"error": "CONTROL_SOURCE_LOCKED", "authority": "broadcaster"},
    )
    response = client.post(
        "/api/rules-play",
        json={"team": "home", "play_type": "run"},
    )
    assert response.status_code == 409
    assert response.get_json()["authority"] == "broadcaster"


