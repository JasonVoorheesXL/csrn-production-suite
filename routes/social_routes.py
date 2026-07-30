from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import secrets
from urllib.parse import urlencode
from typing import Any, Callable

from flask import Blueprint, jsonify, redirect, render_template, request, send_file


RouteDecorator = Callable[[Callable[..., Any]], Callable[..., Any]]


@dataclass(frozen=True)
class SocialRoutesDependencies:
    require_auth: RouteDecorator
    get_social_service: Callable[[], Any]
    get_facebook_connection_service: Callable[[], Any]


def _response(result: Any):
    error_status = {
        "ACCOUNT_NOT_FOUND": 404,
        "DRAFT_NOT_FOUND": 404,
        "EVENT_NOT_FOUND": 404,
        "CARD_NOT_FOUND": 404,
        "PUBLICATION_NOT_FOUND": 404,
        "PLATFORM_UNSUPPORTED": 400,
        "X_MANUAL_ONLY": 400,
        "MANUAL_PLATFORM_UNSUPPORTED": 400,
        "ACCOUNT_ID_INVALID": 400,
        "CREDENTIAL_REFERENCE_INVALID": 400,
        "PAGE_ID_REQUIRED": 400,
        "TEXT_LIMIT_INVALID": 400,
        "RAW_CREDENTIAL_REJECTED": 400,
        "SETTINGS_INVALID": 400,
        "HASHTAGS_INVALID": 400,
        "PLAYER_NAME_POLICY_INVALID": 400,
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
        "X_MANUAL_DISABLED": 409,
        "PUBLISH_FAILED": 502,
        "FACEBOOK_APP_ID_INVALID": 400,
        "FACEBOOK_APP_SECRET_INVALID": 400,
        "FACEBOOK_API_VERSION_INVALID": 400,
        "FACEBOOK_REDIRECT_URI_INVALID": 400,
        "FACEBOOK_APP_NOT_CONFIGURED": 409,
        "FACEBOOK_AUTHORIZATION_CODE_MISSING": 400,
        "FACEBOOK_OAUTH_STATE_INVALID": 400,
        "FACEBOOK_CODE_EXCHANGE_FAILED": 502,
        "FACEBOOK_PAGE_LIST_FAILED": 502,
        "FACEBOOK_NO_MANAGED_PAGES": 409,
        "FACEBOOK_PAGE_SELECTION_EXPIRED": 410,
        "FACEBOOK_PAGE_SELECTION_INVALID": 400,
        "FACEBOOK_SECURE_STORAGE_FAILED": 500,
        "FACEBOOK_SOCIAL_ACCOUNT_SAVE_FAILED": 500,
        "FACEBOOK_SOCIAL_ACCOUNT_REMOVE_FAILED": 500,
        "FACEBOOK_PAGE_NOT_CONNECTED": 409,
        "FACEBOOK_CONNECTION_TEST_FAILED": 502,
        "FACEBOOK_DISCONNECT_CONFIRMATION_REQUIRED": 409,
        "FACEBOOK_APP_REMOVE_CONFIRMATION_REQUIRED": 409,
        "FACEBOOK_LOCALHOST_REQUIRED": 403,
    }
    if getattr(result, "ok", False):
        return jsonify(result.data)
    return jsonify({"error": result.code, **getattr(result, "data", {})}), error_status.get(result.code, 409)


