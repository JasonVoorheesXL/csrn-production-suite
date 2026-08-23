from __future__ import annotations

from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable

import pytest
from flask import Flask, jsonify, request

from routes.live_game_routes import (
    LiveGameRoutesDependencies,
    create_live_game_blueprint,
)


@dataclass(frozen=True)
class StubResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)


class StubGameOperationsService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.results: dict[str, StubResult] = {
            "score": StubResult("OK", {"state": {"home_score": 7}}),
            "set_values": StubResult("OK", {"state": {"quarter": "2"}}),
            "toggle_scorebug": StubResult("OK", {"state": {"scorebug_visible": True}}),
            "toggle_halftime": StubResult("OK", {"state": {"halftime": True}}),
            "end_game": StubResult("OK", {"state": {"status": "completed"}}),
            "reset_data": StubResult("OK", {"state": {"home_score": 0}}),
            "new_broadcast": StubResult("OK", {"state": {"broadcast_created": False}}),
        }

    def score(self, incoming: dict[str, Any]) -> StubResult:
        self.calls.append(("score", incoming))
        return self.results["score"]

    def set_values(self, incoming: dict[str, Any]) -> StubResult:
        self.calls.append(("set_values", incoming))
        return self.results["set_values"]

    def toggle_scorebug(self, incoming: dict[str, Any] | None = None) -> StubResult:
        self.calls.append(("toggle_scorebug", incoming))
        return self.results["toggle_scorebug"]

    def toggle_halftime(self, incoming: dict[str, Any] | None = None) -> StubResult:
        self.calls.append(("toggle_halftime", incoming))
        return self.results["toggle_halftime"]

    def end_game(self, incoming: dict[str, Any] | None = None) -> StubResult:
        self.calls.append(("end_game", incoming))
        return self.results["end_game"]

    def reset_data(self, incoming: dict[str, Any] | None = None) -> StubResult:
        self.calls.append(("reset_data", incoming))
        return self.results["reset_data"]

    def new_broadcast(self, incoming: dict[str, Any] | None = None) -> StubResult:
        self.calls.append(("new_broadcast", incoming))
        return self.results["new_broadcast"]


class StubEventService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.results: dict[str, StubResult] = {
            "set_control_source": StubResult("OK", {"state": {"authority": "broadcaster"}}),
            "trigger": StubResult("OK", {"state": {"event": "touchdown"}, "event": {"id": "EV-1"}}),
            "quick_correction": StubResult("OK", {"state": {"down": "2nd"}}),
            "edit": StubResult("OK", {"event": {"id": "EV-1", "description": "Edited"}}),
            "corrections": StubResult("OK", {"corrections": [{"id": "COR-1"}]}),
            "undo": StubResult("OK", {"state": {"history": []}}),
            "restore": StubResult("OK", {"state": {"history": []}}),
        }

    def set_control_source(self, authority: Any, incoming: dict[str, Any] | None = None) -> StubResult:
        self.calls.append(("set_control_source", (authority, incoming)))
        return self.results["set_control_source"]

    def trigger(self, incoming: dict[str, Any]) -> StubResult:
        self.calls.append(("trigger", incoming))
        return self.results["trigger"]

    def quick_correction(self, incoming: dict[str, Any]) -> StubResult:
        self.calls.append(("quick_correction", incoming))
        return self.results["quick_correction"]

    def edit(self, event_id: str, incoming: dict[str, Any]) -> StubResult:
        self.calls.append(("edit", (event_id, incoming)))
        return self.results["edit"]

    def corrections(self) -> StubResult:
        self.calls.append(("corrections", None))
        return self.results["corrections"]

    def undo(self, incoming: dict[str, Any] | None = None) -> StubResult:
        self.calls.append(("undo", incoming))
        return self.results["undo"]

    def restore(self, incoming: dict[str, Any] | None = None) -> StubResult:
        self.calls.append(("restore", incoming))
        return self.results["restore"]


