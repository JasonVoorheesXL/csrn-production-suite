from __future__ import annotations

import copy
import os
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from flask import Blueprint, jsonify, request

from live_command_service import current_revision
from runtime_diagnostics_service import get_runtime_diagnostics, latest_id, new_request_id, safe_count


RouteDecorator = Callable[[Callable[..., Any]], Callable[..., Any]]

# Captured once at import so /api/health can report process uptime without
# touching any service, lock, or file. The launcher's readiness probe needs an
# endpoint that still answers a fast 200 even when the state write path is
# jammed -- so this route must never call load_state()/load_runtime_state() or
# take any lock.
_PROCESS_STARTED = time.time()


_OVERLAY_HEALTH: dict[str, Any] = {
    "status": "INIT",
    "overlay_last_success": 0,
    "overlay_last_revision": 0,
    "overlay_state_age": 0,
    "consecutive_failures": 0,
    "server_received_at": 0,
}


def _overlay_health_snapshot(now: float | None = None) -> dict[str, Any]:
    current = float(now if now is not None else time.time())
    health = copy.deepcopy(_OVERLAY_HEALTH)
    received_at = float(health.get("server_received_at") or 0)
    server_age_ms = max(0, int((current - received_at) * 1000)) if received_at else 0
    health["server_age_ms"] = server_age_ms
    if received_at and server_age_ms > 8000:
        health["status"] = "STALE"
    return health


@dataclass(frozen=True)
class SystemRoutesDependencies:
    """Injected application boundaries used by the system-routes Blueprint."""

    require_auth: RouteDecorator
    get_configuration_service: Callable[[], Any]
    diagnostic_status: Callable[[], Mapping[str, Any]]
    load_state: Callable[[], Mapping[str, Any]]
    load_runtime_state: Callable[[], Mapping[str, Any]]
    public_state: Callable[[Mapping[str, Any]], Mapping[str, Any]]
    runtime_state: Callable[[Mapping[str, Any]], Mapping[str, Any]]
    readiness_payload: Callable[[], Mapping[str, Any]]
    load_build_journal: Callable[[], Any]


