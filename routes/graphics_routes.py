from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from flask import Blueprint, jsonify, request


RouteDecorator = Callable[[Callable[..., Any]], Callable[..., Any]]
State = dict[str, Any]


@dataclass(frozen=True)
class GraphicsRoutesDependencies:
    """Injected application boundaries used by the graphics Blueprint."""

    require_auth: RouteDecorator
    get_graphics_service: Callable[[], Any]
    load_state: Callable[[], State]
    save_state: Callable[[State], None]
    public_state: Callable[[State], State]
    transaction_lock: Any


def create_graphics_blueprint(
    dependencies: GraphicsRoutesDependencies,
) -> Blueprint:
    """Create graphics routes while leaving graphic behavior in the service."""

    routes = Blueprint("graphics_routes", __name__)

    @routes.post("/api/graphics/lower-third")
    @dependencies.require_auth
    def update_lower_third():
        incoming = request.get_json(force=True) or {}
        with dependencies.transaction_lock:
            result = dependencies.get_graphics_service().update_lower_third(
                dependencies.load_state(),
                incoming,
            )
            state = result.data["state"]
            dependencies.save_state(state)
        return jsonify(dependencies.public_state(state))

    @routes.post("/api/graphics/player")
    @dependencies.require_auth
    def update_player_graphic():
        incoming = request.get_json(force=True) or {}
        with dependencies.transaction_lock:
            result = dependencies.get_graphics_service().update_player(
                dependencies.load_state(),
                incoming,
            )
            if result.code == "PLAYER_REQUIRED":
                return jsonify({"error": result.code}), 400
            state = result.data["state"]
            dependencies.save_state(state)
        response = dependencies.public_state(state)
        warning = str(result.data.get("sponsor_warning", ""))
        if warning:
            response["sponsor_warning"] = warning
        return jsonify(response)

    @routes.post("/api/graphics/sponsor-spotlight")
    @dependencies.require_auth
    def update_sponsor_spotlight():
        incoming = request.get_json(force=True) or {}
        with dependencies.transaction_lock:
            result = dependencies.get_graphics_service().update_sponsor_spotlight(
                dependencies.load_state(),
                incoming,
            )
            if result.code in {
                "SPONSOR_REQUIRED",
                "SPONSOR_MEDIA_REQUIRED",
                "SPONSOR_MEDIA_NOT_APPROVED",
            }:
                return jsonify({"error": result.code}), 400
            state = result.data["state"]
            dependencies.save_state(state)
        response = dependencies.public_state(state)
        warning = str(result.data.get("sponsor_warning", ""))
        if warning:
            response["sponsor_warning"] = warning
        return jsonify(response)

    @routes.post("/api/graphics/queue")
    @dependencies.require_auth
    def update_graphics_queue():
        incoming = request.get_json(force=True) or {}
        with dependencies.transaction_lock:
            result = dependencies.get_graphics_service().update_queue(
                dependencies.load_state(),
                incoming,
            )
            if result.code == "INVALID_QUEUE_ACTION":
                return jsonify({"error": result.code}), 400
            state = result.data["state"]
            dependencies.save_state(state)
        return jsonify(dependencies.public_state(state))

    @routes.post("/api/graphics/personnel")
    @dependencies.require_auth
    def update_personnel_graphic():
        incoming = request.get_json(force=True) or {}
        with dependencies.transaction_lock:
            result = dependencies.get_graphics_service().update_personnel(
                dependencies.load_state(),
                incoming,
            )
            if result.code == "PERSONNEL_REQUIRED":
                return jsonify({"error": result.code}), 400
            state = result.data["state"]
            dependencies.save_state(state)
        response = dependencies.public_state(state)
        warning = str(result.data.get("sponsor_warning", ""))
        if warning:
            response["sponsor_warning"] = warning
        return jsonify(response)

    return routes
