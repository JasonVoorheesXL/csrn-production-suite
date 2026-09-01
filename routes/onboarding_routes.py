"""Round 22: first-run onboarding wizard backend.

Thin routes over existing service logic -- the Identity Profile write path
(Round 12/13), SchoolService.create, and pregame_presentation.save_
organization_logo. Deliberately NOT `@require_auth`: the wizard runs on a
fresh install where no operator PIN is configured yet, and each route is
inert once onboarding is complete.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from flask import Blueprint, jsonify, request


@dataclass(frozen=True)
class OnboardingRoutesDependencies:
    onboarding_incomplete: Callable[[], bool]
    available_sports: Callable[[], list[dict[str, str]]]
    default_sport: Callable[[], str]
    complete_onboarding: Callable[[dict[str, Any]], tuple[bool, str, str]]
    save_logo: Callable[[Any], tuple[int, dict[str, Any]]]


def create_onboarding_blueprint(dependencies: OnboardingRoutesDependencies) -> Blueprint:
    routes = Blueprint("onboarding_routes", __name__)

    @routes.get("/api/onboarding/context")
    def onboarding_context():
        return jsonify(
            {
                "sports": dependencies.available_sports(),
                "default_sport": dependencies.default_sport(),
                "onboarding_complete": not dependencies.onboarding_incomplete(),
            }
        )

    @routes.post("/api/onboarding/logo")
    def onboarding_logo():
        status, body = dependencies.save_logo(request.files.get("logo"))
        return jsonify(body), status

    @routes.post("/api/onboarding/complete")
    def onboarding_complete():
        if not dependencies.onboarding_incomplete():
            return (
                jsonify(
                    {
                        "error": "ALREADY_ONBOARDED",
                        "message": "First-run setup is already done.",
                    }
                ),
                409,
            )
        payload = request.get_json(force=True, silent=True) or {}
        ok, code, message = dependencies.complete_onboarding(payload)
        if not ok:
            return jsonify({"error": code, "message": message}), 400
        return jsonify({"ok": True})

    return routes
