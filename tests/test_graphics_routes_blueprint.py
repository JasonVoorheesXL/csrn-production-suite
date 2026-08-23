from __future__ import annotations

from dataclasses import dataclass, field
from functools import wraps
from threading import Lock
from typing import Any, Callable

import pytest
from flask import Flask, jsonify, request

from routes.graphics_routes import (
    GraphicsRoutesDependencies,
    create_graphics_blueprint,
)


@dataclass(frozen=True)
class StubResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)


class StubGraphicsService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.lower_result = StubResult(
            "OK",
            {"state": {"marker": "lower", "private": "hidden"}},
        )
        self.player_result = StubResult(
            "OK",
            {
                "state": {"marker": "player", "private": "hidden"},
                "sponsor_warning": "",
            },
        )
        self.personnel_result = StubResult(
            "OK",
            {
                "state": {"marker": "personnel", "private": "hidden"},
                "sponsor_warning": "",
            },
        )

    def update_lower_third(self, state: dict[str, Any], incoming: dict[str, Any]) -> StubResult:
        self.calls.append(("lower", (state, incoming)))
        return self.lower_result

    def update_player(self, state: dict[str, Any], incoming: dict[str, Any]) -> StubResult:
        self.calls.append(("player", (state, incoming)))
        return self.player_result

    def update_personnel(self, state: dict[str, Any], incoming: dict[str, Any]) -> StubResult:
        self.calls.append(("personnel", (state, incoming)))
        return self.personnel_result


@pytest.fixture
def graphics_client():
    service = StubGraphicsService()
    saved: list[dict[str, Any]] = []

    def require_auth(view: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(view)
        def protected(*args: Any, **kwargs: Any):
            if request.headers.get("X-Test-Auth") != "yes":
                return jsonify({"error": "AUTH_REQUIRED"}), 401
            return view(*args, **kwargs)

        return protected

    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="graphics-route-test")
    app.register_blueprint(
        create_graphics_blueprint(
            GraphicsRoutesDependencies(
                require_auth=require_auth,
                get_graphics_service=lambda: service,
                load_state=lambda: {"marker": "before", "private": "secret"},
                save_state=lambda state: saved.append(dict(state)),
                public_state=lambda state: {"marker": state["marker"]},
                transaction_lock=Lock(),
            )
        )
    )
    with app.test_client() as client:
        yield client, app, service, saved


def auth_headers() -> dict[str, str]:
    return {"X-Test-Auth": "yes"}


def test_graphics_blueprint_registers_preserved_urls(graphics_client) -> None:
    _, app, _, _ = graphics_client
    rules = {
        (rule.rule, tuple(sorted(rule.methods - {"HEAD", "OPTIONS"})))
        for rule in app.url_map.iter_rules()
    }
    assert ("/api/graphics/lower-third", ("POST",)) in rules
    assert ("/api/graphics/player", ("POST",)) in rules
    assert ("/api/graphics/personnel", ("POST",)) in rules
    assert ("/api/graphics/sponsor-spotlight", ("POST",)) in rules
    assert ("/api/graphics/player-highlight", ("POST",)) in rules
    assert ("/api/graphics/queue", ("POST",)) in rules


def test_graphics_routes_require_authentication(graphics_client) -> None:
    client, _, service, saved = graphics_client
    response = client.post("/api/graphics/lower-third", json={"action": "show"})
    assert response.status_code == 401
    assert response.get_json() == {"error": "AUTH_REQUIRED"}
    assert service.calls == []
    assert saved == []


def test_lower_third_delegates_persists_and_filters_state(graphics_client) -> None:
    client, _, service, saved = graphics_client
    payload = {"action": "show", "headline": "Touchdown"}
    response = client.post(
        "/api/graphics/lower-third",
        json=payload,
        headers=auth_headers(),
    )
    assert response.status_code == 200
    assert response.get_json() == {"marker": "lower"}
    assert service.calls == [
        ("lower", ({"marker": "before", "private": "secret"}, payload))
    ]
    assert saved == [{"marker": "lower", "private": "hidden"}]


def test_player_route_maps_required_player(graphics_client) -> None:
    client, _, service, saved = graphics_client
    service.player_result = StubResult("PLAYER_REQUIRED")
    response = client.post(
        "/api/graphics/player",
        json={"action": "show"},
        headers=auth_headers(),
    )
    assert response.status_code == 400
    assert response.get_json() == {"error": "PLAYER_REQUIRED"}
    assert saved == []


def test_player_route_preserves_sponsor_warning(graphics_client) -> None:
    client, _, service, saved = graphics_client
    service.player_result = StubResult(
        "OK",
        {
            "state": {"marker": "player", "private": "hidden"},
            "sponsor_warning": "Sponsor asset is inactive.",
        },
    )
    response = client.post(
        "/api/graphics/player",
        json={"action": "show", "player_id": "player-1"},
        headers=auth_headers(),
    )
    assert response.status_code == 200
    assert response.get_json() == {
        "marker": "player",
        "sponsor_warning": "Sponsor asset is inactive.",
    }
    assert saved == [{"marker": "player", "private": "hidden"}]


def test_personnel_route_maps_required_personnel(graphics_client) -> None:
    client, _, service, saved = graphics_client
    service.personnel_result = StubResult("PERSONNEL_REQUIRED")
    response = client.post(
        "/api/graphics/personnel",
        json={"action": "show"},
        headers=auth_headers(),
    )
    assert response.status_code == 400
    assert response.get_json() == {"error": "PERSONNEL_REQUIRED"}
    assert saved == []


def test_personnel_route_preserves_sponsor_warning(graphics_client) -> None:
    client, _, service, saved = graphics_client
    service.personnel_result = StubResult(
        "OK",
        {
            "state": {"marker": "personnel", "private": "hidden"},
            "sponsor_warning": "Sponsor logo is missing.",
        },
    )
    response = client.post(
        "/api/graphics/personnel",
        json={"action": "show", "personnel_id": "person-1"},
        headers=auth_headers(),
    )
    assert response.status_code == 200
    assert response.get_json() == {
        "marker": "personnel",
        "sponsor_warning": "Sponsor logo is missing.",
    }
    assert saved == [{"marker": "personnel", "private": "hidden"}]