def create_social_blueprint(dependencies: SocialRoutesDependencies) -> Blueprint:
    routes = Blueprint("social_routes", __name__)

    def localhost_required():
        remote = str(request.remote_addr or "").strip().lower()
        if remote not in {"127.0.0.1", "::1"}:
            result = type("Result", (), {
                "ok": False,
                "code": "FACEBOOK_LOCALHOST_REQUIRED",
                "data": {"message": "Facebook connection setup must be completed from the CSRN laptop at http://127.0.0.1:5050."},
            })()
            return _response(result)
        return None

    @routes.get("/social")
    @dependencies.require_auth
    def social_manager():
        return render_template("social_manager.html")

    @routes.get("/api/social/status")
    @dependencies.require_auth
    def social_status():
        return _response(dependencies.get_social_service().status())

    @routes.get("/api/social/facebook/status")
    @dependencies.require_auth
    def facebook_connection_status():
        return _response(dependencies.get_facebook_connection_service().status())

    @routes.post("/api/social/facebook/app")
    @dependencies.require_auth
    def configure_facebook_app():
        guard = localhost_required()
        if guard is not None:
            return guard
        return _response(
            dependencies.get_facebook_connection_service().configure_app(
                request.get_json(force=True, silent=True) or {}
            )
        )

    @routes.delete("/api/social/facebook/app")
    @dependencies.require_auth
    def remove_facebook_app():
        guard = localhost_required()
        if guard is not None:
            return guard
        incoming = request.get_json(force=True, silent=True) or {}
        return _response(
            dependencies.get_facebook_connection_service().remove_app_configuration(
                incoming.get("confirmation")
            )
        )

    @routes.get("/api/social/facebook/start")
    @dependencies.require_auth
    def start_facebook_connection():
        guard = localhost_required()
        if guard is not None:
            return guard
        oauth_state = secrets.token_urlsafe(32)
        result = dependencies.get_facebook_connection_service().authorization_url(oauth_state)
        if not result.ok:
            return _response(result)
        return redirect(result.data["authorization_url"])

    @routes.get("/api/social/facebook/callback")
    def complete_facebook_connection():
        if request.args.get("error"):
            return redirect("http://127.0.0.1:5050/social?facebook=error&code=FACEBOOK_AUTHORIZATION_DENIED")
        received_state = str(request.args.get("state") or "").strip()
        result = dependencies.get_facebook_connection_service().complete_authorization(
            code=request.args.get("code"),
            received_state=received_state,
        )
        if not result.ok:
            return redirect(
                "http://127.0.0.1:5050/social?" + urlencode(
                    {"facebook": "error", "code": result.code}
                )
            )
        return redirect(
            "http://127.0.0.1:5050/social?" + urlencode(
                {
                    "facebook": "select",
                    "selection_id": result.data["selection_id"],
                    "warning": result.data.get("warning", ""),
                }
            )
        )

    @routes.get("/api/social/facebook/pages")
    @dependencies.require_auth
    def facebook_connection_pages():
        guard = localhost_required()
        if guard is not None:
            return guard
        selection_id = request.args.get("selection_id", "")
        return _response(
            dependencies.get_facebook_connection_service().pending_pages(selection_id)
        )

    @routes.post("/api/social/facebook/select")
    @dependencies.require_auth
    def select_facebook_page():
        guard = localhost_required()
        if guard is not None:
            return guard
        incoming = request.get_json(force=True, silent=True) or {}
        result = dependencies.get_facebook_connection_service().connect_page(
            incoming.get("selection_id"), incoming.get("page_id")
        )
        return _response(result)

    @routes.post("/api/social/facebook/test")
    @dependencies.require_auth
    def test_facebook_connection():
        guard = localhost_required()
        if guard is not None:
            return guard
        return _response(dependencies.get_facebook_connection_service().test_connection())

    @routes.post("/api/social/facebook/disconnect")
    @dependencies.require_auth
    def disconnect_facebook_page():
        guard = localhost_required()
        if guard is not None:
            return guard
        incoming = request.get_json(force=True, silent=True) or {}
        return _response(
            dependencies.get_facebook_connection_service().disconnect(
                incoming.get("confirmation")
            )
        )

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
        return _response(dependencies.get_social_service().discard_draft(draft_id, incoming.get("confirmation")))

    @routes.post("/api/social/drafts/<draft_id>/archive")
    @dependencies.require_auth
    def archive_social_draft(draft_id: str):
        incoming = request.get_json(force=True, silent=True) or {}
        return _response(dependencies.get_social_service().archive_draft(draft_id, incoming.get("confirmation")))

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

    @routes.get("/api/social/drafts/<draft_id>/manual/x")
    @dependencies.require_auth
    def prepare_manual_x_package(draft_id: str):
        return _response(dependencies.get_social_service().manual_package(draft_id, "x"))

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
        return send_file(
            path,
            mimetype="image/png",
            download_name=result.data.get("filename", path.name),
            conditional=True,
            as_attachment=str(request.args.get("download", "")).lower() in {"1", "true", "yes"},
        )

    @routes.get("/api/social/postgame-handoff")
    @dependencies.require_auth
    def social_postgame_handoff():
        return _response(dependencies.get_social_service().postgame_handoff())

    return routes
