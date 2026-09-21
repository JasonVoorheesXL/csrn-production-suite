"""Basketball operator routes -- P4's `routes/hoops_game_routes.py`
blueprint (docs/BASKETBALL_ENGINE_SCOPING_PLAN.md P4 row), mirroring
routes/diamond_game_routes.py's shape (itself mirroring live_game_routes.py's
dependency-injection pattern: a Blueprint factory taking a frozen
dataclass of injected boundaries, no direct import of the application
root) but under entirely new URLs (`/api/hoops/...`) rather than
branching football's existing `/api/score` etc. -- the same deliberate
round decision baseball made, keeping football's already-frozen request
handlers completely unedited.

/api/hoops/action/<action> is ONE generic mutation endpoint rather than
one Flask view per shot/foul/free-throw/rebound/lineup action -- it
forwards to HoopsGameOperationsService.dispatch(), which already resolves
the action name against ACTIONS and binds the JSON body onto that
action's own keyword arguments (see hoops_game_operations_service.py).
This keeps Flask-level code identical for every action; the only thing
that varies per request is the URL segment and the JSON body's shape,
both of which the operator UI (not yet built -- P5) will supply per
action.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from flask import Blueprint, jsonify, request

import engine_router


RouteDecorator = Callable[[Callable[..., Any]], Callable[..., Any]]
State = dict[str, Any]


@dataclass(frozen=True)
class HoopsGameRoutesDependencies:
    """Injected application boundaries used by the hoops-game Blueprint."""

    require_auth: RouteDecorator
    get_hoops_operations_service: Callable[[], Any]
    load_state: Callable[[], State]
    # Basketball panel feed (hoops_overlay_panel.py): leaders, team totals, last
    # basket, who is on the floor -- resolved against the roster server-side.
    get_panel_service: Callable[[], Any] | None = None


def create_hoops_game_blueprint(
    dependencies: HoopsGameRoutesDependencies,
) -> Blueprint:
    """Create basketball routes without importing the application root."""

    routes = Blueprint("hoops_game_routes", __name__)

    def mutation_payload() -> dict[str, Any]:
        incoming = request.get_json(force=True) or {}
        return incoming if isinstance(incoming, dict) else {}

    @routes.post("/api/hoops/initialize")
    @dependencies.require_auth
    def initialize_hoops():
        result = dependencies.get_hoops_operations_service().initialize_hoops(
            mutation_payload()
        )
        if result.code == "NOT_A_HOOPS_SPORT":
            return jsonify({"error": result.code}), 409
        return jsonify(result.data["state"])

    @routes.post("/api/hoops/action/<action>")
    @dependencies.require_auth
    def hoops_action(action: str):
        result = dependencies.get_hoops_operations_service().dispatch(
            action, mutation_payload()
        )
        if result.code == "UNKNOWN_ACTION":
            return jsonify({"error": result.code, "action": action}), 404
        if result.code == "NOT_A_HOOPS_SPORT":
            return jsonify({"error": result.code}), 409
        if result.code == "INVALID_REQUEST":
            return jsonify({"error": result.code, "message": result.data.get("message", "")}), 400
        if not result.ok:
            # Every other non-OK code (a P1/P2 refusal such as
            # PLAYER_DISQUALIFIED, EVENT_NOT_FOUND, NO_EVENTS_TO_UNDO,
            # CANNOT_UNDO_GAME_START, ...) is a well-formed refusal from
            # the service itself, not a routing failure -- state is
            # unchanged; surface the code and whatever data it returned
            # instead of a bare 200.
            return jsonify({"error": result.code, **result.data}), 409
        return jsonify(result.data["state"])

    @routes.get("/api/hoops/overlay-state")
    def hoops_overlay_state():
        # Read-only, unauthenticated: the OBS overlay has no operator login
        # session, matching /api/diamond/overlay-state's own precedent
        # (itself matching /api/statistics/overlay-state, football's).
        state = dependencies.load_state()
        if not engine_router.is_hoops_sport(state):
            return jsonify({"error": "NOT_A_HOOPS_SPORT"}), 409
        return jsonify(engine_router.hoops_overlay_payload(state))

    @routes.get("/api/hoops/panel-state")
    def hoops_panel_state():
        # Read-only, unauthenticated, like /api/hoops/overlay-state: the OBS
        # overlay's Collegiate basketball board (team snapshot rails, player
        # leader cards, last-basket callout) has no login session and no
        # roster access, so the names are resolved here.
        state = dependencies.load_state()
        if not engine_router.is_hoops_sport(state):
            return jsonify({"error": "NOT_A_HOOPS_SPORT"}), 409
        service = dependencies.get_panel_service() if dependencies.get_panel_service else None
        if service is None:
            return jsonify({"error": "PANEL_UNAVAILABLE"}), 503
        try:
            return jsonify(service.panel(state))
        except Exception:  # a derived, cosmetic feed: never a 500 for the overlay
            return jsonify({"leaders": {"home": None, "visitor": None}, "team_stats": {}, "last_basket": None, "on_floor": {"home": [], "visitor": []}})

    @routes.get("/api/hoops/box-score")
    @dependencies.require_auth
    def hoops_box_score():
        state = dependencies.load_state()
        if not engine_router.is_hoops_sport(state):
            return jsonify({"error": "NOT_A_HOOPS_SPORT"}), 409
        return jsonify(engine_router.hoops_box_score_report(state))

    return routes