class StubRulesService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.results: dict[str, StubResult] = {
            "clock_control": StubResult("OK", {"state": {"clock_running": True}}),
            "field_direction": StubResult("OK", {"state": {"home_direction": 1}}),
            "play": StubResult("OK", {"state": {"down": "2nd"}, "play": {"id": "P-1"}}),
        }

    def clock_control(self, incoming: dict[str, Any]) -> StubResult:
        self.calls.append(("clock_control", incoming))
        return self.results["clock_control"]

    def field_direction(self, incoming: dict[str, Any]) -> StubResult:
        self.calls.append(("field_direction", incoming))
        return self.results["field_direction"]

    def play(self, incoming: dict[str, Any]) -> StubResult:
        self.calls.append(("play", incoming))
        return self.results["play"]


class StubStatisticsService:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.result = {"home": {"score": 14}}

    def report(self, state: dict[str, Any]) -> StubResult:
        self.calls.append(state)
        return StubResult("OK", {"statistics": self.result})


@pytest.fixture
def live_game_client():
    game = StubGameOperationsService()
    events = StubEventService()
    rules = StubRulesService()
    statistics = StubStatisticsService()
    state = {"home_score": 14, "private": "hidden"}
    rosters: list[dict[str, Any]] = []

    def require_auth(view: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(view)
        def protected(*args: Any, **kwargs: Any):
            if request.headers.get("X-Test-Auth") != "yes":
                return jsonify({"error": "AUTH_REQUIRED"}), 401
            return view(*args, **kwargs)

        return protected

    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="live-game-route-test")
    app.config["_live_game_state"] = state
    app.config["_live_game_rosters"] = rosters
    app.register_blueprint(
        create_live_game_blueprint(
            LiveGameRoutesDependencies(
                require_auth=require_auth,
                get_game_operations_service=lambda: game,
                get_event_service=lambda: events,
                get_rules_service=lambda: rules,
                get_statistics_service=lambda: statistics,
                load_state=lambda: state,
                load_rosters=lambda: rosters,
            )
        )
    )
    with app.test_client() as client:
        yield client, app, game, events, rules, statistics


def auth_headers() -> dict[str, str]:
    return {"X-Test-Auth": "yes"}


def test_live_game_blueprint_registers_preserved_urls(live_game_client) -> None:
    _, app, *_ = live_game_client
    paths = {rule.rule for rule in app.url_map.iter_rules()}
    assert {
        "/api/score",
        "/api/set",
        "/api/statistics",
        "/api/control-source",
        "/api/event-trigger",
        "/api/game-correction",
        "/api/events/<event_id>/edit",
        "/api/corrections",
        "/api/toggle-scorebug",
        "/api/toggle-halftime",
        "/api/end-game",
        "/api/reset-data",
        "/api/new-broadcast",
        "/api/clock-control",
        "/api/field-direction",
        "/api/rules-play",
        "/api/undo",
    }.issubset(paths)


def test_live_game_routes_require_authentication(live_game_client) -> None:
    client, _, game, events, rules, statistics = live_game_client
    response = client.post("/api/score", json={"team": "home", "delta": 6})
    assert response.status_code == 401
    assert response.get_json() == {"error": "AUTH_REQUIRED"}
    assert game.calls == []
    assert events.calls == []
    assert rules.calls == []
    assert statistics.calls == []


def test_score_success_delegates_payload(live_game_client) -> None:
    client, _, game, *_ = live_game_client
    payload = {"team": "home", "delta": 6}
    response = client.post("/api/score", json=payload, headers=auth_headers())
    assert response.status_code == 200
    assert response.get_json() == {"home_score": 7}
    assert game.calls == [("score", payload)]


@pytest.mark.parametrize(
    ("code", "status", "payload"),
    [
        ("INVALID_SCORE_REQUEST", 400, {"error": "INVALID_SCORE_REQUEST"}),
        (
            "CONTROL_SOURCE_LOCKED",
            409,
            {"error": "CONTROL_SOURCE_LOCKED", "authority": "statistician"},
        ),
    ],
)
def test_score_error_mappings(live_game_client, code, status, payload) -> None:
    client, _, game, *_ = live_game_client
    game.results["score"] = StubResult(code, payload if code == "CONTROL_SOURCE_LOCKED" else {})
    response = client.post("/api/score", json={}, headers=auth_headers())
    assert response.status_code == status
    assert response.get_json() == payload


