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
from typing import Any, Callable, Mapping

from flask import Blueprint, jsonify, request, session

import sport_families
import station_sports_service


RouteDecorator = Callable[[Callable[..., Any]], Callable[..., Any]]


@dataclass(frozen=True)
class AccessModelRoutesDependencies:
    require_auth: RouteDecorator
    licensed_sport_families: Callable[[], list[str]]
    # Audit round 3 (Settings > Sports): the station's on/off switches. The
    # licensed list above already leaves switched-off sports out; these let
    # the view say why and let Settings read and save the switches.
    switched_off_sport_families: Callable[[], list[str]] = lambda: []
    all_licensed_sport_families: Callable[[], list[str]] | None = None
    load_station_sports: Callable[[], Mapping[str, Any]] | None = None
    save_station_sports: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None


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
                session.get("sport_context", ""),
                licensed,
                dependencies.switched_off_sport_families(),
            )
        )

    @routes.post("/api/sport-context")
    @dependencies.require_auth
    def set_sport_context():
        data = request.get_json(silent=True) or {}
        raw = str(data.get("sport", ""))
        licensed = list(dependencies.licensed_sport_families())
        switched_off = list(dependencies.switched_off_sport_families())

        def _view(context: str):
            return sport_families.sport_context_view(context, licensed, switched_off)

        if raw.strip() == "":
            session.pop("sport_context", None)
            return jsonify(_view(""))

        resolved = sport_families.normalize_sport(raw)
        current = session.get("sport_context", "")
        if not resolved or resolved == sport_families.GATEWAY:
            # "all_others" is a gateway, not a context -- pick a real sport.
            return jsonify({"error": "SPORT_NOT_RECOGNIZED", **_view(current)}), 400

        if sport_families.base_family(resolved) in switched_off:
            return jsonify({"error": "SPORT_SWITCHED_OFF", **_view(current)}), 403

        if sport_families.is_engine_ready(resolved):
            if not sport_families.context_is_licensed(resolved, licensed):
                return jsonify({"error": "SPORT_NOT_LICENSED", **_view(current)}), 403
            session["sport_context"] = resolved
            return jsonify(_view(resolved))

        # No broadcast engine for this sport yet. Distinguish "you paid for
        # it, it just isn't built" from "you don't have it at all".
        if sport_families.context_is_licensed(resolved, licensed):
            return jsonify({"error": "SPORT_ENGINE_NOT_READY", **_view(current)}), 400
        return jsonify({"error": "SPORT_COMING_SOON", **_view(current)}), 400

    if dependencies.load_station_sports and dependencies.save_station_sports:

        def _station_sports() -> dict[str, Any]:
            licensed = set(
                (dependencies.all_licensed_sport_families or dependencies.licensed_sport_families)()
            )
            station = station_sports_service.normalize_station_sports(dependencies.load_station_sports())
            return {
                "on": station["on"],
                "sports": [
                    {
                        "family": family,
                        "label": sport_families.LABELS.get(family, family),
                        "licensed": family in licensed,
                    }
                    for family in station_sports_service.SWITCHABLE
                ],
            }

        @routes.get("/api/station-sports")
        @dependencies.require_auth
        def read_station_sports():
            return jsonify(_station_sports())

        @routes.post("/api/station-sports")
        @dependencies.require_auth
        def save_station_sports():
            incoming = request.get_json(force=True, silent=True)
            problem = station_sports_service.validate_station_sports(incoming)
            if problem:
                return jsonify({"error": "INVALID_STATION_SPORTS", "message": problem}), 400
            dependencies.save_station_sports(station_sports_service.normalize_station_sports(incoming))
            return jsonify(_station_sports())

    return routes
