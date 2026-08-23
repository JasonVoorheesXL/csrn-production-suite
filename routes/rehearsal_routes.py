from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from flask import Blueprint, jsonify, request


RouteDecorator = Callable[[Callable[..., Any]], Callable[..., Any]]


@dataclass(frozen=True)
class RehearsalRoutesDependencies:
    require_auth: RouteDecorator
    get_rehearsal_service: Callable[[], Any]


def create_rehearsal_blueprint(dependencies: RehearsalRoutesDependencies) -> Blueprint:
    routes = Blueprint("rehearsal_routes", __name__)

    def service():
        return dependencies.get_rehearsal_service()

    @routes.get("/api/game-day/rehearsals")
    @dependencies.require_auth
    def rehearsal_status():
        result = service().status()
        return jsonify(result.data)

    @routes.get("/api/game-day/rehearsals/catalog")
    @dependencies.require_auth
    def rehearsal_catalog():
        result = service().catalog()
        return jsonify(result.data)

    @routes.post("/api/game-day/rehearsals")
    @dependencies.require_auth
    def create_rehearsal():
        result = service().create_rehearsal(request.get_json(force=True, silent=True))
        if result.code in {"REHEARSAL_REQUIRED", "NAME_REQUIRED", "OPERATOR_REQUIRED"}:
            return jsonify({"error": result.code, **result.data}), 400
        if result.code == "RELEASE_FROZEN":
            return jsonify({"error": result.code}), 409
        return jsonify(result.data), 201

    @routes.patch("/api/game-day/rehearsals/<rehearsal_id>/drills/<path:drill_key>")
    @dependencies.require_auth
    def update_rehearsal_drill(rehearsal_id: str, drill_key: str):
        result = service().update_drill(
            rehearsal_id,
            drill_key,
            request.get_json(force=True, silent=True),
        )
        if result.code in {
            "DRILL_UPDATE_REQUIRED",
            "DRILL_RESULT_INVALID",
            "DRILL_NOTE_REQUIRED",
        }:
            return jsonify({"error": result.code, **result.data}), 400
        if result.code in {
            "RELEASE_FROZEN",
            "REHEARSAL_COMPLETED_LOCKED",
        }:
            return jsonify({"error": result.code, **result.data}), 409
        if result.code in {"REHEARSAL_NOT_FOUND", "DRILL_NOT_FOUND"}:
            return jsonify({"error": result.code}), 404
        return jsonify(result.data)

    @routes.post("/api/game-day/rehearsals/<rehearsal_id>/blockers")
    @dependencies.require_auth
    def add_rehearsal_blocker(rehearsal_id: str):
        result = service().add_blocker(
            rehearsal_id,
            request.get_json(force=True, silent=True),
        )
        if result.code in {
            "BLOCKER_REQUIRED",
            "BLOCKER_DESCRIPTION_REQUIRED",
            "BLOCKER_SEVERITY_INVALID",
        }:
            return jsonify({"error": result.code}), 400
        if result.code == "RELEASE_FROZEN":
            return jsonify({"error": result.code}), 409
        if result.code == "REHEARSAL_NOT_FOUND":
            return jsonify({"error": result.code}), 404
        return jsonify(result.data), 201

    @routes.patch("/api/game-day/rehearsals/<rehearsal_id>/blockers/<blocker_id>")
    @dependencies.require_auth
    def update_rehearsal_blocker(rehearsal_id: str, blocker_id: str):
        result = service().update_blocker(
            rehearsal_id,
            blocker_id,
            request.get_json(force=True, silent=True),
        )
        if result.code in {
            "BLOCKER_UPDATE_REQUIRED",
            "BLOCKER_STATUS_INVALID",
            "BLOCKER_RESOLUTION_REQUIRED",
        }:
            return jsonify({"error": result.code}), 400
        if result.code == "RELEASE_FROZEN":
            return jsonify({"error": result.code}), 409
        if result.code in {"REHEARSAL_NOT_FOUND", "BLOCKER_NOT_FOUND"}:
            return jsonify({"error": result.code}), 404
        return jsonify(result.data)

    @routes.post("/api/game-day/rehearsals/<rehearsal_id>/complete")
    @dependencies.require_auth
    def complete_rehearsal(rehearsal_id: str):
        result = service().complete_rehearsal(
            rehearsal_id,
            request.get_json(force=True, silent=True),
        )
        if result.code in {"COMPLETION_REQUIRED", "CONFIRMATION_REQUIRED", "SIGNOFF_REQUIRED"}:
            return jsonify({"error": result.code, **result.data}), 400
        if result.code in {"REHEARSAL_INCOMPLETE", "RELEASE_FROZEN"}:
            return jsonify({"error": result.code, **result.data}), 409
        if result.code == "REHEARSAL_NOT_FOUND":
            return jsonify({"error": result.code}), 404
        return jsonify(result.data)

    @routes.post("/api/game-day/rehearsals/<rehearsal_id>/reopen")
    @dependencies.require_auth
    def reopen_rehearsal(rehearsal_id: str):
        result = service().reopen_rehearsal(
            rehearsal_id,
            request.get_json(force=True, silent=True),
        )
        if result.code == "CONFIRMATION_REQUIRED":
            return jsonify({"error": result.code}), 400
        if result.code == "RELEASE_FROZEN":
            return jsonify({"error": result.code}), 409
        if result.code == "REHEARSAL_NOT_FOUND":
            return jsonify({"error": result.code}), 404
        return jsonify(result.data)

    @routes.get("/api/game-day/release-readiness")
    @dependencies.require_auth
    def release_readiness():
        result = service().readiness()
        status = 200 if result.code == "OK" else 409
        return jsonify(result.data), status

    @routes.post("/api/game-day/release-freeze")
    @dependencies.require_auth
    def freeze_release():
        result = service().freeze_release(request.get_json(force=True, silent=True))
        if result.code in {
            "FREEZE_REQUIRED",
            "CONFIRMATION_REQUIRED",
            "OPERATOR_REQUIRED",
            "INVALID_RELEASE_COMMIT",
        }:
            return jsonify({"error": result.code, **result.data}), 400
        if result.code in {
            "RELEASE_NOT_READY",
            "RELEASE_ALREADY_FROZEN",
            "SNAPSHOT_FAILED",
            "KNOWN_GOOD_FAILED",
        }:
            return jsonify({"error": result.code, **result.data}), 409
        return jsonify(result.data)

    @routes.post("/api/game-day/release-unfreeze")
    @dependencies.require_auth
    def unfreeze_release():
        result = service().unfreeze_release(request.get_json(force=True, silent=True))
        if result.code in {"CONFIRMATION_REQUIRED", "UNFREEZE_REASON_REQUIRED"}:
            return jsonify({"error": result.code}), 400
        if result.code == "RELEASE_NOT_FROZEN":
            return jsonify({"error": result.code}), 409
        return jsonify(result.data)

    @routes.get("/api/game-day/release-manifest")
    @dependencies.require_auth
    def release_manifest():
        result = service().manifest()
        if result.code == "MANIFEST_NOT_FOUND":
            return jsonify({"error": result.code}), 404
        return jsonify(result.data)

    return routes