def test_set_values_maps_control_lock(live_game_client) -> None:
    client, _, game, *_ = live_game_client
    game.results["set_values"] = StubResult(
        "CONTROL_SOURCE_LOCKED",
        {"error": "CONTROL_SOURCE_LOCKED"},
    )
    response = client.post("/api/set", json={}, headers=auth_headers())
    assert response.status_code == 409
    assert response.get_json() == {"error": "CONTROL_SOURCE_LOCKED"}


def test_statistics_delegates_active_state(live_game_client) -> None:
    client, _, _, _, _, statistics = live_game_client
    response = client.get("/api/statistics", headers=auth_headers())
    assert response.status_code == 200
    assert response.get_json() == {"home": {"score": 14}}
    assert statistics.calls == [{"home_score": 14, "private": "hidden"}]


def test_statistics_overlay_state_is_registered_and_unauthenticated(live_game_client) -> None:
    # The OBS overlay has no operator login session (it's the public
    # /overlay page), so the Collegiate Tech rotating stat rails and
    # player-leader cards must be able to reach this without auth headers.
    client, app, _, _, _, statistics = live_game_client
    assert "/api/statistics/overlay-state" in {
        rule.rule for rule in app.url_map.iter_rules()
    }
    response = client.get("/api/statistics/overlay-state")
    assert response.status_code == 200
    assert response.get_json() == {"home": {"score": 14}}
    assert statistics.calls == [{"home_score": 14, "private": "hidden"}]


def test_statistics_decorates_player_headshots_from_active_rosters(live_game_client) -> None:
    client, app, _, _, _, statistics = live_game_client
    app.config["_live_game_state"].update(
        {
            "season": "2026",
            "sport": "Football",
            "home_school_id": "northwood",
            "visitor_school_id": "pine-valley",
        }
    )
    app.config["_live_game_rosters"].extend(
        [
            {
                "school_id": "northwood",
                "sport": "Football",
                "season": "2026",
                "players": [
                    {
                        "number": "2",
                        "first_name": "Drew",
                        "last_name": "Mason",
                        "headshot": "/roster-headshots/drew.png",
                    }
                ],
            },
            {
                "school_id": "pine-valley",
                "sport": "Football",
                "season": "2026",
                "players": [
                    {
                        "number": "88",
                        "first_name": "Receiver",
                        "last_name": "Only",
                        "headshot": "/roster-headshots/receiver.png",
                    }
                ],
            },
        ]
    )
    statistics.result = {
        "players": [
            {"team": "home", "number": "2", "name": "Drew Mason"},
            {"team": "visitor", "number": "99", "name": "Missing Player"},
        ]
    }

    response = client.get("/api/statistics", headers=auth_headers())

    assert response.status_code == 200
    players = response.get_json()["players"]
    assert players[0]["headshot"] == "/roster-headshots/drew.png"
    assert "headshot" not in players[1]


def test_control_source_maps_invalid_authority(live_game_client) -> None:
    client, _, _, events, *_ = live_game_client
    events.results["set_control_source"] = StubResult("INVALID_CONTROL_SOURCE")
    response = client.post(
        "/api/control-source",
        json={"authority": "invalid"},
        headers=auth_headers(),
    )
    assert response.status_code == 400
    assert response.get_json() == {"error": "INVALID_CONTROL_SOURCE"}


@pytest.mark.parametrize(
    ("code", "status", "payload"),
    [
        ("INVALID_EVENT", 400, {"error": "INVALID_EVENT"}),
        ("NO_ACTIVE_BROADCAST", 409, {"error": "NO_ACTIVE_BROADCAST"}),
        (
            "CONTROL_SOURCE_LOCKED",
            409,
            {"error": "CONTROL_SOURCE_LOCKED", "authority": "broadcaster"},
        ),
    ],
)
def test_event_trigger_error_mappings(live_game_client, code, status, payload) -> None:
    client, _, _, events, *_ = live_game_client
    events.results["trigger"] = StubResult(
        code,
        payload if code == "CONTROL_SOURCE_LOCKED" else {},
    )
    response = client.post("/api/event-trigger", json={}, headers=auth_headers())
    assert response.status_code == status
    assert response.get_json() == payload


