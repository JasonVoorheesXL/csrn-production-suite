from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from flask import Blueprint, jsonify


RouteDecorator = Callable[[Callable[..., Any]], Callable[..., Any]]


@dataclass(frozen=True)
class BroadcastLifecycleRoutesDependencies:
    require_auth: RouteDecorator
    get_lifecycle_service: Callable[[], Any]


def create_broadcast_lifecycle_blueprint(
    dependencies: BroadcastLifecycleRoutesDependencies,
) -> Blueprint:
    routes = Blueprint("broadcast_lifecycle_routes", __name__)

    @routes.post("/api/broadcasts/<broadcast_id>/load")
    @dependencies.require_auth
    def load_planned_broadcast(broadcast_id: str):
        result = dependencies.get_lifecycle_service().load(broadcast_id)
        if result.code == "NOT_FOUND":
            return jsonify({"error": result.code}), 404
        return jsonify(result.data["state"])

    @routes.post("/api/initialize-broadcast")
    @dependencies.require_auth
    def initialize_broadcast():
        result = dependencies.get_lifecycle_service().initialize()
        if result.code == "NO_ACTIVE_BROADCAST":
            return jsonify({"error": result.code}), 409
        return jsonify(result.data)

    @routes.post("/api/start-broadcast")
    @dependencies.require_auth
    def start_broadcast():
        result = dependencies.get_lifecycle_service().start()
        if result.code == "NO_ACTIVE_BROADCAST":
            return jsonify({"error": result.code}), 409
        return jsonify(result.data)

    @routes.post("/api/resume-broadcast")
    @dependencies.require_auth
    def resume_broadcast():
        result = dependencies.get_lifecycle_service().resume()
        if result.code == "NO_ACTIVE_BROADCAST":
            return jsonify({"error": result.code}), 409
        return jsonify(result.data["state"])

    return routes
