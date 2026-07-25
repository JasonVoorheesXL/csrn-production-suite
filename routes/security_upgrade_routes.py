from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from flask import Blueprint, jsonify, request, session


@dataclass(frozen=True)
class SecurityUpgradeRoutesDependencies:
    """Injected boundaries used by the security and upgrade routes."""

    get_security_service: Callable[[], Any]
    load_security: Callable[[], Mapping[str, Any]]
    authenticated: Callable[[], bool]
    clock: Callable[[], float]
    get_upgrade_service: Callable[[], Any]


def create_security_upgrade_blueprint(
    dependencies: SecurityUpgradeRoutesDependencies,
) -> Blueprint:
    """Create public authentication and upgrade endpoints."""

    routes = Blueprint("security_upgrade_routes", __name__)

    @routes.get("/api/security-status")
    def security_status():
        security = dependencies.load_security()
        remaining = max(
            0,
            int(float(security.get("locked_until", 0)) - dependencies.clock()),
        )
        return jsonify(
            {
                "pin_configured": bool(security.get("pin_hash")),
                "authenticated": dependencies.authenticated(),
                "locked_seconds": remaining,
            }
        )

    @routes.post("/api/setup-pin")
    def setup_pin():
        data = request.get_json(force=True)
        pin = str(data.get("pin", ""))
        confirm = str(data.get("confirm", ""))

        result = dependencies.get_security_service().setup_pin(pin, confirm)
        if not result.ok:
            status = {
                "PIN_ALREADY_CONFIGURED": 409,
                "PIN_MUST_BE_6_DIGITS": 400,
                "PIN_MISMATCH": 400,
            }[result.code]
            return jsonify({"error": result.code}), status

        session.clear()
        session.permanent = True
        session["authenticated"] = True
        return jsonify({"ok": True})

    @routes.post("/api/login")
    def login():
        data = request.get_json(force=True)
        pin = str(data.get("pin", ""))
        result = dependencies.get_security_service().authenticate(pin)

        if result.ok:
            session.clear()
            session.permanent = True
            session["authenticated"] = True
            return jsonify({"ok": True})

        payload = {"error": result.code, **result.data}
        if result.code == "LOCKED":
            return jsonify(payload), 429
        return jsonify(payload), 401

    @routes.post("/api/logout")
    def logout():
        session.clear()
        return jsonify({"ok": True})

    @routes.get("/api/upgrade/candidate")
    def upgrade_candidate():
        result = dependencies.get_upgrade_service().candidate()
        if result.code == "INSPECTION_FAILED":
            return jsonify(
                {
                    "error": result.code,
                    "message": result.data.get("message", ""),
                }
            ), 500
        return jsonify(result.data["candidate"])

    @routes.get("/api/upgrade/status")
    def upgrade_status():
        result = dependencies.get_upgrade_service().status()
        return jsonify(result.data["report"])

    @routes.post("/api/upgrade/migrate")
    def run_upgrade_migration():
        incoming = request.get_json(silent=True) or {}
        result = dependencies.get_upgrade_service().run(
            incoming.get("include_security", True)
        )
        return jsonify(result.data["report"])

    return routes
