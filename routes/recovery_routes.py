from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from flask import Blueprint, jsonify, request


RouteDecorator = Callable[[Callable[..., Any]], Callable[..., Any]]


@dataclass(frozen=True)
class RecoveryRoutesDependencies:
    """Injected application boundaries used by recovery routes."""

    require_auth: RouteDecorator
    get_recovery_service: Callable[[], Any]


def create_recovery_blueprint(
    dependencies: RecoveryRoutesDependencies,
) -> Blueprint:
    routes = Blueprint("recovery_routes", __name__)

    @routes.get("/api/game-day/recovery/status")
    @dependencies.require_auth
    def recovery_status():
        result = dependencies.get_recovery_service().status()
        return jsonify({"code": result.code, **result.data})

    @routes.post("/api/game-day/recovery/snapshots/<snapshot_id>/rehearse")
    @dependencies.require_auth
    def rehearse_restore(snapshot_id: str):
        result = dependencies.get_recovery_service().rehearse_restore(snapshot_id)
        status = {
            "INVALID_SNAPSHOT_ID": 400,
            "SNAPSHOT_NOT_FOUND": 404,
            "SNAPSHOT_INVALID": 409,
            "SNAPSHOT_CORRUPT": 409,
            "RESTORE_PAYLOAD_INVALID": 409,
        }.get(result.code, 200)
        return jsonify({"code": result.code, **result.data}), status

    @routes.post("/api/game-day/recovery/snapshots/<snapshot_id>/restore")
    @dependencies.require_auth
    def restore_snapshot(snapshot_id: str):
        incoming = request.get_json(silent=True) or {}
        result = dependencies.get_recovery_service().restore_snapshot(
            snapshot_id,
            confirmation=str(incoming.get("confirm_snapshot_id", "")),
            note=str(incoming.get("note", "")),
        )
        status = {
            "RESTORE_CONFIRMATION_REQUIRED": 400,
            "INVALID_SNAPSHOT_ID": 400,
            "SNAPSHOT_NOT_FOUND": 404,
            "LIVE_BROADCAST_ACTIVE": 409,
            "SNAPSHOT_INVALID": 409,
            "SNAPSHOT_CORRUPT": 409,
            "RESTORE_PAYLOAD_INVALID": 409,
            "PRE_RESTORE_SNAPSHOT_FAILED": 500,
            "RESTORE_FAILED": 500,
        }.get(result.code, 200)
        return jsonify({"code": result.code, **result.data}), status

    @routes.delete("/api/game-day/recovery/unclean-shutdown")
    @dependencies.require_auth
    def clear_unclean_shutdown():
        result = dependencies.get_recovery_service().clear_unclean_shutdown()
        return jsonify({"code": result.code, **result.data})

    @routes.post("/api/game-day/recovery/known-good")
    @dependencies.require_auth
    def register_known_good():
        incoming = request.get_json(silent=True) or {}
        result = dependencies.get_recovery_service().register_known_good(
            commit=str(incoming.get("commit", "")),
            note=str(incoming.get("note", "")),
        )
        status = 400 if result.code == "INVALID_RELEASE_COMMIT" else 201
        return jsonify({"code": result.code, **result.data}), status

    @routes.get("/api/game-day/recovery/rollback-plan")
    @dependencies.require_auth
    def rollback_plan():
        result = dependencies.get_recovery_service().rollback_plan()
        status = {
            "KNOWN_GOOD_NOT_SET": 404,
            "KNOWN_GOOD_INVALID": 409,
        }.get(result.code, 200)
        return jsonify({"code": result.code, **result.data}), status

    return routes
