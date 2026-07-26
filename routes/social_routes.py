from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from flask import Blueprint, jsonify, request, send_from_directory


RouteDecorator = Callable[[Callable[..., Any]], Callable[..., Any]]


@dataclass(frozen=True)
class SocialRoutesDependencies:
    require_auth: RouteDecorator
    get_social_service: Callable[[], Any]
    get_cards_dir: Callable[[], Path]


def create_social_blueprint(dependencies: SocialRoutesDependencies) -> Blueprint:
    routes = Blueprint("social_routes", __name__)

    def error_response(result: Any):
        code = str(result.code)
        status = {
            "EVENT_NOT_FOUND": 404,
            "SOCIAL_POST_NOT_FOUND": 404,
            "SOCIAL_DRAFT_EXISTS": 409,
            "SOCIAL_POST_LOCKED": 409,
            "SPONSOR_NOT_ACTIVE": 409,
            "NO_FAILED_PLATFORMS": 409,
            "EVENT_NOT_SOCIAL_ELIGIBLE": 422,
            "SOCIAL_PLATFORM_REQUIRED": 400,
            "SOCIAL_TEXT_INVALID": 400,
            "PUBLISH_CONFIRMATION_REQUIRED": 400,
            "APPROVER_REQUIRED": 400,
        }.get(code, 400)
        payload = {"error": code}
        payload.update(result.data or {})
        return jsonify(payload), status

    @routes.get("/api/social/status")
    @dependencies.require_auth
    def social_status():
        result = dependencies.get_social_service().platform_status()
        return jsonify(result.data)

    @routes.get("/api/social/posts")
    @dependencies.require_auth
    def social_posts():
        result = dependencies.get_social_service().list_posts(
            status=str(request.args.get("status", "")),
            broadcast_id=str(request.args.get("broadcast_id", "")),
            event_id=str(request.args.get("event_id", "")),
        )
        return jsonify(result.data)

    @routes.post("/api/social/posts/event")
    @dependencies.require_auth
    def create_social_event_post():
        result = dependencies.get_social_service().create_event_draft(
            request.get_json(force=True) or {}
        )
        return jsonify(result.data), 201 if result.ok else error_response(result)

    @routes.get("/api/social/posts/<post_id>")
    @dependencies.require_auth
    def get_social_post(post_id: str):
        result = dependencies.get_social_service().read(post_id)
        if not result.ok:
            return error_response(result)
        return jsonify(result.data)

    @routes.put("/api/social/posts/<post_id>")
    @dependencies.require_auth
    def update_social_post(post_id: str):
        result = dependencies.get_social_service().update(
            post_id,
            request.get_json(force=True) or {},
        )
        if not result.ok:
            return error_response(result)
        return jsonify(result.data)

    @routes.post("/api/social/posts/<post_id>/publish")
    @dependencies.require_auth
    def publish_social_post(post_id: str):
        result = dependencies.get_social_service().publish(
            post_id,
            request.get_json(force=True) or {},
        )
        if not result.ok:
            return error_response(result)
        return jsonify(result.data)

    @routes.post("/api/social/posts/<post_id>/retry")
    @dependencies.require_auth
    def retry_social_post(post_id: str):
        result = dependencies.get_social_service().retry(
            post_id,
            request.get_json(force=True) or {},
        )
        if not result.ok:
            return error_response(result)
        return jsonify(result.data)

    @routes.post("/api/social/posts/<post_id>/cancel")
    @dependencies.require_auth
    def cancel_social_post(post_id: str):
        result = dependencies.get_social_service().cancel(post_id)
        if not result.ok:
            return error_response(result)
        return jsonify(result.data)

    @routes.get("/social-cards/<filename>")
    @dependencies.require_auth
    def social_card_file(filename: str):
        return send_from_directory(dependencies.get_cards_dir(), filename)

    return routes
