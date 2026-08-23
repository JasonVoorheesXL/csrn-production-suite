from __future__ import annotations

from dataclasses import dataclass
import threading
from time import perf_counter
from typing import Any, Callable

from flask import Blueprint, jsonify, request

from live_command_service import command_id_from, current_revision
from runtime_diagnostics_service import (
    get_runtime_diagnostics,
    latest_id,
    new_request_id,
    safe_count,
)


RouteDecorator = Callable[[Callable[..., Any]], Callable[..., Any]]
State = dict[str, Any]


@dataclass(frozen=True)
class LiveGameRoutesDependencies:
    """Injected application boundaries used by the live-game Blueprint."""

    require_auth: RouteDecorator
    get_game_operations_service: Callable[[], Any]
    get_event_service: Callable[[], Any]
    get_rules_service: Callable[[], Any]
    get_statistics_service: Callable[[], Any]
    load_state: Callable[[], State]
    # Optional: falls back to load_state when not provided (e.g. in tests that
    # don't exercise the post-finalization reporting path). When provided,
    # this is a read-only variant that backfills history/events/plays from
    # the archived per-broadcast file once a broadcast has been finalized and
    # its live state cleared — see app.load_state_for_reporting().
    load_state_for_reporting: Callable[[], State] | None = None
    load_rosters: Callable[[], list[dict[str, Any]]] | None = None


