from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from flask import Blueprint, jsonify, request


RouteDecorator = Callable[[Callable[..., Any]], Callable[..., Any]]


@dataclass(frozen=True)
class DeploymentRoutesDependencies:
    require_auth: RouteDecorator
    get_deployment_service: Callable[[], Any]
    get_entitlement_service: Callable[[], Any]


def create_deployment_blueprint(dependencies: DeploymentRoutesDependencies) -> Blueprint:
    routes = Blueprint("deployment_routes", __name__)

    @routes.get("/api/deployment/status")
    @dependencies.require_auth
    def deployment_status():
        result = dependencies.get_deployment_service().status()
        return jsonify(result.data)

    @routes.get("/api/licensing/status")
    @dependencies.require_auth
    def licensing_status():
        result = dependencies.get_entitlement_service().status()
        return jsonify(result.data)

    @routes.get("/api/licensing/activation-request")
    @dependencies.require_auth
    def activation_request():
        result = dependencies.get_entitlement_service().installation_request()
        return jsonify(result.data)

    @routes.post("/api/licensing/install")
    @dependencies.require_auth
    def install_license():
        result = dependencies.get_entitlement_service().install_license(
            request.get_json(force=True, silent=True)
        )
        status = 200
        if result.code in {
            "LICENSE_OBJECT_REQUIRED",
            "PRODUCT_MISMATCH",
            "LICENSE_FIELDS_INVALID",
            "ENTITLEMENTS_INVALID",
        }:
            status = 400
        elif result.code in {
            "VERIFIER_NOT_CONFIGURED",
            "SIGNATURE_INVALID",
            "INSTALLATION_MISMATCH",
        }:
            status = 409
        return jsonify({"status": result.code, **result.data}), status

    @routes.post("/api/licensing/remove")
    @dependencies.require_auth
    def remove_license():
        incoming = request.get_json(force=True, silent=True) or {}
        result = dependencies.get_entitlement_service().remove_license(
            incoming.get("confirmation")
        )
        status = 409 if result.code == "CONFIRMATION_REQUIRED" else 200
        return jsonify({"status": result.code, **result.data}), status

    @routes.post("/api/deployment/update/validate")
    @dependencies.require_auth
    def validate_update():
        incoming = request.get_json(force=True, silent=True) or {}
        package_root = Path(str(incoming.get("package_root", "")))
        result = dependencies.get_deployment_service().validate_update(
            package_root,
            allow_downgrade=bool(incoming.get("allow_downgrade", False)),
        )
        status = 200 if result.ok else 409
        return jsonify({"status": result.code, **result.data}), status

    @routes.post("/api/deployment/update/prepare")
    @dependencies.require_auth
    def prepare_update():
        incoming = request.get_json(force=True, silent=True) or {}
        result = dependencies.get_deployment_service().prepare_update(
            Path(str(incoming.get("package_root", ""))),
            confirmation=incoming.get("confirmation"),
        )
        status = 200 if result.ok else 409
        return jsonify({"status": result.code, **result.data}), status

    @routes.post("/api/deployment/support-bundle")
    @dependencies.require_auth
    def create_support_bundle():
        incoming = request.get_json(force=True, silent=True) or {}
        result = dependencies.get_deployment_service().create_support_bundle(
            note=str(incoming.get("note", ""))
        )
        return jsonify({"status": result.code, **result.data})

    return routes
