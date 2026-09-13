from __future__ import annotations

from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable

import pytest
from flask import Flask, jsonify, request

from routes.hoops_game_routes import (
    HoopsGameRoutesDependencies,
    create_hoops_game_blueprint,
)


@dataclass(frozen=True)
class StubResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.code == "OK"


class StubHoopsOperationsService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.next_result = StubResult("OK", {"state": {"hoops": {"home_team_fouls": 1}}})

    def initialize_hoops(self, payload: dict[str, Any] | None = None) -> StubResult:
        self.calls.append(("initialize_hoops", payload))
        return self.next_result

    def dispatch(self, action: str, payload: dict[str, Any] | None = None) -> StubResult:
        self.calls.append((action, payload))
        return self.next_result


@pytest.fixture
def hoops_game_client():
    service = StubHoopsOperationsService()
    state = {
        "sport": "basketball",
        "hoops": {
            "home_team_fouls": 0, "visitor_team_fouls": 3,
            "home_bonus": "NONE", "visitor_bonus": "NONE",
            "home_timeouts": 5, "visitor_timeouts": 5,
            "shot_clock_seconds": None, "shot_clock_visible": False,
        },
    }

    def require_auth(view: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(view)
        def protected(*args: Any, **kwargs: Any):
            if request.headers.get("X-Test-Auth") != "yes":
                return jsonify({"error": "AUTH_REQUIRED"}), 401
            return view(*args, **kwargs)

        return protected

    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="hoops-game-route-test")
    app.register_blueprint(
        create_hoops_game_blueprint(
            HoopsGameRoutesDependencies(
                require_auth=require_auth,
                get_hoops_operations_service=lambda: service,
                load_state=lambda: state,
            )
        )
    )
    with app.test_client() as client:
        yield client, app, service, state


def auth_headers() -> dict[str, str]:
    return {"X-Test-Auth": "yes"}


def test_hoops_blueprint_registers_the_new_urls_only(hoops_game_client) -> None:
    _, app, *_ = hoops_game_client
    paths = {rule.rule for rule in app.url_map.iter_rules()}
    assert {
        "/api/hoops/initialize",
        "/api/hoops/action/<action>",
        "/api/hoops/overlay-state",
        "/api/hoops/box-score",
    }.issubset(paths)
    # Football's own URLs -- and baseball's diamond ones -- must never
    # appear here; this blueprint owns nothing under those paths.
    assert "/api/score" not in paths
    assert "/api/set" not in paths
    assert "/api/diamond/initialize" not in paths


def test_mutation_routes_require_authentication(hoops_game_client) -> None:
    client, _, _, _ = hoops_game_client
    response = client.post("/api/hoops/initialize", json={})
    assert response.status_code == 401
    response = client.post("/api/hoops/action/shot", json={})
    assert response.status_code == 401


def test_overlay_state_is_unauthenticated(hoops_game_client) -> None:
    client, _, _, _ = hoops_game_client
    response = client.get("/api/hoops/overlay-state")
    assert response.status_code == 200
    assert response.get_json()["visitor_fouls"] == "3"


def test_box_score_requires_authentication(hoops_game_client) -> None:
    client, _, _, _ = hoops_game_client
    response = client.get("/api/hoops/box-score")
    assert response.status_code == 401


def test_hoops_reporting_routes_reject_a_football_state(hoops_game_client) -> None:
    client, _, _, state = hoops_game_client
    state.clear()
    state.update({"sport": "Football"})
    overlay = client.get("/api/hoops/overlay-state")
    assert overlay.status_code == 409
    assert overlay.get_json() == {"error": "NOT_A_HOOPS_SPORT"}

    box_score = client.get("/api/hoops/box-score", headers=auth_headers())
    assert box_score.status_code == 409


def test_initialize_hoops_forwards_the_payload_and_returns_state(hoops_game_client) -> None:
    client, _, service, _ = hoops_game_client
    response = client.post("/api/hoops/initialize", json={"command_id": "c1"}, headers=auth_headers())
    assert response.status_code == 200
    assert response.get_json() == {"hoops": {"home_team_fouls": 1}}
    assert service.calls == [("initialize_hoops", {"command_id": "c1"})]


def test_hoops_action_forwards_the_action_name_and_payload(hoops_game_client) -> None:
    client, _, service, _ = hoops_game_client
    payload = {"team": "home", "made": True, "points": 2, "shooterId": "h1"}
    response = client.post("/api/hoops/action/shot", json=payload, headers=auth_headers())
    assert response.status_code == 200
    assert service.calls == [("shot", payload)]


def test_hoops_action_unknown_action_returns_404(hoops_game_client) -> None:
    client, _, service, _ = hoops_game_client
    service.next_result = StubResult("UNKNOWN_ACTION", {"action": "nonsense"})
    response = client.post("/api/hoops/action/nonsense", json={}, headers=auth_headers())
    assert response.status_code == 404


def test_hoops_action_hard_error_returns_409_with_messages(hoops_game_client) -> None:
    client, _, service, _ = hoops_game_client
    service.next_result = StubResult("PLAYER_DISQUALIFIED", {"player_id": "v1"})
    response = client.post("/api/hoops/action/substitute", json={}, headers=auth_headers())
    assert response.status_code == 409
    assert response.get_json() == {"error": "PLAYER_DISQUALIFIED", "player_id": "v1"}


def test_hoops_action_invalid_request_returns_400(hoops_game_client) -> None:
    client, _, service, _ = hoops_game_client
    service.next_result = StubResult("INVALID_REQUEST", {"message": "boom"})
    response = client.post("/api/hoops/action/foul", json={}, headers=auth_headers())
    assert response.status_code == 400
    assert response.get_json() == {"error": "INVALID_REQUEST", "message": "boom"}
