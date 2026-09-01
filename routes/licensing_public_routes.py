"""Round 22: unauthenticated license-file install for the gate screen.

`license_required.html` is served before any operator PIN exists on a fresh
install (and again for every renewal), so its "Choose License File" control
cannot post to the @require_auth `/api/licensing/install` route. This
blueprint exposes one sibling route that is deliberately open: the Ed25519
signature check inside `EntitlementService.install_license()` is the real
boundary, and the effect -- a valid license unlocks the app -- is benign.

Kept out of `deployment_routes` on purpose: that blueprint has an
"every route is authenticated" invariant with tests to match.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from flask import Blueprint, jsonify, request

# install_license() result code -> HTTP status (mirrors deployment_routes'
# authenticated JSON route).
_BAD_REQUEST_CODES = frozenset(
    {"LICENSE_OBJECT_REQUIRED", "PRODUCT_MISMATCH", "LICENSE_FIELDS_INVALID", "ENTITLEMENTS_INVALID"}
)
_CONFLICT_CODES = frozenset(
    {"VERIFIER_NOT_CONFIGURED", "SIGNATURE_INVALID", "INSTALLATION_MISMATCH"}
)
# Operator-facing wording for the gate screen.
_INSTALL_MESSAGES = {
    "LICENSE_INSTALLED": "License installed. Reload to return to broadcast controls.",
    "LICENSE_OBJECT_REQUIRED": "That file is not a license object.",
    "PRODUCT_MISMATCH": "That license is for a different product.",
    "LICENSE_FIELDS_INVALID": "That license is missing required fields or has an invalid status.",
    "ENTITLEMENTS_INVALID": "That license's features/sports list is malformed.",
    "VERIFIER_NOT_CONFIGURED": "This build cannot verify license signatures.",
    "SIGNATURE_INVALID": "That license's signature did not verify.",
    "INSTALLATION_MISMATCH": "That license is bound to a different installation.",
}


def _http_status(code: str) -> int:
    if code in _BAD_REQUEST_CODES:
        return 400
    if code in _CONFLICT_CODES:
        return 409
    return 200


@dataclass(frozen=True)
class LicensingPublicRoutesDependencies:
    get_entitlement_service: Callable[[], Any]


def create_licensing_public_blueprint(
    dependencies: LicensingPublicRoutesDependencies,
) -> Blueprint:
    routes = Blueprint("licensing_public_routes", __name__)

    @routes.post("/api/licensing/install-file")
    def install_license_file():
        upload = request.files.get("license")
        if upload is None or not getattr(upload, "filename", ""):
            return (
                jsonify(
                    {
                        "status": "LICENSE_FILE_REQUIRED",
                        "message": "Choose a license file to install.",
                    }
                ),
                400,
            )
        try:
            payload = json.loads(upload.read().decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return (
                jsonify(
                    {
                        "status": "LICENSE_FILE_UNREADABLE",
                        "message": "That file is not a valid license (expected a JSON license object).",
                    }
                ),
                400,
            )
        result = dependencies.get_entitlement_service().install_license(payload)
        body = {
            "status": result.code,
            "message": result.data.get("message")
            or _INSTALL_MESSAGES.get(result.code, result.code),
            **result.data,
        }
        return jsonify(body), _http_status(result.code)

    return routes
