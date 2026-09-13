"""Baseball/softball operator routes -- P4's `routes/diamond_game_routes.py`
blueprint (BASEBALL_SOFTBALL_ENGINE_SCOPING_PLAN.md P4 row), mirroring
live_game_routes.py's dependency-injection shape (a Blueprint factory
taking a frozen dataclass of injected boundaries, no direct import of the
application root) but under entirely new URLs (`/api/diamond/...`) rather
than branching football's existing `/api/score` etc. -- a deliberate round
decision to keep football's already-frozen request handlers completely
unedited.

/api/diamond/action/<action> is ONE generic mutation endpoint rather than
one Flask view per lineup/diamond action (~28 of them) -- it forwards to
DiamondGameOperationsService.dispatch(), which already resolves the action
name against ACTIONS and binds the JSON body onto that action's own
keyword arguments (see diamond_game_operations_service.py). This keeps
Flask-level code identical for every action; the only thing that varies
per request is the URL segment and the JSON body's shape, both of which
the operator UI (not yet built -- P5) will supply per action.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from flask import Blueprint, jsonify, request

import engine_router


RouteDecorator = Callable[[Callable[..., Any]], Callable[..., Any]]
State = dict[str, Any]


@dataclass(frozen=True)
class DiamondGameRoutesDependencies:
    """Injected application boundaries used by the diamond-game Blueprint."""

    require_auth: RouteDecorator
    get_diamond_operations_service: Callable[[], Any]
    load_state: Callable[[], State]


def create_diamond_game_blueprint(
    dependencies: DiamondGameRoutesDependencies,
) -> Blueprint:
    """Create baseball/softball routes without importing the application root."""

    routes = Blueprint("diamond_game_routes", __name__)

    def mutation_payload() -> dict[str, Any]:
        incoming = request.get_json(force=True) or {}
        return incoming if isinstance(incoming, dict) else {}

    @routes.post("/api/diamond/initialize")
    @dependencies.require_auth
    def initialize_diamond():
        result = dependencies.get_diamond_operations_service().initialize_diamond(
            mutation_payload()
        )
        if result.code == "NOT_A_DIAMOND_SPORT":
            return jsonify({"error": result.code}), 409
        return jsonify(result.data["state"])

    @routes.post("/api/diamond/action/<action>")
    @dependencies.require_auth
    def diamond_action(action: str):
        result = dependencies.get_diamond_operations_service().dispatch(
            action, mutation_payload()
        )
        if result.code == "UNKNOWN_ACTION":
            return jsonify({"error": result.code, "action": action}), 404
        if result.code == "NOT_A_DIAMOND_SPORT":
            return jsonify({"error": result.code}), 409
        if result.code == "INVALID_REQUEST":
            return jsonify({"error": result.code, "message": result.data.get("message", "")}), 400
        if not result.ok:
            # Every other non-OK code (HARD_ERROR, EVENT_NOT_FOUND,
            # NO_EVENTS_TO_UNDO, ALREADY_SUSPENDED, NOT_SUSPENDED, ...) is a
            # well-formed refusal from the P1/P2 service itself, not a
            # routing failure -- state is unchanged; surface the code and
            # whatever messages/data it returned instead of a bare 200.
            return jsonify({"error": result.code, **result.data}), 409
        return jsonify(result.data["state"])

    @routes.get("/api/diamond/overlay-state")
    def diamond_overlay_state():
        # Read-only, unauthenticated: the OBS overlay has no operator login
        # session, matching /api/statistics/overlay-state's existing
        # football precedent (live_game_routes.py).
        state = dependencies.load_state()
        if not engine_router.is_diamond_sport(state):
            return jsonify({"error": "NOT_A_DIAMOND_SPORT"}), 409
        return jsonify(engine_router.overlay_payload(state))

    @routes.get("/api/diamond/box-score")
    @dependencies.require_auth
    def diamond_box_score():
        state = dependencies.load_state()
        if not engine_router.is_diamond_sport(state):
            return jsonify({"error": "NOT_A_DIAMOND_SPORT"}), 409
        return jsonify(engine_router.box_score_report(state))

    return routes