def create_system_blueprint(
    dependencies: SystemRoutesDependencies,
) -> Blueprint:
    """Create the first Phase 5 route Blueprint without owning business logic."""

    routes = Blueprint("system_routes", __name__)

    @routes.get("/api/config")
    @dependencies.require_auth
    def get_config():
        result = dependencies.get_configuration_service().read()
        return jsonify(result.data["config"])

    @routes.post("/api/config")
    @dependencies.require_auth
    def update_config():
        incoming = request.get_json(force=True)
        result = dependencies.get_configuration_service().update(incoming)
        if result.code == "CONFIG_PAYLOAD_REQUIRED":
            return jsonify({"error": result.code}), 400
        if result.code == "INVALID_SOCIAL_URL":
            return jsonify(
                {
                    "error": result.code,
                    "fields": result.data.get("fields", {}),
                }
            ), 400
        return jsonify(result.data["config"])

    @routes.get("/api/diagnostics")
    @dependencies.require_auth
    def diagnostics():
        return jsonify(dict(dependencies.diagnostic_status()))

    @routes.get("/api/health")
    def get_health():
        # Public, dependency-free liveness probe for CSRN_GAME_DAY_LAUNCHER.ps1.
        # Intentionally does NOT read game state or take any lock: the launcher
        # uses it to tell "healthy" apart from "port bound but hung", so it has
        # to answer even when a mutation is stuck holding the state lock.
        now = time.time()
        return jsonify(
            {
                "status": "ok",
                "service": "csrn",
                "pid": os.getpid(),
                "time": int(now),
                "uptime_s": int(max(0.0, now - _PROCESS_STARTED)),
            }
        )

    @routes.get("/api/state")
    def get_state():
        # Read-only endpoint for authenticated controls and the OBS overlay.
        state = dependencies.load_state()
        return jsonify(dict(dependencies.public_state(state)))

    @routes.get("/api/runtime-state")
    def get_runtime_state():
        started = time.perf_counter()
        request_id = new_request_id()
        state = dependencies.load_runtime_state()
        payload = dict(dependencies.runtime_state(state))
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        get_runtime_diagnostics().record(
            "SERVER_RUNTIME_STATE",
            request_id=request_id,
            route="/api/runtime-state",
            method=request.method,
            http_status=200,
            duration_ms=duration_ms,
            slow_request=duration_ms > 500,
            severe_slow_request=duration_ms > 2000,
            state_revision_after=current_revision(state),
            broadcast_id=str(state.get("broadcast_id", "") or ""),
            authoritative_play_count=safe_count(state.get("plays")),
            authoritative_event_count=safe_count(state.get("events")),
            latest_play_id=latest_id(state.get("plays"), "play_id"),
            latest_event_id=latest_id(state.get("events"), "id"),
            runtime_contains_plays=isinstance(payload.get("plays"), list),
            runtime_play_count=safe_count(payload.get("plays")),
        )
        return jsonify(payload)

    @routes.post("/api/overlay-health")
    def report_overlay_health():
        payload = request.get_json(silent=True) or {}
        now = time.time()
        _OVERLAY_HEALTH.update(
            {
                "status": str(payload.get("status") or "UNKNOWN").upper(),
                "overlay_last_success": int(payload.get("overlay_last_success") or 0),
                "overlay_last_revision": int(payload.get("overlay_last_revision") or 0),
                "overlay_state_age": int(payload.get("overlay_state_age") or 0),
                "consecutive_failures": int(payload.get("consecutive_failures") or 0),
                "reported_at": int(payload.get("reported_at") or 0),
                "server_received_at": now,
            }
        )
        return jsonify(_overlay_health_snapshot(now))

    @routes.get("/api/overlay-health")
    @dependencies.require_auth
    def get_overlay_health():
        return jsonify(_overlay_health_snapshot())

    @routes.post("/api/client-telemetry")
    @dependencies.require_auth
    def client_telemetry():
        payload = request.get_json(silent=True) or {}
        if not isinstance(payload, dict):
            payload = {}
        get_runtime_diagnostics().record(
            "CLIENT_TELEMETRY",
            route="/api/client-telemetry",
            method=request.method,
            client_event=str(payload.get("event_type") or payload.get("type") or "CLIENT_EVENT"),
            client_id=str(payload.get("client_id", "") or ""),
            client_role=str(payload.get("client_role", "") or ""),
            revision=payload.get("revision", 0),
            broadcast_id=str(payload.get("broadcast_id", "") or ""),
            play_count=payload.get("play_count", 0),
            rendered_play_count=payload.get("rendered_play_count", 0),
            received_play_count=payload.get("received_play_count", 0),
            latest_play_id=str(payload.get("latest_play_id", "") or ""),
            previous_count=payload.get("previous_count", 0),
            new_count=payload.get("new_count", 0),
            severity=str(payload.get("severity", "") or ""),
            duration_ms=payload.get("duration_ms", 0),
            status=str(payload.get("status", "") or ""),
        )
        return jsonify({"ok": True})

    @routes.get("/api/runtime-diagnostics")
    @dependencies.require_auth
    def runtime_diagnostics():
        try:
            limit = int(request.args.get("limit", "200"))
        except ValueError:
            limit = 200
        state = dependencies.load_runtime_state()
        snapshot = get_runtime_diagnostics().snapshot(limit=limit)
        snapshot["current"] = {
            "state_revision": current_revision(state),
            "broadcast_id": str(state.get("broadcast_id", "") or ""),
            "authoritative_play_count": safe_count(state.get("plays")),
            "authoritative_event_count": safe_count(state.get("events")),
            "latest_play_id": latest_id(state.get("plays"), "play_id"),
            "latest_event_id": latest_id(state.get("events"), "id"),
            "overlay_health": _overlay_health_snapshot(),
        }
        return jsonify(snapshot)

    @routes.post("/api/runtime-diagnostics/export")
    @dependencies.require_auth
    def export_runtime_diagnostics():
        bundle = get_runtime_diagnostics().export_bundle(
            load_state=dependencies.load_state,
            runtime_state=dependencies.runtime_state,
            overlay_health=_overlay_health_snapshot(),
        )
        return jsonify({"bundle_path": str(bundle)})

    @routes.get("/api/readiness")
    @dependencies.require_auth
    def readiness():
        return jsonify(dict(dependencies.readiness_payload()))

    @routes.get("/api/build-journal")
    @dependencies.require_auth
    def build_journal():
        return jsonify(dependencies.load_build_journal())

    return routes
