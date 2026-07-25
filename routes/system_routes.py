from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from flask import Blueprint, jsonify, request


RouteDecorator = Callable[[Callable[..., Any]], Callable[..., Any]]


@dataclass(frozen=True)
class SystemRoutesDependencies:
    """Injected application boundaries used by the system-routes Blueprint."""

    require_auth: RouteDecorator
    get_configuration_service: Callable[[], Any]
    diagnostic_status: Callable[[], Mapping[str, Any]]
    load_state: Callable[[], Mapping[str, Any]]
    public_state: Callable[[Mapping[str, Any]], Mapping[str, Any]]
    readiness_payload: Callable[[], Mapping[str, Any]]
    load_build_journal: Callable[[], Any]


def create_system_blueprint(
    dependencies: SystemRoutesDependencies,
) -> Blueprint:
    """Create the first Phase 5 route Blueprint without owning business logic."""

    routes = Blueprint("system_routes", __name__)

    @routes.get("/api/config")
    @dependencies.require_auth
    def get_config():
        result = dependencies.get_configuration_service().read()
        return jsonify(result.data["config"])

    @routes.post("/api/config")
    @dependencies.require_auth
    def update_config():
        incoming = request.get_json(force=True)
        result = dependencies.get_configuration_service().update(incoming)
        if result.code == "CONFIG_PAYLOAD_REQUIRED":
            return jsonify({"error": result.code}), 400
        if result.code == "INVALID_SOCIAL_URL":
            return jsonify(
                {
                    "error": result.code,
                    "fields": result.data.get("fields", {}),
                }
            ), 400
        return jsonify(result.data["config"])

    @routes.get("/api/diagnostics")
    @dependencies.require_auth
    def diagnostics():
        return jsonify(dict(dependencies.diagnostic_status()))

    @routes.get("/api/state")
    def get_state():
        # Read-only endpoint for authenticated controls and the OBS overlay.
        state = dependencies.load_state()
        return jsonify(dict(dependencies.public_state(state)))

    @routes.get("/api/readiness")
    @dependencies.require_auth
    def readiness():
        return jsonify(dict(dependencies.readiness_payload()))

    @routes.get("/api/build-journal")
    @dependencies.require_auth
    def build_journal():
        return jsonify(dependencies.load_build_journal())

    return routes
