from __future__ import annotations

import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from flask import Blueprint, Response, jsonify, request, send_from_directory


RouteDecorator = Callable[[Callable[..., Any]], Callable[..., Any]]


@dataclass(frozen=True)
class SupportRoutesDependencies:
    """Injected application boundaries used by support-media routes."""

    require_auth: RouteDecorator
    get_support_media_service: Callable[[], Any]
    get_headshots_dir: Callable[[], Path]
    connection_port: int = 5050


def create_support_blueprint(
    dependencies: SupportRoutesDependencies,
) -> Blueprint:
    """Create player-headshot and connectivity routes."""

    routes = Blueprint("support_routes", __name__)

    @routes.get("/roster-headshots/<filename>")
    def roster_headshot_file(filename: str):
        response = send_from_directory(dependencies.get_headshots_dir(), filename)
        # Player headshots can be replaced in place. Prevent browsers and OBS
        # browser sources from holding onto an older image at the same URL.
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    @routes.post("/api/rosters/<roster_id>/players/<player_id>/headshot")
    @dependencies.require_auth
    def upload_player_headshot(roster_id: str, player_id: str):
        upload = request.files.get("headshot")
        if not upload or not upload.filename:
            return jsonify({"error": "HEADSHOT_FILE_REQUIRED"}), 400
        result = dependencies.get_support_media_service().upload_headshot(
            roster_id,
            player_id,
            original_filename=upload.filename,
            raw=upload.read(),
        )
        if result.code in {
            "HEADSHOT_FILE_REQUIRED",
            "UNSUPPORTED_IMAGE_TYPE",
            "INVALID_IMAGE",
            "IMAGE_TOO_SMALL",
        }:
            return jsonify({"error": result.code}), 400
        if result.code in {"ROSTER_NOT_FOUND", "PLAYER_NOT_FOUND"}:
            return jsonify({"error": result.code}), 404
        if result.code == "HEADSHOT_STORAGE_FAILED":
            return jsonify(
                {
                    "error": result.code,
                    "message": result.data.get("message", ""),
                }
            ), 500
        return jsonify(
            {
                "headshot": result.data["headshot"],
                "player": result.data["player"],
            }
        )

    def reel_oval() -> dict[str, Any]:
        return {name: request.form.get(name) for name in ("x", "y", "width", "height", "tolerance") if request.form.get(name) not in (None, "")}

    def reel_problem(result: Any):
        if result.code in {"HEADSHOT_FILE_REQUIRED", "UNSUPPORTED_IMAGE_TYPE", "INVALID_IMAGE"}:
            return jsonify({"error": result.code}), 400
        if result.code in {"ROSTER_NOT_FOUND", "PLAYER_NOT_FOUND"}:
            return jsonify({"error": result.code}), 404
        return jsonify({"error": result.code, "message": result.data.get("message", "")}), 500

    @routes.post("/api/reel-headshot/preview")
    @dependencies.require_auth
    def preview_reel_headshot():
        upload = request.files.get("photo")
        result = dependencies.get_support_media_service().preview_reel_headshot(
            original_filename=upload.filename if upload else "", raw=upload.read() if upload else None, **reel_oval(),
        )
        if result.code != "OK":
            return reel_problem(result)
        cut = result.data["cut"]
        return jsonify({"image": "data:image/png;base64," + base64.b64encode(cut.png).decode("ascii"), "low_resolution": cut.low_resolution})

    @routes.post("/api/rosters/<roster_id>/players/<player_id>/reel-headshot")
    @dependencies.require_auth
    def save_reel_headshot(roster_id: str, player_id: str):
        upload = request.files.get("photo")
        result = dependencies.get_support_media_service().save_reel_headshot(
            roster_id, player_id, original_filename=upload.filename if upload else "", raw=upload.read() if upload else None, **reel_oval(),
        )
        if result.code != "OK":
            return reel_problem(result)
        return jsonify(result.data)

    @routes.delete("/api/rosters/<roster_id>/players/<player_id>/reel-headshot")
    @dependencies.require_auth
    def remove_reel_headshot(roster_id: str, player_id: str):
        result = dependencies.get_support_media_service().remove_reel_headshot(roster_id, player_id)
        if result.code != "OK":
            return reel_problem(result)
        return jsonify(result.data)

    @routes.get("/api/connection-info")
    @dependencies.require_auth
    def connection_info():
        result = dependencies.get_support_media_service().connection_info(
            dependencies.connection_port
        )
        return jsonify(result.data["connection"])

    @routes.get("/api/connection-qr")
    @dependencies.require_auth
    def connection_qr():
        result = dependencies.get_support_media_service().qr_svg(
            request.args.get("url", "")
        )
        if result.code == "INVALID_URL":
            return jsonify({"error": result.code}), 400
        if result.code == "QR_GENERATION_FAILED":
            return jsonify(
                {
                    "error": result.code,
                    "message": result.data.get("message", ""),
                }
            ), 500
        return Response(
            result.data["svg"],
            mimetype=result.data["mimetype"],
            headers=result.data["headers"],
        )

    return routes
