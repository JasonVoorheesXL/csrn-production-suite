from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from flask import Blueprint, jsonify, request


RouteDecorator = Callable[[Callable[..., Any]], Callable[..., Any]]


@dataclass(frozen=True)
class CommissioningRoutesDependencies:
    """Injected application boundaries used by commissioning routes."""

    require_auth: RouteDecorator
    get_commissioning_service: Callable[[], Any]


def create_commissioning_blueprint(
    dependencies: CommissioningRoutesDependencies,
) -> Blueprint:
    routes = Blueprint("commissioning_routes", __name__)

    @routes.get("/api/game-day/commissioning")
    @dependencies.require_auth
    def get_commissioning_profile():
        result = dependencies.get_commissioning_service().load()
        return jsonify(result.data)

    @routes.put("/api/game-day/commissioning")
    @dependencies.require_auth
    def update_commissioning_profile():
        result = dependencies.get_commissioning_service().update_profile(
            request.get_json(silent=True)
        )
        if result.code == "PROFILE_MUST_BE_OBJECT":
            return jsonify({"error": result.code}), 400
        return jsonify({"code": result.code, **result.data})

    @routes.post("/api/game-day/commissioning/check")
    @dependencies.require_auth
    def update_commissioning_check():
        incoming = request.get_json(silent=True) or {}
        result = dependencies.get_commissioning_service().set_check(
            section=incoming.get("section"),
            key=incoming.get("key"),
            passed=incoming.get("passed"),
            note=incoming.get("note", ""),
        )
        status = {
            "INVALID_CHECK_SECTION": 400,
            "INVALID_CHECK_KEY": 400,
            "PASSED_MUST_BE_BOOLEAN": 400,
        }.get(result.code, 200)
        return jsonify({"code": result.code, **result.data}), status

    @routes.post("/api/game-day/commissioning/obs-test")
    @dependencies.require_auth
    def run_commissioning_obs_test():
        result = dependencies.get_commissioning_service().run_obs_check()
        return jsonify({"code": result.code, **result.data})

    @routes.get("/api/game-day/commissioning/report")
    @dependencies.require_auth
    def get_commissioning_report():
        result = dependencies.get_commissioning_service().report()
        status = 200 if result.code == "COMMISSIONING_READY" else 409
        return jsonify({"code": result.code, **result.data}), status

    return routes
