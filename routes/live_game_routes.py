from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from flask import Blueprint, jsonify, request


RouteDecorator = Callable[[Callable[..., Any]], Callable[..., Any]]
State = dict[str, Any]


@dataclass(frozen=True)
class LiveGameRoutesDependencies:
    """Injected application boundaries used by the live-game Blueprint."""

    require_auth: RouteDecorator
    get_game_operations_service: Callable[[], Any]
    get_event_service: Callable[[], Any]
    get_rules_service: Callable[[], Any]
    get_statistics_service: Callable[[], Any]
    load_state: Callable[[], State]


def create_live_game_blueprint(
    dependencies: LiveGameRoutesDependencies,
) -> Blueprint:
    """Create live-game routes without importing the application root."""

    routes = Blueprint("live_game_routes", __name__)

    @routes.post("/api/score")
    @dependencies.require_auth
    def update_score():
        result = dependencies.get_game_operations_service().score(
            request.get_json(force=True) or {}
        )
        if result.code == "INVALID_SCORE_REQUEST":
            return jsonify({"error": result.code}), 400
        if result.code == "CONTROL_SOURCE_LOCKED":
            return jsonify(result.data), 409
        return jsonify(result.data["state"])

    @routes.post("/api/set")
    @dependencies.require_auth
    def set_value():
        result = dependencies.get_game_operations_service().set_values(
            request.get_json(force=True) or {}
        )
        if result.code == "CONTROL_SOURCE_LOCKED":
            return jsonify(result.data), 409
        return jsonify(result.data["state"])

    @routes.get("/api/statistics")
    @dependencies.require_auth
    def statistics_report():
        result = dependencies.get_statistics_service().report(
            dependencies.load_state()
        )
        return jsonify(result.data["statistics"])

    @routes.post("/api/control-source")
    @dependencies.require_auth
    def set_control_source():
        incoming = request.get_json(force=True) or {}
        result = dependencies.get_event_service().set_control_source(
            incoming.get("authority", "")
        )
        if result.code == "INVALID_CONTROL_SOURCE":
            return jsonify({"error": result.code}), 400
        return jsonify(result.data["state"])

    @routes.post("/api/event-trigger")
    @dependencies.require_auth
    def event_trigger():
        result = dependencies.get_event_service().trigger(
            request.get_json(force=True) or {}
        )
        if result.code == "INVALID_EVENT":
            return jsonify({"error": result.code}), 400
        if result.code == "NO_ACTIVE_BROADCAST":
            return jsonify({"error": result.code}), 409
        if result.code == "CONTROL_SOURCE_LOCKED":
            return jsonify(result.data), 409
        return jsonify(result.data)

    @routes.post("/api/game-correction")
    @dependencies.require_auth
    def game_correction():
        result = dependencies.get_event_service().quick_correction(
            request.get_json(force=True) or {}
        )
        if result.code in {"INVALID_DOWN", "INVALID_POSSESSION"}:
            return jsonify({"error": result.code}), 400
        if result.code == "CONTROL_SOURCE_LOCKED":
            return jsonify(result.data), 409
        return jsonify(result.data["state"])

    @routes.post("/api/events/<event_id>/edit")
    @dependencies.require_auth
    def edit_event(event_id: str):
        result = dependencies.get_event_service().edit(
            event_id,
            request.get_json(force=True) or {},
        )
        if result.code == "EVENT_NOT_FOUND":
            return jsonify({"error": result.code}), 404
        if result.code == "CONTROL_SOURCE_LOCKED":
            return jsonify(result.data), 409
        return jsonify(result.data)

    @routes.get("/api/corrections")
    @dependencies.require_auth
    def corrections_report():
        result = dependencies.get_event_service().corrections()
        return jsonify(result.data["corrections"])

    @routes.post("/api/toggle-scorebug")
    @dependencies.require_auth
    def toggle_scorebug():
        result = dependencies.get_game_operations_service().toggle_scorebug()
        if result.code == "OBS_COMMAND_BLOCKED":
            return jsonify(
                {
                    "error": result.code,
                    "message": result.data.get("message", ""),
                }
            ), 409
        return jsonify(result.data["state"])

    @routes.post("/api/toggle-halftime")
    @dependencies.require_auth
    def toggle_halftime():
        result = dependencies.get_game_operations_service().toggle_halftime()
        return jsonify(result.data["state"])

    @routes.post("/api/end-game")
    @dependencies.require_auth
    def end_game():
        result = dependencies.get_game_operations_service().end_game()
        return jsonify(result.data["state"])

    @routes.post("/api/reset-data")
    @dependencies.require_auth
    def reset_data():
        result = dependencies.get_game_operations_service().reset_data()
        return jsonify(result.data["state"])

    @routes.post("/api/new-broadcast")
    @dependencies.require_auth
    def new_broadcast():
        result = dependencies.get_game_operations_service().new_broadcast()
        return jsonify(result.data["state"])

    @routes.post("/api/clock-control")
    @dependencies.require_auth
    def clock_control():
        result = dependencies.get_rules_service().clock_control(
            request.get_json(force=True) or {}
        )
        return jsonify(result.data["state"])

    @routes.post("/api/field-direction")
    @dependencies.require_auth
    def field_direction():
        result = dependencies.get_rules_service().field_direction(
            request.get_json(force=True) or {}
        )
        if result.code == "INVALID_DIRECTION":
            return jsonify({"error": result.code}), 400
        return jsonify(result.data["state"])

    @routes.post("/api/rules-play")
    @dependencies.require_auth
    def rules_play():
        result = dependencies.get_rules_service().play(
            request.get_json(force=True) or {}
        )
        if result.code == "INVALID_PLAY":
            return jsonify({"error": result.code}), 400
        if result.code == "NO_ACTIVE_BROADCAST":
            return jsonify({"error": result.code}), 409
        if result.code == "CONTROL_SOURCE_LOCKED":
            return jsonify(result.data), 409
        return jsonify(result.data)

    @routes.post("/api/undo")
    @dependencies.require_auth
    def undo():
        result = dependencies.get_event_service().undo()
        return jsonify(result.data["state"])

    return routes
