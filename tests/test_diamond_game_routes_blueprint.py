from __future__ import annotations

from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable

import pytest
from flask import Flask, jsonify, request

from routes.diamond_game_routes import (
    DiamondGameRoutesDependencies,
    create_diamond_game_blueprint,
)


@dataclass(frozen=True)
class StubResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.code == "OK"


class StubDiamondOperationsService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.next_result = StubResult("OK", {"state": {"diamond": {"inning": 1}}})

    def initialize_diamond(self, payload: dict[str, Any] | None = None) -> StubResult:
        self.calls.append(("initialize_diamond", payload))
        return self.next_result

    def dispatch(self, action: str, payload: dict[str, Any] | None = None) -> StubResult:
        self.calls.append((action, payload))
        return self.next_result


@pytest.fixture
def diamond_game_client():
    service = StubDiamondOperationsService()
    state = {"sport": "baseball", "diamond": {"inning": 3}}

    def require_auth(view: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(view)
        def protected(*args: Any, **kwargs: Any):
            if request.headers.get("X-Test-Auth") != "yes":
                return jsonify({"error": "AUTH_REQUIRED"}), 401
            return view(*args, **kwargs)

        return protected

    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="diamond-game-route-test")
    app.register_blueprint(
        create_diamond_game_blueprint(
            DiamondGameRoutesDependencies(
                require_auth=require_auth,
                get_diamond_operations_service=lambda: service,
                load_state=lambda: state,
            )
        )
    )
    with app.test_client() as client:
        yield client, app, service, state


def auth_headers() -> dict[str, str]:
    return {"X-Test-Auth": "yes"}


def test_diamond_blueprint_registers_the_new_urls_only(diamond_game_client) -> None:
    _, app, *_ = diamond_game_client
    paths = {rule.rule for rule in app.url_map.iter_rules()}
    assert {
        "/api/diamond/initialize",
        "/api/diamond/action/<action>",
        "/api/diamond/overlay-state",
        "/api/diamond/box-score",
    }.issubset(paths)
    # Football's own URLs must never appear here -- this blueprint owns
    # nothing under those paths.
    assert "/api/score" not in paths
    assert "/api/set" not in paths


def test_mutation_routes_require_authentication(diamond_game_client) -> None:
    client, _, _, _ = diamond_game_client
    response = client.post("/api/diamond/initialize", json={})
    assert response.status_code == 401
    response = client.post("/api/diamond/action/substitute", json={})
    assert response.status_code == 401


def test_overlay_state_is_unauthenticated(diamond_game_client) -> None:
    client, _, _, _ = diamond_game_client
    response = client.get("/api/diamond/overlay-state")
    assert response.status_code == 200
    assert response.get_json()["inning"] == 3


def test_box_score_requires_authentication(diamond_game_client) -> None:
    client, _, _, _ = diamond_game_client
    response = client.get("/api/diamond/box-score")
    assert response.status_code == 401


def test_diamond_reporting_routes_reject_a_football_state(diamond_game_client) -> None:
    client, _, _, state = diamond_game_client
    state.clear()
    state.update({"sport": "Football"})
    overlay = client.get("/api/diamond/overlay-state")
    assert overlay.status_code == 409
    assert overlay.get_json() == {"error": "NOT_A_DIAMOND_SPORT"}

    box_score = client.get("/api/diamond/box-score", headers=auth_headers())
    assert box_score.status_code == 409


def test_initialize_diamond_forwards_the_payload_and_returns_state(diamond_game_client) -> None:
    client, _, service, _ = diamond_game_client
    response = client.post("/api/diamond/initialize", json={"command_id": "c1"}, headers=auth_headers())
    assert response.status_code == 200
    assert response.get_json() == {"diamond": {"inning": 1}}
    assert service.calls == [("initialize_diamond", {"command_id": "c1"})]


def test_diamond_action_forwards_the_action_name_and_payload(diamond_game_client) -> None:
    client, _, service, _ = diamond_game_client
    payload = {"side": "home", "slot": 3, "incoming_player_id": "p9"}
    response = client.post("/api/diamond/action/substitute", json=payload, headers=auth_headers())
    assert response.status_code == 200
    assert service.calls == [("substitute", payload)]


def test_diamond_action_unknown_action_returns_404(diamond_game_client) -> None:
    client, _, service, _ = diamond_game_client
    service.next_result = StubResult("UNKNOWN_ACTION", {"action": "nonsense"})
    response = client.post("/api/diamond/action/nonsense", json={}, headers=auth_headers())
    assert response.status_code == 404


def test_diamond_action_hard_error_returns_409_with_messages(diamond_game_client) -> None:
    client, _, service, _ = diamond_game_client
    service.next_result = StubResult("HARD_ERROR", {"messages": ["bad payload"]})
    response = client.post("/api/diamond/action/record_plate_appearance", json={}, headers=auth_headers())
    assert response.status_code == 409
    assert response.get_json() == {"error": "HARD_ERROR", "messages": ["bad payload"]}


def test_diamond_action_invalid_request_returns_400(diamond_game_client) -> None:
    client, _, service, _ = diamond_game_client
    service.next_result = StubResult("INVALID_REQUEST", {"message": "boom"})
    response = client.post("/api/diamond/action/substitute", json={}, headers=auth_headers())
    assert response.status_code == 400
    assert response.get_json() == {"error": "INVALID_REQUEST", "message": "boom"}
