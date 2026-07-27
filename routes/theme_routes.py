from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from flask import Blueprint, Response, jsonify, render_template, request


RouteDecorator = Callable[[Callable[..., Any]], Callable[..., Any]]


@dataclass(frozen=True)
class ThemeRoutesDependencies:
    require_auth: RouteDecorator
    get_theme_service: Callable[[], Any]


def create_theme_blueprint(dependencies: ThemeRoutesDependencies) -> Blueprint:
    routes = Blueprint("theme_routes", __name__)

    @routes.get("/themes")
    @dependencies.require_auth
    def theme_manager():
        return render_template("theme_manager.html")

    @routes.get("/themes/current.css")
    def current_theme_css():
        result = dependencies.get_theme_service().css()
        response = Response(result.data.get("css", ""), mimetype="text/css")
        response.headers["Cache-Control"] = "no-store, max-age=0"
        return response

    @routes.get("/api/themes/public-state")
    def public_theme_state():
        result = dependencies.get_theme_service().public_state()
        return jsonify(result.data)

    @routes.get("/api/themes/catalog")
    @dependencies.require_auth
    def theme_catalog():
        result = dependencies.get_theme_service().catalog()
        return jsonify(result.data)

    @routes.get("/api/themes/status")
    @dependencies.require_auth
    def theme_status():
        result = dependencies.get_theme_service().status()
        return jsonify(result.data)

    @routes.post("/api/themes/preview")
    @dependencies.require_auth
    def preview_theme():
        incoming = request.get_json(force=True, silent=True) or {}
        result = dependencies.get_theme_service().preview(
            incoming.get("preset_id"),
            incoming.get("overrides"),
        )
        if result.code == "PRESET_NOT_FOUND":
            return jsonify({"error": result.code}), 404
        if result.code == "OVERRIDES_INVALID":
            return jsonify({"error": result.code, **result.data}), 400
        return jsonify(result.data)

    @routes.post("/api/themes/activate")
    @dependencies.require_auth
    def activate_theme():
        incoming = request.get_json(force=True, silent=True) or {}
        result = dependencies.get_theme_service().activate(
            incoming.get("preset_id"),
            incoming.get("overrides"),
            confirmation=incoming.get("confirmation"),
        )
        if result.code == "PRESET_NOT_FOUND":
            return jsonify({"error": result.code}), 404
        if result.code == "OVERRIDES_INVALID":
            return jsonify({"error": result.code, **result.data}), 400
        if result.code == "LOCKED_THEME_CONFIRMATION_REQUIRED":
            return jsonify({"error": result.code}), 409
        return jsonify(result.data)

    @routes.post("/api/themes/lock")
    @dependencies.require_auth
    def lock_theme():
        incoming = request.get_json(force=True, silent=True) or {}
        result = dependencies.get_theme_service().set_lock(
            incoming.get("locked"),
            incoming.get("confirmation"),
        )
        if result.code == "LOCK_VALUE_REQUIRED":
            return jsonify({"error": result.code}), 400
        if result.code == "LOCK_CONFIRMATION_REQUIRED":
            return jsonify({"error": result.code, **result.data}), 409
        return jsonify(result.data)

    @routes.post("/api/themes/reset-overrides")
    @dependencies.require_auth
    def reset_theme_overrides():
        incoming = request.get_json(force=True, silent=True) or {}
        result = dependencies.get_theme_service().reset_overrides(
            confirmation=incoming.get("confirmation")
        )
        if result.code == "LOCKED_THEME_CONFIRMATION_REQUIRED":
            return jsonify({"error": result.code}), 409
        return jsonify(result.data)

    @routes.post("/api/themes/variants")
    @dependencies.require_auth
    def save_theme_variant():
        incoming = request.get_json(force=True, silent=True) or {}
        result = dependencies.get_theme_service().save_variant(
            incoming.get("name"),
            incoming.get("preset_id"),
            incoming.get("overrides"),
        )
        if result.code in {"VARIANT_NAME_INVALID", "OVERRIDES_INVALID"}:
            return jsonify({"error": result.code, **result.data}), 400
        if result.code == "PRESET_NOT_FOUND":
            return jsonify({"error": result.code}), 404
        if result.code == "VARIANT_LIMIT_REACHED":
            return jsonify({"error": result.code}), 409
        return jsonify(result.data)

    @routes.post("/api/themes/variants/<path:name>/activate")
    @dependencies.require_auth
    def activate_theme_variant(name: str):
        incoming = request.get_json(force=True, silent=True) or {}
        result = dependencies.get_theme_service().activate_variant(
            name,
            confirmation=incoming.get("confirmation"),
        )
        if result.code == "VARIANT_NOT_FOUND":
            return jsonify({"error": result.code}), 404
        if result.code == "LOCKED_THEME_CONFIRMATION_REQUIRED":
            return jsonify({"error": result.code}), 409
        return jsonify(result.data)

    @routes.delete("/api/themes/variants/<path:name>")
    @dependencies.require_auth
    def delete_theme_variant(name: str):
        incoming = request.get_json(force=True, silent=True) or {}
        result = dependencies.get_theme_service().delete_variant(
            name,
            incoming.get("confirmation"),
        )
        if result.code == "VARIANT_NOT_FOUND":
            return jsonify({"error": result.code}), 404
        if result.code == "VARIANT_DELETE_CONFIRMATION_REQUIRED":
            return jsonify({"error": result.code}), 409
        return jsonify(result.data)

    return routes
