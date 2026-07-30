from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from typing import Any, Callable

from flask import Blueprint, jsonify, render_template, request, send_file


RouteDecorator = Callable[[Callable[..., Any]], Callable[..., Any]]


@dataclass(frozen=True)
class RecapRoutesDependencies:
    require_auth: RouteDecorator
    get_recap_service: Callable[[], Any]


def _response(result: Any):
    error_status = {
        "RECAP_NOT_FOUND": 404,
        "BROADCAST_NOT_READY": 409,
        "FINAL_SCORE_UNAVAILABLE": 409,
        "RECAP_ALREADY_EXISTS": 409,
        "RECAP_UPDATE_INVALID": 400,
        "RECAP_APPROVAL_CONFIRMATION_REQUIRED": 409,
        "RECAP_DELETE_CONFIRMATION_REQUIRED": 409,
        "RECAP_NOT_APPROVABLE": 409,
        "RECAP_NOT_APPROVED": 409,
        "RECAP_IMMUTABLE": 409,
        "RECAP_STALE": 409,
        "SOCIAL_HANDOFF_UNAVAILABLE": 409,
        "SOCIAL_DRAFT_FAILED": 409,
    }
    if getattr(result, "ok", False):
        return jsonify(result.data)
    return jsonify({"error": result.code, **getattr(result, "data", {})}), error_status.get(result.code, 409)


def create_recap_blueprint(dependencies: RecapRoutesDependencies) -> Blueprint:
    routes = Blueprint("recap_routes", __name__)

    @routes.get("/recaps")
    @dependencies.require_auth
    def recap_manager():
        return render_template("recap_manager.html")

    @routes.get("/api/recaps/status")
    @dependencies.require_auth
    def recap_status():
        return _response(dependencies.get_recap_service().status())

    @routes.post("/api/recaps/generate")
    @dependencies.require_auth
    def generate_recap():
        incoming = request.get_json(force=True, silent=True) or {}
        return _response(
            dependencies.get_recap_service().generate(
                regenerate=bool(incoming.get("regenerate", False)),
                article_style=str(incoming.get("article_style") or "local_sports"),
            )
        )

    @routes.get("/api/recaps/<recap_id>")
    @dependencies.require_auth
    def read_recap(recap_id: str):
        return _response(dependencies.get_recap_service().read(recap_id))

    @routes.patch("/api/recaps/<recap_id>")
    @dependencies.require_auth
    def update_recap(recap_id: str):
        return _response(
            dependencies.get_recap_service().update(
                recap_id,
                request.get_json(force=True, silent=True) or {},
            )
        )

    @routes.post("/api/recaps/<recap_id>/approve")
    @dependencies.require_auth
    def approve_recap(recap_id: str):
        incoming = request.get_json(force=True, silent=True) or {}
        return _response(
            dependencies.get_recap_service().approve(
                recap_id,
                operator=incoming.get("operator", "operator"),
                confirmation=incoming.get("confirmation"),
            )
        )

    @routes.get("/api/recaps/<recap_id>/grounding")
    @dependencies.require_auth
    def recap_grounding(recap_id: str):
        return _response(dependencies.get_recap_service().grounding_report(recap_id))

    @routes.post("/api/recaps/<recap_id>/social-draft")
    @dependencies.require_auth
    def recap_social_draft(recap_id: str):
        return _response(
            dependencies.get_recap_service().create_social_final_draft(recap_id)
        )

    @routes.get("/api/recaps/<recap_id>/export.txt")
    @dependencies.require_auth
    def export_recap(recap_id: str):
        result = dependencies.get_recap_service().export_text(recap_id)
        if not result.ok:
            return _response(result)
        payload = BytesIO(str(result.data["text"]).encode("utf-8"))
        return send_file(
            payload,
            mimetype="text/plain; charset=utf-8",
            as_attachment=True,
            download_name=str(result.data["filename"]),
        )

    @routes.delete("/api/recaps/<recap_id>")
    @dependencies.require_auth
    def delete_recap(recap_id: str):
        incoming = request.get_json(force=True, silent=True) or {}
        return _response(
            dependencies.get_recap_service().delete(
                recap_id,
                incoming.get("confirmation"),
            )
        )

    return routes