def create_live_game_blueprint(
    dependencies: LiveGameRoutesDependencies,
) -> Blueprint:
    """Create live-game routes without importing the application root."""

    routes = Blueprint("live_game_routes", __name__)

    def load_state_for_reporting() -> State:
        loader = dependencies.load_state_for_reporting or dependencies.load_state
        return loader()

    def normalized_player_name(player: dict[str, Any]) -> str:
        return " ".join(
            str(
                player.get("display_name")
                or player.get("preferred_name")
                or f"{player.get('first_name', '')} {player.get('last_name', '')}"
                or player.get("name", "")
            ).casefold().split()
        )

    def decorate_statistics_headshots(statistics: dict[str, Any], state: State) -> dict[str, Any]:
        if dependencies.load_rosters is None:
            return statistics
        players = statistics.get("players")
        if not isinstance(players, list):
            return statistics
        try:
            rosters = dependencies.load_rosters()
        except Exception:
            return statistics
        if not isinstance(rosters, list):
            return statistics

        active_school_ids = {
            "home": str(state.get("home_school_id", "") or ""),
            "visitor": str(state.get("visitor_school_id", "") or ""),
        }
        roster_players: dict[str, list[dict[str, Any]]] = {"home": [], "visitor": []}
        season = str(state.get("season", "") or "")
        sport = str(state.get("sport", "") or "").casefold()
        for side, school_id in active_school_ids.items():
            if not school_id:
                continue
            candidates = [
                roster for roster in rosters
                if isinstance(roster, dict)
                and str(roster.get("school_id", "") or "") == school_id
            ]
            if season:
                season_matches = [
                    roster for roster in candidates
                    if str(roster.get("season", "") or "") == season
                ]
                if season_matches:
                    candidates = season_matches
            if sport:
                sport_matches = [
                    roster for roster in candidates
                    if str(roster.get("sport", "") or "").casefold() == sport
                ]
                if sport_matches:
                    candidates = sport_matches
            for roster in candidates:
                roster_players[side].extend([
                    player for player in roster.get("players", [])
                    if isinstance(player, dict)
                ])

        for row in players:
            if not isinstance(row, dict) or row.get("headshot"):
                continue
            side = str(row.get("team", "") or "")
            candidates = roster_players.get(side, [])
            number = str(row.get("number", "") or "").strip()
            matched = None
            if number:
                matched = next(
                    (
                        player for player in candidates
                        if str(player.get("number", "") or "").strip() == number
                    ),
                    None,
                )
            else:
                target_name = " ".join(str(row.get("name", "") or "").casefold().split())
                matched = next(
                    (player for player in candidates if normalized_player_name(player) == target_name),
                    None,
                )
            if matched and matched.get("headshot"):
                row["headshot"] = str(matched.get("headshot") or "")
        return statistics

    def state_summary(state: State | None) -> dict[str, Any]:
        if not isinstance(state, dict):
            return {}
        return {
            "state_revision": current_revision(state),
            "broadcast_id": str(state.get("broadcast_id", "") or ""),
            "play_count": safe_count(state.get("plays")),
            "event_count": safe_count(state.get("events")),
            "latest_play_id": latest_id(state.get("plays"), "play_id"),
            "latest_event_id": latest_id(state.get("events"), "id"),
        }

    def load_summary_safely() -> dict[str, Any]:
        try:
            return state_summary(dependencies.load_state())
        except Exception as exc:
            get_runtime_diagnostics().record(
                "DIAGNOSTIC_STATE_SUMMARY_FAILED",
                error_type=type(exc).__name__,
                error_message=str(exc)[:240],
            )
            return {}

    def log_route(
        *,
        event_type: str,
        route: str,
        action: str,
        request_id: str,
        payload: dict[str, Any],
        status: int,
        started: float,
        before: dict[str, Any],
        after: dict[str, Any] | None = None,
        result: Any | None = None,
        error: Any | None = None,
        response_uncertain: bool = False,
    ) -> None:
        after = after or {}
        data = getattr(result, "data", {}) if result is not None else {}
        play = data.get("play") if isinstance(data, dict) and isinstance(data.get("play"), dict) else {}
        event = data.get("event") if isinstance(data, dict) and isinstance(data.get("event"), dict) else {}
        duration_ms = round((perf_counter() - started) * 1000, 2)
        get_runtime_diagnostics().record(
            event_type,
            request_id=request_id,
            command_id=command_id_from(payload),
            client_id=str(payload.get("client_id", "") or ""),
            route=route,
            action=action,
            method=request.method,
            http_status=status,
            thread=threading.current_thread().name,
            duration_ms=duration_ms,
            slow_request=duration_ms > 500,
            severe_slow_request=duration_ms > 2000,
            state_revision_before=before.get("state_revision", 0),
            state_revision_after=after.get("state_revision", 0),
            broadcast_id=after.get("broadcast_id") or before.get("broadcast_id", ""),
            duplicate_replay=bool(
                isinstance(data, dict)
                and data.get("command_id")
                and before.get("state_revision") == after.get("state_revision")
            ),
            event_id=event.get("id", ""),
            play_id=play.get("play_id", ""),
            play_count_before=before.get("play_count", 0),
            play_count_after=after.get("play_count", 0),
            latest_play_id=after.get("latest_play_id", ""),
            error_type=type(error).__name__ if error else getattr(result, "code", ""),
            error_message=str(error)[:240] if error else "",
            response_uncertain=bool(response_uncertain),
        )

    def mutation_payload() -> dict[str, Any]:
        incoming = request.get_json(force=True) or {}
        return incoming if isinstance(incoming, dict) else {}

    @routes.post("/api/score")
    @dependencies.require_auth
    def update_score():
        request_id = new_request_id()
        payload = mutation_payload()
        started = perf_counter()
        before = load_summary_safely()
        result = dependencies.get_game_operations_service().score(payload)
        if result.code == "INVALID_SCORE_REQUEST":
            log_route(event_type="SERVER_MUTATION", route="/api/score", action="score", request_id=request_id, payload=payload, status=400, started=started, before=before, after=load_summary_safely(), result=result)
            return jsonify({"error": result.code}), 400
        if result.code == "CONTROL_SOURCE_LOCKED":
            log_route(event_type="SERVER_MUTATION", route="/api/score", action="score", request_id=request_id, payload=payload, status=409, started=started, before=before, after=load_summary_safely(), result=result)
            return jsonify(result.data), 409
        log_route(event_type="SERVER_MUTATION", route="/api/score", action="score", request_id=request_id, payload=payload, status=200, started=started, before=before, after=load_summary_safely(), result=result)
        return jsonify(result.data["state"])

    @routes.post("/api/set")
    @dependencies.require_auth
    def set_value():
        request_id = new_request_id()
        payload = mutation_payload()
        started = perf_counter()
        before = load_summary_safely()
        result = dependencies.get_game_operations_service().set_values(payload)
        if result.code == "CONTROL_SOURCE_LOCKED":
            log_route(event_type="SERVER_MUTATION", route="/api/set", action="set", request_id=request_id, payload=payload, status=409, started=started, before=before, after=load_summary_safely(), result=result)
            return jsonify(result.data), 409
        log_route(event_type="SERVER_MUTATION", route="/api/set", action=str(payload.get("period_action") or "set"), request_id=request_id, payload=payload, status=200, started=started, before=before, after=load_summary_safely(), result=result)
        return jsonify(result.data["state"])

    def build_statistics_payload() -> dict[str, Any]:
        state = load_state_for_reporting()
        result = dependencies.get_statistics_service().report(state)
        return decorate_statistics_headshots(result.data["statistics"], state)

    @routes.get("/api/statistics")
    @dependencies.require_auth
    def statistics_report():
        return jsonify(build_statistics_payload())

    @routes.get("/api/statistics/overlay-state")
    def statistics_overlay_state():
        # Read-only, unauthenticated: the OBS overlay (Collegiate Tech's
        # rotating stat rails and player-leader cards) has no operator login
        # session, so it cannot call the authenticated /api/statistics above.
        # Same payload, public, matching the existing /api/state and
        # /api/captions/overlay-state pattern.
        return jsonify(build_statistics_payload())

    @routes.get("/api/play-register")
    @dependencies.require_auth
    def play_register():
        state = load_state_for_reporting()
        plays = [play for play in list(state.get("plays") or []) if isinstance(play, dict)]
        events = [event for event in list(state.get("events") or []) if isinstance(event, dict)]
        payload = {
            "state_revision": current_revision(state),
            "broadcast_id": str(state.get("broadcast_id", "") or ""),
            "plays": plays,
            "events": events,
            "play_count": len(plays),
            "event_count": len(events),
            "latest_play_id": latest_id(plays, "play_id"),
            "latest_event_id": latest_id(events, "id"),
        }
        get_runtime_diagnostics().record(
            "SERVER_PLAY_REGISTER",
            route="/api/play-register",
            method=request.method,
            http_status=200,
            state_revision_after=payload["state_revision"],
            broadcast_id=payload["broadcast_id"],
            authoritative_play_count=payload["play_count"],
            authoritative_event_count=payload["event_count"],
            latest_play_id=payload["latest_play_id"],
            latest_event_id=payload["latest_event_id"],
        )
        return jsonify(payload)

    @routes.post("/api/control-source")
    @dependencies.require_auth
    def set_control_source():
        incoming = request.get_json(force=True) or {}
        result = dependencies.get_event_service().set_control_source(
            incoming.get("authority", ""),
            incoming,
        )
        if result.code == "INVALID_CONTROL_SOURCE":
            return jsonify({"error": result.code}), 400
        return jsonify(result.data["state"])

    @routes.post("/api/event-trigger")
    @dependencies.require_auth
    def event_trigger():
        request_id = new_request_id()
        payload = mutation_payload()
        started = perf_counter()
        before = load_summary_safely()
        result = dependencies.get_event_service().trigger(payload)
        if result.code == "INVALID_EVENT":
            log_route(event_type="SERVER_MUTATION", route="/api/event-trigger", action=str(payload.get("event") or "event"), request_id=request_id, payload=payload, status=400, started=started, before=before, after=load_summary_safely(), result=result)
            return jsonify({"error": result.code}), 400
        if result.code == "NO_ACTIVE_BROADCAST":
            log_route(event_type="SERVER_MUTATION", route="/api/event-trigger", action=str(payload.get("event") or "event"), request_id=request_id, payload=payload, status=409, started=started, before=before, after=load_summary_safely(), result=result)
            return jsonify({"error": result.code}), 409
        if result.code == "CONTROL_SOURCE_LOCKED":
            log_route(event_type="SERVER_MUTATION", route="/api/event-trigger", action=str(payload.get("event") or "event"), request_id=request_id, payload=payload, status=409, started=started, before=before, after=load_summary_safely(), result=result)
            return jsonify(result.data), 409
        log_route(event_type="SERVER_MUTATION", route="/api/event-trigger", action=str(payload.get("event") or "event"), request_id=request_id, payload=payload, status=200, started=started, before=before, after=load_summary_safely(), result=result)
        return jsonify(result.data)

    @routes.post("/api/game-correction")
    @dependencies.require_auth
    def game_correction():
        request_id = new_request_id()
        payload = mutation_payload()
        started = perf_counter()
        before = load_summary_safely()
        result = dependencies.get_event_service().quick_correction(payload)
        if result.code in {"INVALID_DOWN", "INVALID_POSSESSION"}:
            log_route(event_type="SERVER_MUTATION", route="/api/game-correction", action="game_correction", request_id=request_id, payload=payload, status=400, started=started, before=before, after=load_summary_safely(), result=result)
            return jsonify({"error": result.code}), 400
        if result.code == "CONTROL_SOURCE_LOCKED":
            log_route(event_type="SERVER_MUTATION", route="/api/game-correction", action="game_correction", request_id=request_id, payload=payload, status=409, started=started, before=before, after=load_summary_safely(), result=result)
            return jsonify(result.data), 409
        log_route(event_type="SERVER_MUTATION", route="/api/game-correction", action="game_correction", request_id=request_id, payload=payload, status=200, started=started, before=before, after=load_summary_safely(), result=result)
        return jsonify(result.data["state"])

    @routes.post("/api/events/<event_id>/edit")
    @dependencies.require_auth
    def edit_event(event_id: str):
        result = dependencies.get_event_service().edit(
            event_id,
            request.get_json(force=True) or {},
        )
        if result.code == "EVENT_NOT_FOUND":
            return jsonify({"error": result.code}), 404
        if result.code == "CONTROL_SOURCE_LOCKED":
            return jsonify(result.data), 409
        return jsonify(result.data)

    @routes.get("/api/corrections")
    @dependencies.require_auth
    def corrections_report():
        result = dependencies.get_event_service().corrections()
        return jsonify(result.data["corrections"])

    @routes.post("/api/toggle-scorebug")
    @dependencies.require_auth
    def toggle_scorebug():
        result = dependencies.get_game_operations_service().toggle_scorebug(
            request.get_json(silent=True) or {}
        )
        if result.code == "OBS_COMMAND_BLOCKED":
            return jsonify(
                {
                    "error": result.code,
                    "message": result.data.get("message", ""),
                }
            ), 409
        return jsonify(result.data["state"])

    @routes.post("/api/toggle-halftime")
    @dependencies.require_auth
    def toggle_halftime():
        result = dependencies.get_game_operations_service().toggle_halftime(
            request.get_json(silent=True) or {}
        )
        return jsonify(result.data["state"])

    @routes.post("/api/end-game")
    @dependencies.require_auth
    def end_game():
        result = dependencies.get_game_operations_service().end_game(
            request.get_json(silent=True) or {}
        )
        return jsonify(result.data["state"])

    @routes.post("/api/reset-data")
    @dependencies.require_auth
    def reset_data():
        result = dependencies.get_game_operations_service().reset_data(
            request.get_json(silent=True) or {}
        )
        return jsonify(result.data["state"])

    @routes.post("/api/new-broadcast")
    @dependencies.require_auth
    def new_broadcast():
        result = dependencies.get_game_operations_service().new_broadcast(
            request.get_json(silent=True) or {}
        )
        return jsonify(result.data["state"])

    @routes.post("/api/clock-control")
    @dependencies.require_auth
    def clock_control():
        request_id = new_request_id()
        payload = mutation_payload()
        started = perf_counter()
        before = load_summary_safely()
        result = dependencies.get_rules_service().clock_control(payload)
        log_route(event_type="SERVER_MUTATION", route="/api/clock-control", action=str(payload.get("action") or "clock"), request_id=request_id, payload=payload, status=200, started=started, before=before, after=load_summary_safely(), result=result)
        return jsonify(result.data["state"])

    @routes.post("/api/field-direction")
    @dependencies.require_auth
    def field_direction():
        result = dependencies.get_rules_service().field_direction(
            request.get_json(force=True) or {}
        )
        if result.code == "INVALID_DIRECTION":
            return jsonify({"error": result.code}), 400
        return jsonify(result.data["state"])

    @routes.post("/api/rules-play")
    @dependencies.require_auth
    def rules_play():
        request_id = new_request_id()
        payload = mutation_payload()
        started = perf_counter()
        before = load_summary_safely()
        result = None
        status = 500
        logged = False
        action = str(payload.get("play_type") or "play")

        try:
            result = dependencies.get_rules_service().play(payload)
            if result.code == "INVALID_PLAY":
                status = 400
                response = jsonify({"error": result.code})
            elif result.code == "NO_ACTIVE_BROADCAST":
                status = 409
                response = jsonify({"error": result.code})
            elif result.code == "CONTROL_SOURCE_LOCKED":
                status = 409
                response = jsonify(result.data)
            else:
                status = 200
                response = jsonify(result.data)

            log_route(
                event_type="SERVER_RULES_PLAY",
                route="/api/rules-play",
                action=action,
                request_id=request_id,
                payload=payload,
                status=status,
                started=started,
                before=before,
                after=load_summary_safely(),
                result=result,
            )
            logged = True
            if status == 200:
                return response
            return response, status
        except Exception as exc:
            if result is not None and not logged:
                try:
                    log_route(
                        event_type="SERVER_RULES_PLAY",
                        route="/api/rules-play",
                        action=action,
                        request_id=request_id,
                        payload=payload,
                        status=status,
                        started=started,
                        before=before,
                        after=load_summary_safely(),
                        result=result,
                        error=exc,
                        response_uncertain=True,
                    )
                except Exception:
                    # Preserve the original response-path exception. Diagnostics must
                    # never replace the failure Flask should surface to the caller.
                    pass
            raise

    @routes.post("/api/undo")
    @dependencies.require_auth
    def undo():
        request_id = new_request_id()
        payload = request.get_json(silent=True) or {}
        started = perf_counter()
        before = load_summary_safely()
        result = dependencies.get_event_service().undo(payload)
        log_route(event_type="SERVER_MUTATION", route="/api/undo", action="undo", request_id=request_id, payload=payload, status=200, started=started, before=before, after=load_summary_safely(), result=result)
        return jsonify(result.data["state"])

    @routes.post("/api/restore")
    @dependencies.require_auth
    def restore_undone():
        request_id = new_request_id()
        payload = request.get_json(silent=True) or {}
        started = perf_counter()
        before = load_summary_safely()
        result = dependencies.get_event_service().restore(payload)
        if not result.ok:
            log_route(event_type="SERVER_MUTATION", route="/api/restore", action="restore", request_id=request_id, payload=payload, status=409, started=started, before=before, after=load_summary_safely(), result=result)
            return jsonify({
                "error": result.code,
                "message": result.data.get("message", "Restore is unavailable."),
                "state": result.data.get("state", {}),
            }), 409
        log_route(event_type="SERVER_MUTATION", route="/api/restore", action="restore", request_id=request_id, payload=payload, status=200, started=started, before=before, after=load_summary_safely(), result=result)
        return jsonify(result.data["state"])

    return routes
