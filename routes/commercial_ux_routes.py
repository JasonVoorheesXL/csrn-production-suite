from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable
from urllib.parse import urlencode

from flask import Blueprint, jsonify, redirect, render_template, request, url_for


RouteDecorator = Callable[[Callable[..., Any]], Callable[..., Any]]


@dataclass(frozen=True)
class CommercialUxDependencies:
    require_auth: RouteDecorator
    get_ux_service: Callable[[], Any]
    get_oauth_service: Callable[[], Any]
    get_theme_service: Callable[[], Any]


def _response(result: Any):
    if getattr(result, "ok", False):
        return jsonify(result.data)
    statuses = {
        "PROVIDER_UNSUPPORTED": 404,
        "CONNECTION_NOT_FOUND": 404,
        "CALLBACK_URL_INVALID": 400,
        "AUTHORIZATION_CODE_REQUIRED": 400,
        "PROTECTED_STORAGE_UNAVAILABLE": 409,
        "PROVIDER_APPLICATION_NOT_CONFIGURED": 409,
        "OAUTH_STATE_INVALID": 409,
        "OAUTH_STATE_EXPIRED": 409,
        "TOKEN_EXCHANGE_FAILED": 502,
        "ACCESS_TOKEN_MISSING": 502,
        "FACEBOOK_PAGE_SELECTION_REQUIRED": 409,
        "CREDENTIAL_STORAGE_FAILED": 500,
        "SOCIAL_ACCOUNT_CONFIGURATION_FAILED": 409,
        "CREDENTIAL_UNAVAILABLE": 409,
        "CONNECTION_TEST_FAILED": 502,
        "DISCONNECT_CONFIRMATION_REQUIRED": 409,
        "PRESET_NOT_FOUND": 404,
        "LOCKED_THEME_CONFIRMATION_REQUIRED": 409,
        "OVERRIDES_INVALID": 400,
    }
    return jsonify({"error": result.code, **getattr(result, "data", {})}), statuses.get(result.code, 409)


def create_commercial_ux_blueprint(dependencies: CommercialUxDependencies) -> Blueprint:
    routes = Blueprint("commercial_ux_routes", __name__)

    @routes.get("/setup")
    @dependencies.require_auth
    def setup_hub():
        return render_template("setup_hub.html")

    @routes.get("/api/setup/status")
    @dependencies.require_auth
    def setup_status():
        return _response(dependencies.get_ux_service().status())

    @routes.get("/api/setup/options")
    @dependencies.require_auth
    def setup_options():
        return _response(dependencies.get_ux_service().options())

    @routes.post("/api/setup/theme")
    @dependencies.require_auth
    def select_theme():
        incoming = request.get_json(force=True, silent=True) or {}
        result = dependencies.get_theme_service().activate(
            incoming.get("preset_id"),
            incoming.get("overrides"),
            confirmation=incoming.get("confirmation"),
        )
        return _response(result)

    @routes.post("/api/setup/oauth/<provider>/start")
    @dependencies.require_auth
    def start_oauth(provider: str):
        callback_url = url_for(
            "commercial_ux_routes.oauth_callback",
            provider=provider,
            _external=True,
        )
        return _response(dependencies.get_oauth_service().start(provider, callback_url))

    @routes.get("/setup/oauth/<provider>/callback")
    @dependencies.require_auth
    def oauth_callback(provider: str):
        error = request.args.get("error", "")
        if error:
            return redirect("/setup?" + urlencode({"oauth_error": error, "provider": provider}))
        result = dependencies.get_oauth_service().complete(
            provider,
            state_token=request.args.get("state", ""),
            code=request.args.get("code", ""),
        )
        if result.ok:
            return redirect("/setup?" + urlencode({"connected": provider}))
        return redirect("/setup?" + urlencode({"oauth_error": result.code, "provider": provider}))

    @routes.post("/api/setup/oauth/<provider>/test")
    @dependencies.require_auth
    def test_oauth(provider: str):
        return _response(dependencies.get_oauth_service().test_connection(provider))

    @routes.post("/api/setup/oauth/<provider>/disconnect")
    @dependencies.require_auth
    def disconnect_oauth(provider: str):
        incoming = request.get_json(force=True, silent=True) or {}
        return _response(
            dependencies.get_oauth_service().disconnect(
                provider,
                str(incoming.get("confirmation", "")),
            )
        )

    return routes
