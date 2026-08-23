from __future__ import annotations

from typing import Any

import pytest

import app as app_module
from game_operations_service import GameOperationsResult


if not hasattr(app_module, "get_game_operations_service"):
    pytest.skip(
        "GameOperationsService routes are not integrated yet.",
        allow_module_level=True,
    )


class StubGameOperationsService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.score_result = GameOperationsResult(
            "OK",
            {"state": {"home_score": 6, "status": "live"}},
        )
        self.set_result = GameOperationsResult(
            "OK",
            {"state": {"quarter": "2"}},
        )
        self.scorebug_result = GameOperationsResult(
            "OK",
            {"state": {"scorebug_visible": True}},
        )
        self.halftime_result = GameOperationsResult(
            "OK",
            {"state": {"broadcast_phase": "halftime"}},
        )
        self.end_result = GameOperationsResult(
            "OK",
            {"state": {"broadcast_phase": "final", "status": "completed"}},
        )
        self.reset_result = GameOperationsResult(
            "OK",
            {"state": {"broadcast_id": "FB-2026-01", "home_score": 0}},
        )
        self.new_result = GameOperationsResult(
            "OK",
            {"state": {"broadcast_id": "", "broadcast_created": False}},
        )

    def score(self, payload: Any) -> GameOperationsResult:
        self.calls.append(("score", payload))
        return self.score_result

    def set_values(self, payload: Any) -> GameOperationsResult:
        self.calls.append(("set", payload))
        return self.set_result

    def toggle_scorebug(self) -> GameOperationsResult:
        self.calls.append(("scorebug", None))
        return self.scorebug_result

    def toggle_halftime(self) -> GameOperationsResult:
        self.calls.append(("halftime", None))
        return self.halftime_result

    def end_game(self) -> GameOperationsResult:
        self.calls.append(("end", None))
        return self.end_result

    def reset_data(self) -> GameOperationsResult:
        self.calls.append(("reset", None))
        return self.reset_result

    def new_broadcast(self) -> GameOperationsResult:
        self.calls.append(("new", None))
        return self.new_result


@pytest.fixture
def operations_client(monkeypatch: pytest.MonkeyPatch):
    service = StubGameOperationsService()
    monkeypatch.setattr(
        app_module,
        "GAME_OPERATIONS_SERVICE",
        service,
        raising=False,
    )
    monkeypatch.setattr(app_module, "pin_is_configured", lambda: True)
    monkeypatch.setitem(app_module.app.config, "TESTING", True)
    monkeypatch.setitem(
        app_module.app.config,
        "SECRET_KEY",
        "game-operations-route-test",
    )
    with app_module.app.test_client() as client:
        with client.session_transaction() as active_session:
            active_session["authenticated"] = True
        yield client, service


def test_score_route_delegates(operations_client) -> None:
    client, service = operations_client
    payload = {"team": "home", "delta": 6}
    response = client.post("/api/score", json=payload)
    assert response.status_code == 200
    assert response.get_json()["home_score"] == 6
    assert service.calls == [("score", payload)]


def test_score_route_maps_invalid_request(operations_client) -> None:
    client, service = operations_client
    service.score_result = GameOperationsResult("INVALID_SCORE_REQUEST", {})
    response = client.post("/api/score", json={"team": "neutral", "delta": 9})
    assert response.status_code == 400
    assert response.get_json() == {"error": "INVALID_SCORE_REQUEST"}


def test_score_route_maps_control_lock(operations_client) -> None:
    client, service = operations_client
    service.score_result = GameOperationsResult(
        "CONTROL_SOURCE_LOCKED",
        {"error": "CONTROL_SOURCE_LOCKED", "authority": "statistician"},
    )
    response = client.post("/api/score", json={"team": "home", "delta": 1})
    assert response.status_code == 409
    assert response.get_json()["authority"] == "statistician"


def test_set_route_delegates(operations_client) -> None:
    client, service = operations_client
    payload = {"quarter": "2"}
    response = client.post("/api/set", json=payload)
    assert response.status_code == 200
    assert response.get_json()["quarter"] == "2"
    assert service.calls == [("set", payload)]


def test_set_route_maps_control_lock(operations_client) -> None:
    client, service = operations_client
    service.set_result = GameOperationsResult(
        "CONTROL_SOURCE_LOCKED",
        {"error": "CONTROL_SOURCE_LOCKED", "authority": "statistician"},
    )
    response = client.post("/api/set", json={"quarter": "2"})
    assert response.status_code == 409
    assert response.get_json()["error"] == "CONTROL_SOURCE_LOCKED"


def test_toggle_scorebug_route_delegates(operations_client) -> None:
    client, service = operations_client
    response = client.post("/api/toggle-scorebug")
    assert response.status_code == 200
    assert response.get_json()["scorebug_visible"] is True
    assert service.calls == [("scorebug", None)]


def test_toggle_scorebug_route_maps_obs_failure(operations_client) -> None:
    client, service = operations_client
    service.scorebug_result = GameOperationsResult(
        "OBS_COMMAND_BLOCKED",
        {"message": "OBS unavailable"},
    )
    response = client.post("/api/toggle-scorebug")
    assert response.status_code == 409
    assert response.get_json() == {
        "error": "OBS_COMMAND_BLOCKED",
        "message": "OBS unavailable",
    }


def test_toggle_halftime_route_delegates(operations_client) -> None:
    client, service = operations_client
    response = client.post("/api/toggle-halftime")
    assert response.status_code == 200
    assert response.get_json()["broadcast_phase"] == "halftime"
    assert service.calls == [("halftime", None)]


def test_end_game_route_delegates(operations_client) -> None:
    client, service = operations_client
    response = client.post("/api/end-game")
    assert response.status_code == 200
    assert response.get_json()["status"] == "completed"
    assert service.calls == [("end", None)]


def test_reset_data_route_delegates(operations_client) -> None:
    client, service = operations_client
    response = client.post("/api/reset-data")
    assert response.status_code == 200
    assert response.get_json()["home_score"] == 0
    assert service.calls == [("reset", None)]


def test_new_broadcast_route_delegates(operations_client) -> None:
    client, service = operations_client
    response = client.post("/api/new-broadcast")
    assert response.status_code == 200
    assert response.get_json()["broadcast_created"] is False
    assert service.calls == [("new", None)]