@pytest.mark.parametrize("code", ["INVALID_DOWN", "INVALID_POSSESSION"])
def test_game_correction_maps_validation_errors(live_game_client, code) -> None:
    client, _, _, events, *_ = live_game_client
    events.results["quick_correction"] = StubResult(code)
    response = client.post("/api/game-correction", json={}, headers=auth_headers())
    assert response.status_code == 400
    assert response.get_json() == {"error": code}


def test_edit_event_maps_not_found(live_game_client) -> None:
    client, _, _, events, *_ = live_game_client
    events.results["edit"] = StubResult("EVENT_NOT_FOUND")
    response = client.post(
        "/api/events/missing/edit",
        json={"description": "Edit"},
        headers=auth_headers(),
    )
    assert response.status_code == 404
    assert response.get_json() == {"error": "EVENT_NOT_FOUND"}


def test_corrections_report_and_undo_delegate(live_game_client) -> None:
    client, _, _, events, *_ = live_game_client
    corrections = client.get("/api/corrections", headers=auth_headers())
    undo = client.post("/api/undo", headers=auth_headers())
    assert corrections.status_code == 200
    assert corrections.get_json() == [{"id": "COR-1"}]
    assert undo.status_code == 200
    assert undo.get_json() == {"history": []}
    assert events.calls == [("corrections", None), ("undo", {})]


def test_toggle_scorebug_maps_obs_block(live_game_client) -> None:
    client, _, game, *_ = live_game_client
    game.results["toggle_scorebug"] = StubResult(
        "OBS_COMMAND_BLOCKED",
        {"message": "Controlled OBS commands are disabled."},
    )
    response = client.post("/api/toggle-scorebug", headers=auth_headers())
    assert response.status_code == 409
    assert response.get_json() == {
        "error": "OBS_COMMAND_BLOCKED",
        "message": "Controlled OBS commands are disabled.",
    }


@pytest.mark.parametrize(
    ("path", "method", "expected"),
    [
        ("/api/toggle-halftime", "toggle_halftime", {"halftime": True}),
        ("/api/end-game", "end_game", {"status": "completed"}),
        ("/api/reset-data", "reset_data", {"home_score": 0}),
        ("/api/new-broadcast", "new_broadcast", {"broadcast_created": False}),
    ],
)
def test_simple_game_operations_preserve_state_payload(
    live_game_client,
    path,
    method,
    expected,
) -> None:
    client, _, game, *_ = live_game_client
    response = client.post(path, headers=auth_headers())
    assert response.status_code == 200
    assert response.get_json() == expected
    assert game.calls == [(method, {})]


def test_clock_control_delegates_payload(live_game_client) -> None:
    client, _, _, _, rules, _ = live_game_client
    payload = {"action": "start"}
    response = client.post(
        "/api/clock-control",
        json=payload,
        headers=auth_headers(),
    )
    assert response.status_code == 200
    assert response.get_json() == {"clock_running": True}
    assert rules.calls == [("clock_control", payload)]


def test_field_direction_maps_invalid_direction(live_game_client) -> None:
    client, _, _, _, rules, _ = live_game_client
    rules.results["field_direction"] = StubResult("INVALID_DIRECTION")
    response = client.post(
        "/api/field-direction",
        json={"team": "home", "direction": "sideways"},
        headers=auth_headers(),
    )
    assert response.status_code == 400
    assert response.get_json() == {"error": "INVALID_DIRECTION"}


@pytest.mark.parametrize(
    ("code", "status", "payload"),
    [
        ("INVALID_PLAY", 400, {"error": "INVALID_PLAY"}),
        ("NO_ACTIVE_BROADCAST", 409, {"error": "NO_ACTIVE_BROADCAST"}),
        (
            "CONTROL_SOURCE_LOCKED",
            409,
            {"error": "CONTROL_SOURCE_LOCKED", "authority": "statistician"},
        ),
    ],
)
def test_rules_play_error_mappings(live_game_client, code, status, payload) -> None:
    client, _, _, _, rules, _ = live_game_client
    rules.results["play"] = StubResult(
        code,
        payload if code == "CONTROL_SOURCE_LOCKED" else {},
    )
    response = client.post("/api/rules-play", json={}, headers=auth_headers())
    assert response.status_code == status
    assert response.get_json() == payload


