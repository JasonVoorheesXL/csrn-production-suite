from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from flask import Blueprint, jsonify, request


RouteDecorator = Callable[[Callable[..., Any]], Callable[..., Any]]


@dataclass(frozen=True)
class BroadcastPackageRoutesDependencies:
    require_auth: RouteDecorator
    get_package_service: Callable[[], Any]
    public_state: Callable[[dict[str, Any]], dict[str, Any]]


def create_broadcast_package_blueprint(
    dependencies: BroadcastPackageRoutesDependencies,
) -> Blueprint:
    routes = Blueprint("broadcast_package_routes", __name__)

    @routes.get("/api/packages")
    @dependencies.require_auth
    def list_packages_route():
        return jsonify(dependencies.get_package_service().list_packages())

    @routes.post("/api/packages")
    @dependencies.require_auth
    def create_package_route():
        result = dependencies.get_package_service().create(
            request.get_json(force=True) or {}
        )
        return jsonify(result.data["package"]), 201

    @routes.put("/api/packages/<package_id>")
    @dependencies.require_auth
    def update_package_route(package_id: str):
        result = dependencies.get_package_service().update(
            package_id,
            request.get_json(force=True) or {},
        )
        if result.code == "NOT_FOUND":
            return jsonify({"error": result.code}), 404
        if result.code == "PACKAGE_LOCKED":
            return jsonify({"error": result.code}), 409
        return jsonify(result.data["package"])

    @routes.delete("/api/packages/<package_id>")
    @dependencies.require_auth
    def delete_package_route(package_id: str):
        result = dependencies.get_package_service().delete(package_id)
        if result.code == "NOT_FOUND":
            return jsonify({"error": result.code}), 404
        if result.code == "PACKAGE_LOCKED":
            return jsonify({"error": result.code}), 409
        return jsonify({"deleted": result.data["deleted"]})

    @routes.post("/api/packages/<package_id>/duplicate")
    @dependencies.require_auth
    def duplicate_package_route(package_id: str):
        result = dependencies.get_package_service().duplicate(package_id)
        if result.code == "NOT_FOUND":
            return jsonify({"error": result.code}), 404
        return jsonify(result.data["package"]), 201

    @routes.post("/api/packages/<package_id>/load")
    @dependencies.require_auth
    def load_package_route(package_id: str):
        result = dependencies.get_package_service().load(package_id)
        if result.code == "NOT_FOUND":
            return jsonify({"error": result.code}), 404
        if result.code == "BROADCAST_NOT_FOUND":
            return jsonify({"error": result.code}), 409
        return jsonify(
            {
                "package": result.data["package"],
                "state": dependencies.public_state(result.data["state"]),
                "health": result.data["health"],
            }
        )

    return routes
