from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from flask import Blueprint, jsonify, request, send_from_directory


RouteDecorator = Callable[[Callable[..., Any]], Callable[..., Any]]


@dataclass(frozen=True)
class LogoRoutesDependencies:
    require_auth: RouteDecorator
    get_logo_service: Callable[[], Any]
    get_base_dir: Callable[[], Path]
    get_school_logo_dir: Callable[[str], Path]
    normalize_school_id: Callable[[str], str]


def create_logo_blueprint(
    dependencies: LogoRoutesDependencies,
) -> Blueprint:
    routes = Blueprint("logo_routes", __name__)

    @routes.get("/school-logos/<school_id>/<filename>")
    def school_logo_file(school_id: str, filename: str):
        return send_from_directory(
            dependencies.get_school_logo_dir(school_id),
            filename,
        )

    @routes.post("/api/schools/<school_id>/logo/process")
    @dependencies.require_auth
    def process_school_logo(school_id: str):
        upload = request.files.get("logo")
        if not upload or not upload.filename:
            return jsonify({"error": "LOGO_FILE_REQUIRED"}), 400

        raw = upload.read()
        normalized_school_id = dependencies.normalize_school_id(school_id)
        folder = dependencies.get_school_logo_dir(school_id)

        def write_original(extension: str, payload: bytes) -> str:
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / f"original{extension}"
            path.write_bytes(payload)
            return str(
                path.relative_to(dependencies.get_base_dir())
            ).replace("\\", "/")

        def write_master(image: Any) -> str:
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / "round-master.png"
            image.save(path)
            return f"/school-logos/{normalized_school_id}/round-master.png"

        def write_scorebug(image: Any) -> str:
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / "round-scorebug.png"
            image.save(path)
            return f"/school-logos/{normalized_school_id}/round-scorebug.png"

        result = dependencies.get_logo_service().process_candidate(
            school_id,
            raw=raw,
            original_filename=upload.filename,
            write_original=write_original,
            write_master=write_master,
            write_scorebug=write_scorebug,
        )
        if result.code == "SCHOOL_NOT_FOUND":
            return jsonify({"error": result.code}), 404
        if result.code == "INVALID_IMAGE":
            return jsonify({"error": result.code}), 400
        if result.code == "LOGO_STORAGE_FAILED":
            return jsonify(
                {
                    "error": result.code,
                    "message": result.data.get("message", ""),
                }
            ), 500
        return jsonify(result.data)

    @routes.get("/api/logos")
    @dependencies.require_auth
    def list_logos():
        result = dependencies.get_logo_service().list_records(
            school_id=str(request.args.get("school_id", "")),
            designation=str(request.args.get("designation", "")),
            approval_status=str(request.args.get("approval_status", "")),
        )
        return jsonify(result.data["logos"])

    return routes
