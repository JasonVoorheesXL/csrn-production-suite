from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from flask import Blueprint, Response, jsonify, request


RouteDecorator = Callable[[Callable[..., Any]], Callable[..., Any]]


@dataclass(frozen=True)
class BroadcastRoutesDependencies:
    require_auth: RouteDecorator
    get_broadcast_service: Callable[[], Any]
    get_broadcaster_print_service: Callable[[], Any]


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

    @routes.get("/api/broadcasts")
    @dependencies.require_auth
    def list_broadcasts():
        include_archived = str(
            request.args.get("include_archived", "false")
        ).strip().lower() in {"1", "true", "yes", "y", "on"}
        result = dependencies.get_broadcast_service().list_records(
            include_archived=include_archived
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

    return routes
