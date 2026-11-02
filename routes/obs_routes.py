from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from flask import Blueprint, jsonify, request, send_file

import reel_audio


RouteDecorator = Callable[[Callable[..., Any]], Callable[..., Any]]


@dataclass(frozen=True)
class OBSRoutesDependencies:
    """Injected application boundaries used by the OBS Blueprint."""

    require_auth: RouteDecorator
    get_obs_service: Callable[[], Any]
    get_replay_audio_service: Callable[[], Any] | None = None


def create_obs_blueprint(dependencies: OBSRoutesDependencies) -> Blueprint:
    """Create OBS routes without importing the application composition root."""

    routes = Blueprint("obs_routes", __name__)

    @routes.get("/api/obs/status")
    @dependencies.require_auth
    def obs_status():
        result = dependencies.get_obs_service().status()
        return jsonify(result.data["status"])

    @routes.get("/api/obs/replay-audio")
    @dependencies.require_auth
    def obs_replay_audio_status():
        return jsonify(dependencies.get_replay_audio_service().status(check=True))

    @routes.post("/api/obs/replay-audio/start")
    @dependencies.require_auth
    def obs_replay_audio_start():
        return jsonify(dependencies.get_replay_audio_service().start_buffer())

    @routes.get("/api/broadcasts/<broadcast_id>/replay-audio/<int:play_at>.m4a")
    @dependencies.require_auth
    def obs_replay_audio_clip(broadcast_id: str, play_at: int):
        path = dependencies.get_replay_audio_service().clip_file(broadcast_id, play_at)
        if path is None:
            return jsonify({"error": "AUDIO_NOT_FOUND"}), 404
        return send_file(path, mimetype="audio/mp4")

    @routes.get("/api/broadcasts/<broadcast_id>/replay-audio/<int:play_at>/wave")
    @dependencies.require_auth
    def obs_replay_audio_wave(broadcast_id: str, play_at: int):
        path = dependencies.get_replay_audio_service().clip_file(broadcast_id, play_at)
        if path is None:
            return jsonify({"error": "AUDIO_NOT_FOUND"}), 404
        return jsonify(reel_audio.waveform(path))

    @routes.post("/api/obs/test")
    @dependencies.require_auth
    def test_obs_connection():
        result = dependencies.get_obs_service().test_connection()
        return jsonify(result.data["obs"])

    @routes.post("/api/obs/scorebug-visibility")
    @dependencies.require_auth
    def obs_scorebug_visibility():
        incoming = request.get_json(force=True) or {}
        result = dependencies.get_obs_service().scorebug_visibility(
            incoming.get("visible")
        )
        if result.code == "VISIBLE_MUST_BE_BOOLEAN":
            return jsonify({"error": result.code}), 400
        if result.code == "OBS_COMMAND_BLOCKED":
            return jsonify(
                {
                    "error": result.code,
                    "message": result.data.get("message", ""),
                }
            ), 409
        return jsonify(result.data["obs"])

    @routes.post("/api/obs/program-visual-mode")
    @dependencies.require_auth
    def obs_program_visual_mode():
        incoming = request.get_json(force=True) or {}
        result = dependencies.get_obs_service().program_visual_mode(
            incoming.get("mode", "")
        )
        if result.code == "OBS_COMMAND_BLOCKED":
            return jsonify(
                {
                    "error": result.code,
                    "message": result.data.get("message", ""),
                }
            ), 409
        return jsonify(result.data)

    return routes
