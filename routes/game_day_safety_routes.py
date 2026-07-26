from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from flask import Blueprint, jsonify, request


RouteDecorator = Callable[[Callable[..., Any]], Callable[..., Any]]


@dataclass(frozen=True)
class GameDaySafetyRoutesDependencies:
    """Injected application boundaries used by game-day safety routes."""

    require_auth: RouteDecorator
    get_safety_service: Callable[[], Any]


def create_game_day_safety_blueprint(
    dependencies: GameDaySafetyRoutesDependencies,
) -> Blueprint:
    routes = Blueprint("game_day_safety_routes", __name__)

    @routes.get("/api/game-day/preflight")
    @dependencies.require_auth
    def game_day_preflight():
        result = dependencies.get_safety_service().preflight()
        status = 200 if result.code == "OK" else 409
        return jsonify({"code": result.code, **result.data}), status

    @routes.get("/api/game-day/snapshots")
    @dependencies.require_auth
    def list_game_day_snapshots():
        result = dependencies.get_safety_service().list_snapshots()
        return jsonify(result.data)

    @routes.post("/api/game-day/snapshots")
    @dependencies.require_auth
    def create_game_day_snapshot():
        incoming = request.get_json(silent=True) or {}
        result = dependencies.get_safety_service().create_snapshot(
            kind=str(incoming.get("kind", "manual")),
            note=str(incoming.get("note", "")),
        )
        if result.code == "PREFLIGHT_FAILED":
            return jsonify({"code": result.code, **result.data}), 409
        if result.code == "SNAPSHOT_FAILED":
            return jsonify({"code": result.code, **result.data}), 500
        return jsonify({"code": result.code, **result.data}), 201

    @routes.post("/api/game-day/snapshots/<snapshot_id>/verify")
    @dependencies.require_auth
    def verify_game_day_snapshot(snapshot_id: str):
        result = dependencies.get_safety_service().verify_snapshot(snapshot_id)
        status = {
            "INVALID_SNAPSHOT_ID": 400,
            "SNAPSHOT_NOT_FOUND": 404,
            "SNAPSHOT_INVALID": 409,
            "SNAPSHOT_CORRUPT": 409,
        }.get(result.code, 200)
        return jsonify({"code": result.code, **result.data}), status

    return routes
