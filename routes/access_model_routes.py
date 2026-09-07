"""Round 27 access model: the operator's switchable sport context.

The sport context is a session value (like ``authenticated``). It is set
at login from the sport icon the operator picked, and can be changed
afterwards from the top-nav switcher WITHOUT re-entering the PIN -- that is
what ``POST /api/sport-context`` is for. It scopes which rosters / teams /
sponsors the management views show; it is orthogonal to the Round 26
jurisdiction picker, which chooses the ruleset *inside* the football
context.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from flask import Blueprint, jsonify, request, session

import sport_families


RouteDecorator = Callable[[Callable[..., Any]], Callable[..., Any]]


@dataclass(frozen=True)
class AccessModelRoutesDependencies:
    require_auth: RouteDecorator
    licensed_sport_families: Callable[[], list[str]]


def create_access_model_blueprint(
    dependencies: AccessModelRoutesDependencies,
) -> Blueprint:
    routes = Blueprint("access_model_routes", __name__)

    @routes.get("/api/session-context")
    @dependencies.require_auth
    def session_context():
        licensed = list(dependencies.licensed_sport_families())
        return jsonify(
            sport_families.sport_context_view(
                session.get("sport_context", ""), licensed
            )
        )

    @routes.post("/api/sport-context")
    @dependencies.require_auth
    def set_sport_context():
        data = request.get_json(silent=True) or {}
        raw = str(data.get("sport", ""))
        licensed = list(dependencies.licensed_sport_families())

        def _view(context: str):
            return sport_families.sport_context_view(context, licensed)

        if raw.strip() == "":
            session.pop("sport_context", None)
            return jsonify(_view(""))

        resolved = sport_families.normalize_sport(raw)
        if not resolved or resolved == sport_families.GATEWAY:
            # "all_others" is a gateway, not a context -- pick a real sport.
            return jsonify(
                {"error": "SPORT_NOT_RECOGNIZED", **_view(session.get("sport_context", ""))}
            ), 400
        if not sport_families.is_engine_ready(resolved):
            return jsonify(
                {"error": "SPORT_COMING_SOON", **_view(session.get("sport_context", ""))}
            ), 400
        if not sport_families.context_is_licensed(resolved, licensed):
            return jsonify(
                {"error": "SPORT_NOT_LICENSED", **_view(session.get("sport_context", ""))}
            ), 403

        session["sport_context"] = resolved
        return jsonify(_view(resolved))

    return routes
