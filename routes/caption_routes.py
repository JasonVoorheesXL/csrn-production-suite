from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from flask import Blueprint, Response, jsonify, render_template, request


RouteDecorator = Callable[[Callable[..., Any]], Callable[..., Any]]


@dataclass(frozen=True)
class CaptionRoutesDependencies:
    require_auth: RouteDecorator
    get_caption_service: Callable[[], Any]


def create_caption_blueprint(dependencies: CaptionRoutesDependencies) -> Blueprint:
    routes = Blueprint("caption_routes", __name__)

    @routes.get("/captions")
    def caption_overlay():
        return render_template("captions.html")

    @routes.get("/api/captions/overlay-state")
    def caption_overlay_state():
        result = dependencies.get_caption_service().public_state()
        return jsonify(result.data)

    @routes.get("/api/captions/status")
    @dependencies.require_auth
    def caption_status():
        result = dependencies.get_caption_service().status()
        return jsonify(result.data)

    @routes.put("/api/captions/profile")
    @dependencies.require_auth
    def update_caption_profile():
        result = dependencies.get_caption_service().update_profile(
            request.get_json(force=True, silent=True)
        )
        if result.code == "PROFILE_REQUIRED":
            return jsonify({"error": result.code}), 400
        if result.code == "INVALID_PROFILE":
            return jsonify({"error": result.code, **result.data}), 400
        return jsonify(result.data)

    @routes.post("/api/captions/segments")
    @dependencies.require_auth
    def ingest_caption_segment():
        result = dependencies.get_caption_service().ingest_segment(
            request.get_json(force=True, silent=True)
        )
        if result.code == "LOW_CONFIDENCE":
            return jsonify({"status": result.code, **result.data}), 202
        if result.code in {
            "SEGMENT_REQUIRED",
            "CHANNEL_INVALID",
            "TEXT_REQUIRED",
            "CONFIDENCE_INVALID",
        }:
            return jsonify({"error": result.code}), 400
        if result.code in {"CHANNEL_NOT_CONFIGURED", "CHANNEL_DISABLED"}:
            return jsonify({"error": result.code}), 409
        return jsonify(result.data), 201

    @routes.post("/api/captions/visibility")
    @dependencies.require_auth
    def caption_visibility():
        incoming = request.get_json(force=True, silent=True) or {}
        result = dependencies.get_caption_service().set_visibility(
            incoming.get("visible")
        )
        if result.code == "VISIBLE_MUST_BE_BOOLEAN":
            return jsonify({"error": result.code}), 400
        return jsonify(result.data)

    @routes.post("/api/captions/clear")
    @dependencies.require_auth
    def clear_captions():
        result = dependencies.get_caption_service().clear()
        return jsonify(result.data)

    @routes.patch("/api/captions/segments/<segment_id>")
    @dependencies.require_auth
    def correct_caption_segment(segment_id: str):
        incoming = request.get_json(force=True, silent=True) or {}
        result = dependencies.get_caption_service().correct_segment(
            segment_id,
            incoming.get("text"),
        )
        if result.code == "TEXT_REQUIRED":
            return jsonify({"error": result.code}), 400
        if result.code == "SEGMENT_NOT_FOUND":
            return jsonify({"error": result.code}), 404
        return jsonify(result.data)

    @routes.get("/api/captions/transcripts/<broadcast_id>")
    @dependencies.require_auth
    def caption_transcript(broadcast_id: str):
        result = dependencies.get_caption_service().transcript(broadcast_id)
        return jsonify(result.data)

    @routes.get("/api/captions/transcripts/<broadcast_id>.srt")
    @dependencies.require_auth
    def caption_transcript_srt(broadcast_id: str):
        result = dependencies.get_caption_service().export_srt(broadcast_id)
        return Response(
            result.data["content"],
            mimetype=result.data["mimetype"],
            headers={"Content-Disposition": f'attachment; filename="{broadcast_id}.srt"'},
        )

    @routes.get("/api/captions/transcripts/<broadcast_id>.vtt")
    @dependencies.require_auth
    def caption_transcript_vtt(broadcast_id: str):
        result = dependencies.get_caption_service().export_vtt(broadcast_id)
        return Response(
            result.data["content"],
            mimetype=result.data["mimetype"],
            headers={"Content-Disposition": f'attachment; filename="{broadcast_id}.vtt"'},
        )

    return routes
