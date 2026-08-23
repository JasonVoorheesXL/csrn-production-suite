from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from flask import Blueprint, jsonify, request


RouteDecorator = Callable[[Callable[..., Any]], Callable[..., Any]]


@dataclass(frozen=True)
class RosterRoutesDependencies:
    require_auth: RouteDecorator
    get_roster_service: Callable[[], Any]


def create_roster_blueprint(
    dependencies: RosterRoutesDependencies,
) -> Blueprint:
    routes = Blueprint("roster_routes", __name__)

    @routes.get("/api/rosters")
    @dependencies.require_auth
    def list_rosters():
        return jsonify(dependencies.get_roster_service().list_rosters())

    @routes.post("/api/rosters")
    @dependencies.require_auth
    def create_roster():
        result = dependencies.get_roster_service().create(
            request.get_json(force=True) or {}
        )
        if result.code == "SCHOOL_AND_SEASON_REQUIRED":
            return jsonify({"error": result.code}), 400
        if result.code == "ROSTER_ALREADY_EXISTS":
            return jsonify(
                {
                    "error": result.code,
                    "roster": result.data["roster"],
                }
            ), 409
        return jsonify(result.data["roster"]), 201

    @routes.put("/api/rosters/<roster_id>")
    @dependencies.require_auth
    def update_roster(roster_id: str):
        result = dependencies.get_roster_service().update(
            roster_id,
            request.get_json(force=True) or {},
        )
        if result.code == "ROSTER_NOT_FOUND":
            return jsonify({"error": result.code}), 404
        return jsonify(result.data["roster"])

    @routes.delete("/api/rosters/<roster_id>")
    @dependencies.require_auth
    def delete_roster(roster_id: str):
        result = dependencies.get_roster_service().delete(roster_id)
        if result.code == "ROSTER_NOT_FOUND":
            return jsonify({"error": result.code}), 404
        return jsonify({"ok": True})

    @routes.post("/api/rosters/<roster_id>/players")
    @dependencies.require_auth
    def create_roster_player(roster_id: str):
        result = dependencies.get_roster_service().create_player(
            roster_id,
            request.get_json(force=True) or {},
        )
        if result.code == "ROSTER_NOT_FOUND":
            return jsonify({"error": result.code}), 404
        if result.code == "PLAYER_NAME_REQUIRED":
            return jsonify({"error": result.code}), 400
        return jsonify(result.data), 201

    @routes.put("/api/rosters/<roster_id>/players/<player_id>")
    @dependencies.require_auth
    def update_roster_player(roster_id: str, player_id: str):
        result = dependencies.get_roster_service().update_player(
            roster_id,
            player_id,
            request.get_json(force=True) or {},
        )
        if result.code in {"ROSTER_NOT_FOUND", "PLAYER_NOT_FOUND"}:
            return jsonify({"error": result.code}), 404
        return jsonify(result.data)

    @routes.delete("/api/rosters/<roster_id>/players/<player_id>")
    @dependencies.require_auth
    def delete_roster_player(roster_id: str, player_id: str):
        result = dependencies.get_roster_service().delete_player(
            roster_id,
            player_id,
        )
        if result.code in {"ROSTER_NOT_FOUND", "PLAYER_NOT_FOUND"}:
            return jsonify({"error": result.code}), 404
        return jsonify({"ok": True})

    @routes.post("/api/rosters/<roster_id>/players/import")
    @dependencies.require_auth
    def import_roster_players(roster_id: str):
        incoming = request.get_json(force=True) or {}
        result = dependencies.get_roster_service().import_players(
            roster_id,
            incoming.get("players", []),
        )
        if result.code == "INVALID_PLAYER_LIST":
            return jsonify({"error": result.code}), 400
        if result.code == "ROSTER_NOT_FOUND":
            return jsonify({"error": result.code}), 404
        return jsonify(result.data)

    @routes.post("/api/rosters/pronunciation")
    @dependencies.require_auth
    def generate_roster_pronunciation():
        incoming = request.get_json(force=True) or {}
        first_name = str(incoming.get("first_name", "")).strip()
        last_name = str(incoming.get("last_name", "")).strip()
        pronunciation = dependencies.get_roster_service().pronunciation_for_player_name(
            first_name,
            last_name,
        )
        return jsonify({
            "first_name": first_name,
            "last_name": last_name,
            "pronunciation": pronunciation,
        })

    return routes
