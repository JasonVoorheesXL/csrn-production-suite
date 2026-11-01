from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from flask import Blueprint, Response, jsonify, request


RouteDecorator = Callable[[Callable[..., Any]], Callable[..., Any]]


def _no_sport_scope() -> str:
    return ""


@dataclass(frozen=True)
class BroadcastRoutesDependencies:
    require_auth: RouteDecorator
    get_broadcast_service: Callable[[], Any]
    get_broadcaster_print_service: Callable[[], Any]
    get_social_media_preview_service: Callable[[], Any]
    get_maxpreps_export_service: Callable[[], Any]
    get_ai_writer: Callable[[], Any] = lambda: None
    # The operator's exact active sport context (not base_family-collapsed --
    # Game Manager fully separates football/canadian_football broadcasts,
    # matching the roster/sponsor fix). "" -> list every broadcast.
    sport_scope: Callable[[], str] = _no_sport_scope


def create_broadcast_blueprint(
    dependencies: BroadcastRoutesDependencies,
) -> Blueprint:
    routes = Blueprint("broadcast_routes", __name__)

    @routes.post("/api/create-broadcast")
    @dependencies.require_auth
    def create_broadcast():
        result = dependencies.get_broadcast_service().create(
            request.get_json(force=True) or {}
        )
        return jsonify(result.data)

    @routes.get("/api/rulesets")
    @dependencies.require_auth
    def list_rulesets():
        """Shipped rulesets + their jurisdiction, for the broadcast-creation
        jurisdiction picker to group and select from."""
        import ruleset_service

        return jsonify({"rulesets": ruleset_service.available_rulesets()})

    @routes.get("/api/broadcasts")
    @dependencies.require_auth
    def list_broadcasts():
        include_archived = str(
            request.args.get("include_archived", "false")
        ).strip().lower() in {"1", "true", "yes", "y", "on"}
        result = dependencies.get_broadcast_service().list_records(
            include_archived=include_archived,
            sport_scope=dependencies.sport_scope(),
        )
        return jsonify(result.data["broadcasts"])

    @routes.get("/api/broadcasts/inherited-record")
    @dependencies.require_auth
    def broadcast_inherited_record():
        result = dependencies.get_broadcast_service().inherited_record(
            request.args.get("team", ""),
            request.args.get("sport", ""),
            request.args.get("season", ""),
        )
        return jsonify(result.data["inheritance"])

    @routes.get("/api/broadcasts/<broadcast_id>")
    @dependencies.require_auth
    def get_broadcast_record(broadcast_id: str):
        result = dependencies.get_broadcast_service().read(broadcast_id)
        if result.code == "NOT_FOUND":
            return jsonify({"error": "NOT_FOUND"}), 404
        return jsonify(result.data["broadcast"])

    @routes.put("/api/broadcasts/<broadcast_id>")
    @dependencies.require_auth
    def update_broadcast_record(broadcast_id: str):
        result = dependencies.get_broadcast_service().update(
            broadcast_id,
            request.get_json(force=True) or {},
        )
        if result.code == "NOT_FOUND":
            return jsonify({"error": "NOT_FOUND"}), 404
        return jsonify(result.data)

    @routes.put("/api/broadcasts/<broadcast_id>/status")
    @dependencies.require_auth
    def set_broadcast_status(broadcast_id: str):
        incoming = request.get_json(force=True) or {}
        result = dependencies.get_broadcast_service().set_status(
            broadcast_id,
            incoming.get("status", ""),
        )
        if result.code == "INVALID_STATUS":
            return jsonify({"error": "INVALID_STATUS"}), 400
        if result.code == "NOT_FOUND":
            return jsonify({"error": "NOT_FOUND"}), 404
        return jsonify(result.data["broadcast"])

    @routes.delete("/api/broadcasts/<broadcast_id>")
    @dependencies.require_auth
    def delete_broadcast_record(broadcast_id: str):
        result = dependencies.get_broadcast_service().delete(broadcast_id)
        if result.code == "NOT_FOUND":
            return jsonify({"error": "NOT_FOUND"}), 404
        return jsonify(result.data)

    @routes.get("/api/broadcasts/<broadcast_id>/broadcaster-print-sheet.pdf")
    @dependencies.require_auth
    def broadcaster_print_sheet(broadcast_id: str):
        result = dependencies.get_broadcaster_print_service().generate(broadcast_id)

        if result.code == "BROADCAST_NOT_FOUND":
            return jsonify({"error": result.code}), 404

        if result.code == "PDF_GENERATION_FAILED":
            return jsonify(
                {
                    "error": result.code,
                    "message": result.data.get(
                        "message",
                        "Unable to generate broadcaster print sheet.",
                    ),
                }
            ), 500

        response = Response(
            result.data["pdf"],
            mimetype="application/pdf",
        )
        response.headers["Content-Disposition"] = (
            f'attachment; filename="{result.data["filename"]}"'
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    @routes.get("/api/broadcasts/<broadcast_id>/social-preview.png")
    @dependencies.require_auth
    def social_media_preview(broadcast_id: str):
        result = dependencies.get_social_media_preview_service().generate(broadcast_id)

        if result.code == "BROADCAST_NOT_FOUND":
            return jsonify({"error": result.code}), 404

        if result.code == "IMAGE_GENERATION_FAILED":
            return jsonify(
                {
                    "error": result.code,
                    "message": result.data.get(
                        "message",
                        "Unable to generate the social media preview image.",
                    ),
                }
            ), 500

        response = Response(
            result.data["image"],
            mimetype="image/png",
        )
        response.headers["Content-Disposition"] = (
            f'inline; filename="{result.data["filename"]}"'
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    @routes.get("/api/broadcasts/<broadcast_id>/postgame-story")
    @dependencies.require_auth
    def postgame_story(broadcast_id: str):
        variant = request.args.get("variant", "0")
        result = dependencies.get_social_media_preview_service().postgame_story(
            broadcast_id,
            variant=int(variant) if variant.isdigit() else 0,
            sponsor_id=request.args.get("sponsor", ""),
            player_of_game=request.args.get("player", ""),
        )
        if result.code == "BROADCAST_NOT_FOUND":
            return jsonify({"error": result.code}), 404
        if result.code == "NO_GAME_DATA":
            return jsonify(
                {"error": result.code, "message": "No plays were recorded for this game, so there is nothing to write about."}
            ), 409
        return jsonify(result.data)

    @routes.get("/api/broadcasts/<broadcast_id>/pregame-story")
    @dependencies.require_auth
    def pregame_story(broadcast_id: str):
        variant = request.args.get("variant", "0")
        result = dependencies.get_social_media_preview_service().pregame_story(
            broadcast_id,
            variant=int(variant) if variant.isdigit() else 0,
            sponsor_id=request.args.get("sponsor", ""),
        )
        if result.code == "BROADCAST_NOT_FOUND":
            return jsonify({"error": result.code}), 404
        return jsonify(result.data)

    @routes.post("/api/broadcasts/<broadcast_id>/ai-story")
    @dependencies.require_auth
    def ai_story(broadcast_id: str):
        payload = request.get_json(silent=True) or {}
        result = dependencies.get_social_media_preview_service().ai_story(
            str(payload.get("kind", "postgame")),
            broadcast_id,
            sponsor_id=str(payload.get("sponsor", "") or ""),
            player_of_game=",".join(payload["player"]) if isinstance(payload.get("player"), list) else str(payload.get("player", "") or ""),
            previous=str(payload.get("previous", "") or "")[:20000],
            notes=[str(n)[:1000] for n in (payload.get("notes") or []) if str(n).strip()][:20],
            instructions=str(payload.get("instructions", "") or "")[:4000],
        )
        if result.code == "BROADCAST_NOT_FOUND":
            return jsonify({"error": result.code}), 404
        if result.code.startswith("AI_"):
            return jsonify({"error": result.code, "message": result.data.get("message", "The AI writer could not revise the story.")}), 502
        if result.code == "NO_GAME_DATA":
            return jsonify(
                {"error": result.code, "message": "No plays were recorded for this game, so there is nothing to write about."}
            ), 409
        return jsonify(result.data)

    def _ai_writer_response(result):
        messages = {
            "AI_KEY_FORMAT": "That doesn't look like an Anthropic API key. It starts with sk-ant-.",
            "AI_NOT_CONFIGURED": "No API key is saved yet.",
            "AI_KEY_INVALID": "Anthropic did not accept this key.",
            "AI_UNREACHABLE": "Anthropic could not be reached. Check the internet connection.",
            "AI_BUSY": "Anthropic is busy right now. Try again in a minute.",
            "AI_NO_CREDIT": "Your Anthropic credit is used up. Add credit at console.anthropic.com under Billing.",
            "AI_UNAVAILABLE": "The AI writer is not installed in this copy of the app.",
        }
        if result.ok:
            return jsonify(result.data)
        status = 400 if result.code in {"AI_KEY_FORMAT", "AI_NOT_CONFIGURED"} else 502
        return jsonify({"error": result.code, "message": messages.get(result.code, "The AI writer test failed.")}), status

    @routes.get("/api/ai-writer")
    @dependencies.require_auth
    def ai_writer_status():
        writer = dependencies.get_ai_writer()
        return jsonify(writer.status() if writer else {"configured": False})

    @routes.post("/api/ai-writer/key")
    @dependencies.require_auth
    def ai_writer_save_key():
        payload = request.get_json(silent=True) or {}
        return _ai_writer_response(dependencies.get_ai_writer().set_key(str(payload.get("api_key", "") or "")))

    @routes.delete("/api/ai-writer/key")
    @dependencies.require_auth
    def ai_writer_remove_key():
        return _ai_writer_response(dependencies.get_ai_writer().remove_key())

    @routes.post("/api/ai-writer/test")
    @dependencies.require_auth
    def ai_writer_test():
        return _ai_writer_response(dependencies.get_ai_writer().test())

    @routes.get("/api/broadcasts/<broadcast_id>/postgame-story.png")
    @dependencies.require_auth
    def postgame_story_card(broadcast_id: str):
        variant = request.args.get("variant", "0")
        result = dependencies.get_social_media_preview_service().generate_postgame_card(
            broadcast_id,
            variant=int(variant) if variant.isdigit() else 0,
            headline=request.args.get("headline", ""),
            sponsor_id=request.args.get("sponsor", ""),
            player_of_game=request.args.get("player", ""),
            theme=request.args.get("theme", ""),
            logo_style=request.args.get("logo", ""),
        )
        if result.code == "BROADCAST_NOT_FOUND":
            return jsonify({"error": result.code}), 404
        if result.code == "IMAGE_GENERATION_FAILED":
            return jsonify(
                {"error": result.code, "message": result.data.get("message", "Unable to generate the postgame graphic.")}
            ), 500
        response = Response(result.data["image"], mimetype="image/png")
        response.headers["Content-Disposition"] = f'inline; filename="{result.data["filename"]}"'
        response.headers["Cache-Control"] = "no-store"
        return response

    @routes.get("/api/broadcasts/<broadcast_id>/final-score-preview.png")
    @dependencies.require_auth
    def final_score_preview(broadcast_id: str):
        result = dependencies.get_social_media_preview_service().generate_final_score(broadcast_id)

        if result.code == "BROADCAST_NOT_FOUND":
            return jsonify({"error": result.code}), 404

        if result.code == "IMAGE_GENERATION_FAILED":
            return jsonify(
                {
                    "error": result.code,
                    "message": result.data.get(
                        "message",
                        "Unable to generate the final score graphic.",
                    ),
                }
            ), 500

        response = Response(
            result.data["image"],
            mimetype="image/png",
        )
        response.headers["Content-Disposition"] = (
            f'inline; filename="{result.data["filename"]}"'
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    @routes.get("/api/broadcasts/<broadcast_id>/maxpreps-export.txt")
    @dependencies.require_auth
    def maxpreps_export(broadcast_id: str):
        team = request.args.get("team", "")
        result = dependencies.get_maxpreps_export_service().generate(broadcast_id, team)

        if result.code == "INVALID_TEAM":
            return jsonify(
                {
                    "error": result.code,
                    "message": "Pass ?team=home or ?team=visitor -- MaxPreps' "
                    "import is itself scoped to one team's account, so CSRN "
                    "exports one file per team rather than one per game.",
                }
            ), 400

        if result.code == "BROADCAST_NOT_FOUND":
            return jsonify({"error": result.code}), 404

        if result.code == "NO_PLAYER_DATA":
            return jsonify(
                {"error": result.code, "message": result.data["message"]}
            ), 422

        response = Response(
            result.data["content"],
            mimetype="text/plain",
        )
        response.headers["Content-Disposition"] = (
            f'attachment; filename="{result.data["filename"]}"'
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    return routes
