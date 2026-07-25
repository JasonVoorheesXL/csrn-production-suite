from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from flask import Blueprint, jsonify, request


RouteDecorator = Callable[[Callable[..., Any]], Callable[..., Any]]


@dataclass(frozen=True)
class SchoolRoutesDependencies:
    """Injected application boundaries used by school HTTP routes."""

    require_auth: RouteDecorator
    get_school_service: Callable[[], Any]


def create_school_blueprint(
    dependencies: SchoolRoutesDependencies,
) -> Blueprint:
    """Create school CRUD routes without constructing application services."""

    routes = Blueprint("school_routes", __name__)

    @routes.get("/api/schools")
    @dependencies.require_auth
    def list_schools():
        return jsonify(dependencies.get_school_service().list_schools())

    @routes.get("/api/schools/<school_id>")
    @dependencies.require_auth
    def read_school(school_id: str):
        result = dependencies.get_school_service().read(school_id)
        if result.code == "SCHOOL_NOT_FOUND":
            return jsonify({"error": result.code}), 404
        return jsonify(result.data["school"])

    @routes.post("/api/schools")
    @dependencies.require_auth
    def create_school():
        result = dependencies.get_school_service().create(
            request.get_json(force=True) or {}
        )
        if result.code == "SCHOOL_NAME_REQUIRED":
            return jsonify({"error": result.code}), 400
        if result.code == "LIKELY_DUPLICATE":
            return jsonify(
                {
                    "error": result.code,
                    "matches": result.data["matches"],
                }
            ), 409
        if result.code == "INVALID_SOCIAL_URL":
            return jsonify(
                {
                    "error": result.code,
                    "fields": result.data["fields"],
                }
            ), 400
        return jsonify(result.data["school"]), 201

    @routes.put("/api/schools/<school_id>")
    @dependencies.require_auth
    def update_school(school_id: str):
        result = dependencies.get_school_service().update(
            school_id,
            request.get_json(force=True) or {},
        )
        if result.code == "SCHOOL_NOT_FOUND":
            return jsonify({"error": result.code}), 404
        if result.code == "INVALID_SOCIAL_URL":
            return jsonify(
                {
                    "error": result.code,
                    "fields": result.data["fields"],
                }
            ), 400
        return jsonify(result.data["school"])

    @routes.delete("/api/schools/<school_id>")
    @dependencies.require_auth
    def delete_school(school_id: str):
        result = dependencies.get_school_service().delete(school_id)
        if result.code == "SCHOOL_NOT_FOUND":
            return jsonify({"error": result.code}), 404
        return jsonify({"ok": True})

    @routes.post("/api/schools/duplicate-check")
    @dependencies.require_auth
    def duplicate_check():
        incoming = request.get_json(force=True) or {}
        matches = dependencies.get_school_service().duplicate_candidates(
            incoming,
            str(incoming.get("exclude_id", "")),
        )
        return jsonify({"matches": matches})

    return routes
