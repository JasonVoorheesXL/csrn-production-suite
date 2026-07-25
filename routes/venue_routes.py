from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from flask import Blueprint, jsonify, request


RouteDecorator = Callable[[Callable[..., Any]], Callable[..., Any]]


@dataclass(frozen=True)
class VenueRoutesDependencies:
    require_auth: RouteDecorator
    get_venue_service: Callable[[], Any]


def create_venue_blueprint(
    dependencies: VenueRoutesDependencies,
) -> Blueprint:
    routes = Blueprint("venue_routes", __name__)

    @routes.get("/api/venues")
    @dependencies.require_auth
    def list_venues():
        include_inactive = str(
            request.args.get("include_inactive", "true")
        ).strip().lower() not in {"0", "false", "no", "off"}
        result = dependencies.get_venue_service().list_venues(
            school_id=str(request.args.get("school_id", "")),
            sport=str(request.args.get("sport", "")),
            include_inactive=include_inactive,
        )
        return jsonify(result.data["venues"])

    @routes.get("/api/venues/<venue_id>")
    @dependencies.require_auth
    def read_venue(venue_id: str):
        result = dependencies.get_venue_service().read(venue_id)
        if result.code == "VENUE_NOT_FOUND":
            return jsonify({"error": result.code}), 404
        return jsonify(result.data["venue"])

    @routes.post("/api/venues")
    @dependencies.require_auth
    def create_venue():
        result = dependencies.get_venue_service().create(
            request.get_json(silent=True) or {}
        )
        if result.code == "VENUE_NAME_REQUIRED":
            return jsonify({"error": result.code}), 400
        if result.code == "DUPLICATE_VENUE":
            return jsonify(
                {
                    "error": result.code,
                    "duplicate_venue": result.data["duplicate_venue"],
                }
            ), 409
        return jsonify(result.data["venue"]), 201

    @routes.put("/api/venues/<venue_id>")
    @dependencies.require_auth
    def update_venue(venue_id: str):
        result = dependencies.get_venue_service().update(
            venue_id,
            request.get_json(silent=True) or {},
        )
        if result.code == "VENUE_NOT_FOUND":
            return jsonify({"error": result.code}), 404
        if result.code == "VENUE_NAME_REQUIRED":
            return jsonify({"error": result.code}), 400
        if result.code == "DUPLICATE_VENUE":
            return jsonify(
                {
                    "error": result.code,
                    "duplicate_venue": result.data["duplicate_venue"],
                }
            ), 409
        return jsonify(result.data["venue"])

    @routes.delete("/api/venues/<venue_id>")
    @dependencies.require_auth
    def delete_venue(venue_id: str):
        result = dependencies.get_venue_service().delete(venue_id)
        if result.code == "VENUE_NOT_FOUND":
            return jsonify({"error": result.code}), 404
        if result.code == "VENUE_IN_USE":
            return jsonify({"error": result.code, **result.data}), 409
        return jsonify(result.data)

    return routes
