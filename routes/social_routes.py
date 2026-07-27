from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from flask import Blueprint, jsonify, render_template, request, send_file


RouteDecorator = Callable[[Callable[..., Any]], Callable[..., Any]]


@dataclass(frozen=True)
class SocialRoutesDependencies:
    require_auth: RouteDecorator
    get_social_service: Callable[[], Any]


def _response(result: Any):
    error_status = {
        "ACCOUNT_NOT_FOUND": 404,
        "DRAFT_NOT_FOUND": 404,
        "EVENT_NOT_FOUND": 404,
        "CARD_NOT_FOUND": 404,
        "PUBLICATION_NOT_FOUND": 404,
        "PLATFORM_UNSUPPORTED": 400,
        "ACCOUNT_ID_INVALID": 400,
        "CREDENTIAL_REFERENCE_INVALID": 400,
        "PAGE_ID_REQUIRED": 400,
        "TEXT_LIMIT_INVALID": 400,
        "RAW_CREDENTIAL_REJECTED": 400,
        "SETTINGS_INVALID": 400,
        "HASHTAGS_INVALID": 400,
        "SPONSOR_RULES_INVALID": 400,
        "SPONSOR_RULE_KIND_INVALID": 400,
        "DRAFT_KIND_INVALID": 400,
        "GROUNDED_MESSAGE_REQUIRED": 400,
        "DRAFT_UPDATE_INVALID": 400,
        "EVENT_KIND_MISMATCH": 409,
        "DUPLICATE_DRAFT": 409,
        "ACCOUNT_LIMIT_REACHED": 409,
        "SPONSOR_NOT_ACTIVE": 409,
        "ACCOUNT_REMOVE_CONFIRMATION_REQUIRED": 409,
        "APPROVAL_CONFIRMATION_REQUIRED": 409,
        "DRAFT_NOT_APPROVABLE": 409,
        "DRAFT_NOT_APPROVED": 409,
        "DRAFT_IMMUTABLE": 409,
        "CARD_RENDER_REQUIRED": 409,
        "NO_ENABLED_ACCOUNTS": 409,
        "CORRECTION_REQUIRES_PUBLICATION": 409,
        "RETRACT_CONFIRMATION_REQUIRED": 409,
        "RETRACT_FAILED": 409,
        "DRAFT_DELETE_CONFIRMATION_REQUIRED": 409,
        "ACTIVE_PUBLICATION_EXISTS": 409,
        "AUTO_PUBLISH_DISABLED": 409,
        "PUBLISH_FAILED": 502,
    }
    if getattr(result, "ok", False):
        return jsonify(result.data)
    return jsonify({"error": result.code, **getattr(result, "data", {})}), error_status.get(result.code, 409)


def create_social_blueprint(dependencies: SocialRoutesDependencies) -> Blueprint:
    routes = Blueprint("social_routes", __name__)

    @routes.get("/social")
    @dependencies.require_auth
    def social_manager():
        return render_template("social_manager.html")

    @routes.get("/api/social/status")
    @dependencies.require_auth
    def social_status():
        return _response(dependencies.get_social_service().status())

    @routes.post("/api/social/accounts")
    @dependencies.require_auth
    def configure_social_account():
        return _response(dependencies.get_social_service().configure_account(request.get_json(force=True, silent=True) or {}))

    @routes.delete("/api/social/accounts/<account_id>")
    @dependencies.require_auth
    def remove_social_account(account_id: str):
        incoming = request.get_json(force=True, silent=True) or {}
        return _response(dependencies.get_social_service().remove_account(account_id, incoming.get("confirmation")))

    @routes.post("/api/social/settings")
    @dependencies.require_auth
    def update_social_settings():
        return _response(dependencies.get_social_service().update_settings(request.get_json(force=True, silent=True) or {}))

    @routes.post("/api/social/sponsor-rules")
    @dependencies.require_auth
    def update_social_sponsor_rules():
        return _response(dependencies.get_social_service().update_sponsor_rules(request.get_json(force=True, silent=True) or {}))

    @routes.get("/api/social/eligible-events")
    @dependencies.require_auth
    def eligible_social_events():
        return _response(dependencies.get_social_service().eligible_events())

    @routes.post("/api/social/drafts")
    @dependencies.require_auth
    def create_social_draft():
        incoming = request.get_json(force=True, silent=True) or {}
        return _response(
            dependencies.get_social_service().create_draft(
                incoming.get("kind"),
                event_id=incoming.get("event_id", ""),
                payload=incoming.get("payload") if isinstance(incoming.get("payload"), dict) else incoming,
                force_duplicate=bool(incoming.get("force_duplicate", False)),
            )
        )

    @routes.get("/api/social/drafts/<draft_id>")
    @dependencies.require_auth
    def read_social_draft(draft_id: str):
        return _response(dependencies.get_social_service().read_draft(draft_id))

    @routes.patch("/api/social/drafts/<draft_id>")
    @dependencies.require_auth
    def update_social_draft(draft_id: str):
        return _response(dependencies.get_social_service().update_draft(draft_id, request.get_json(force=True, silent=True) or {}))

    @routes.delete("/api/social/drafts/<draft_id>")
    @dependencies.require_auth
    def delete_social_draft(draft_id: str):
        incoming = request.get_json(force=True, silent=True) or {}
        return _response(dependencies.get_social_service().delete_draft(draft_id, incoming.get("confirmation")))

    @routes.post("/api/social/drafts/<draft_id>/approve")
    @dependencies.require_auth
    def approve_social_draft(draft_id: str):
        incoming = request.get_json(force=True, silent=True) or {}
        return _response(
            dependencies.get_social_service().approve_draft(
                draft_id,
                operator=incoming.get("operator", "operator"),
                confirmation=incoming.get("confirmation"),
            )
        )

    @routes.post("/api/social/drafts/<draft_id>/publish")
    @dependencies.require_auth
    def publish_social_draft(draft_id: str):
        incoming = request.get_json(force=True, silent=True) or {}
        account_ids = incoming.get("account_ids")
        return _response(
            dependencies.get_social_service().publish_draft(
                draft_id,
                account_ids=account_ids if isinstance(account_ids, list) else None,
            )
        )

    @routes.post("/api/social/auto-queue/process")
    @dependencies.require_auth
    def process_social_auto_queue():
        incoming = request.get_json(force=True, silent=True) or {}
        return _response(dependencies.get_social_service().process_auto_queue(limit=incoming.get("limit", 10)))

    @routes.post("/api/social/drafts/<draft_id>/corrections")
    @dependencies.require_auth
    def create_social_correction(draft_id: str):
        return _response(dependencies.get_social_service().create_correction(draft_id, request.get_json(force=True, silent=True) or {}))

    @routes.post("/api/social/drafts/<draft_id>/publications/<account_id>/retract")
    @dependencies.require_auth
    def retract_social_publication(draft_id: str, account_id: str):
        incoming = request.get_json(force=True, silent=True) or {}
        return _response(dependencies.get_social_service().retract_publication(draft_id, account_id, incoming.get("confirmation")))

    @routes.get("/api/social/drafts/<draft_id>/cards/<platform>")
    @dependencies.require_auth
    def social_card(draft_id: str, platform: str):
        result = dependencies.get_social_service().card_path(draft_id, platform)
        if not result.ok:
            return _response(result)
        path = Path(result.data["path"])
        return send_file(path, mimetype="image/png", download_name=result.data.get("filename", path.name), conditional=True)

    @routes.get("/api/social/postgame-handoff")
    @dependencies.require_auth
    def social_postgame_handoff():
        return _response(dependencies.get_social_service().postgame_handoff())

    return routes
