from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from flask import Blueprint, jsonify, request, send_from_directory


RouteDecorator = Callable[[Callable[..., Any]], Callable[..., Any]]


@dataclass(frozen=True)
class PersonnelRoutesDependencies:
    require_auth: RouteDecorator
    get_personnel_service: Callable[[], Any]
    get_headshots_dir: Callable[[], Path]
    normalize_personnel_id: Callable[[str], str]


def create_personnel_blueprint(
    dependencies: PersonnelRoutesDependencies,
) -> Blueprint:
    routes = Blueprint("personnel_routes", __name__)

    @routes.get("/api/broadcasters")
    @dependencies.require_auth
    def list_broadcasters():
        include_inactive = str(
            request.args.get("include_inactive", "true")
        ).strip().lower() not in {"0", "false", "no", "off"}
        result = dependencies.get_personnel_service().list_records(
            include_inactive=include_inactive,
            category=str(request.args.get("category", "")),
            role=str(request.args.get("role", "")),
            school_id=str(request.args.get("school_id", "")),
        )
        return jsonify(result.data["personnel"])

    @routes.post("/api/broadcasters")
    @dependencies.require_auth
    def create_broadcaster():
        result = dependencies.get_personnel_service().create(
            request.get_json(force=True) or {}
        )
        if result.code in {"STAFF_NAME_REQUIRED", "INVALID_STAFF_ROLE"}:
            return jsonify({"error": result.code}), 400
        if result.code == "INVALID_SOCIAL_URL":
            return jsonify({"error": result.code, **result.data}), 400
        return jsonify(result.data["personnel"]), 201

    @routes.put("/api/broadcasters/<broadcaster_id>")
    @dependencies.require_auth
    def update_broadcaster(broadcaster_id: str):
        result = dependencies.get_personnel_service().update(
            broadcaster_id,
            request.get_json(force=True) or {},
        )
        if result.code == "BROADCASTER_NOT_FOUND":
            return jsonify({"error": result.code}), 404
        if result.code in {"STAFF_NAME_REQUIRED", "INVALID_STAFF_ROLE"}:
            return jsonify({"error": result.code}), 400
        if result.code == "INVALID_SOCIAL_URL":
            return jsonify({"error": result.code, **result.data}), 400
        return jsonify(result.data["personnel"])

    @routes.delete("/api/broadcasters/<broadcaster_id>")
    @dependencies.require_auth
    def delete_broadcaster(broadcaster_id: str):
        result = dependencies.get_personnel_service().delete(broadcaster_id)
        if result.code == "BROADCASTER_NOT_FOUND":
            return jsonify({"error": result.code}), 404
        return jsonify({"ok": True})

    @routes.get("/personnel-headshots/<filename>")
    def personnel_headshot_file(filename: str):
        return send_from_directory(dependencies.get_headshots_dir(), filename)

    @routes.post("/api/personnel/<personnel_id>/headshot")
    @dependencies.require_auth
    def upload_personnel_headshot(personnel_id: str):
        upload = request.files.get("file")
        if not upload or not upload.filename:
            return jsonify({"error": "FILE_REQUIRED"}), 400
        extension = Path(upload.filename).suffix.lower()
        if extension not in {".png", ".jpg", ".jpeg", ".webp"}:
            return jsonify({"error": "UNSUPPORTED_IMAGE"}), 400

        headshots_dir = dependencies.get_headshots_dir()
        headshots_dir.mkdir(parents=True, exist_ok=True)
        target = headshots_dir / (
            f"{dependencies.normalize_personnel_id(personnel_id)}{extension}"
        )
        upload.save(target)
        relative = "/personnel-headshots/" + target.name
        result = dependencies.get_personnel_service().attach_headshot(
            personnel_id,
            relative,
        )
        if result.code == "PERSONNEL_NOT_FOUND":
            target.unlink(missing_ok=True)
            return jsonify({"error": result.code}), 404
        return jsonify({"path": result.data["path"]})

    @routes.post("/api/validate-social")
    @dependencies.require_auth
    def validate_social():
        incoming = request.get_json(force=True) or {}
        result = dependencies.get_personnel_service().validate_social(
            str(incoming.get("platform", "")),
            str(incoming.get("value", "")),
        )
        return jsonify(result.data)

    return routes
