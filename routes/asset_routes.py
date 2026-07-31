from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from flask import Blueprint, jsonify, request, send_from_directory


RouteDecorator = Callable[[Callable[..., Any]], Callable[..., Any]]


@dataclass(frozen=True)
class AssetRoutesDependencies:
    require_auth: RouteDecorator
    get_asset_service: Callable[[], Any]
    get_upload_dir: Callable[[], Path]
    extension_allowed: Callable[[str], bool]
    normalize_asset_id: Callable[[str], str]
    clock: Callable[[], float]
    token_hex: Callable[[int], str]


def create_asset_blueprint(
    dependencies: AssetRoutesDependencies,
) -> Blueprint:
    routes = Blueprint("asset_routes", __name__)

    def managed_path(file_url: Any) -> Path | None:
        value = str(file_url or "").strip()
        prefix = "/asset-files/"
        if not value.startswith(prefix):
            return None
        filename = value[len(prefix):]
        if not filename or Path(filename).name != filename:
            return None
        upload_dir = dependencies.get_upload_dir().resolve()
        candidate = (upload_dir / filename).resolve()
        return candidate if candidate.parent == upload_dir else None

    def file_is_referenced(file_url: str, *, exclude_id: str = "") -> bool:
        rows = dependencies.get_asset_service().list_records().data.get("assets", [])
        return any(
            str(row.get("id", "")) != str(exclude_id)
            and str(row.get("file_url", "")).strip() == str(file_url or "").strip()
            for row in rows
        )

    def remove_unreferenced_managed_file(
        file_url: str,
        *,
        exclude_id: str = "",
    ) -> bool:
        target = managed_path(file_url)
        if target is None or file_is_referenced(file_url, exclude_id=exclude_id):
            return False
        if not target.exists() or not target.is_file():
            return False
        target.unlink()
        return True

    @routes.get("/api/assets")
    @dependencies.require_auth
    def list_assets():
        include_inactive = str(
            request.args.get("include_inactive", "true")
        ).strip().lower() not in {"0", "false", "no", "off"}
        result = dependencies.get_asset_service().list_records(
            include_inactive=include_inactive,
            category=str(request.args.get("category", "")),
            asset_type=str(request.args.get("asset_type", "")),
            rights_status=str(request.args.get("rights_status", "")),
            placement=str(request.args.get("placement", "")),
        )
        return jsonify(result.data)

    @routes.get("/api/assets/storage")
    @dependencies.require_auth
    def asset_storage():
        upload_dir = dependencies.get_upload_dir()
        rows = dependencies.get_asset_service().list_records().data.get("assets", [])
        referenced = {
            str(row.get("file_url", "")).strip()
            for row in rows
            if managed_path(row.get("file_url")) is not None
        }
        files = (
            [path for path in upload_dir.iterdir() if path.is_file()]
            if upload_dir.exists()
            else []
        )
        orphan_files = [
            path
            for path in files
            if f"/asset-files/{path.name}" not in referenced
        ]
        return jsonify(
            {
                "managed_file_count": len(files),
                "managed_bytes": sum(path.stat().st_size for path in files),
                "orphan_count": len(orphan_files),
                "orphan_bytes": sum(path.stat().st_size for path in orphan_files),
            }
        )

    @routes.post("/api/assets")
    @dependencies.require_auth
    def create_asset():
        result = dependencies.get_asset_service().create(
            request.get_json(silent=True) or {}
        )
        if result.code == "ASSET_NAME_REQUIRED":
            return jsonify({"error": "Asset name is required."}), 400
        return jsonify({"asset": result.data["asset"]})

    @routes.put("/api/assets/<asset_id>")
    @dependencies.require_auth
    def update_asset(asset_id: str):
        result = dependencies.get_asset_service().update(
            asset_id,
            request.get_json(silent=True) or {},
        )
        if result.code == "ASSET_NOT_FOUND":
            return jsonify({"error": "Asset not found."}), 404
        if result.code == "ASSET_NAME_REQUIRED":
            return jsonify({"error": "Asset name is required."}), 400
        return jsonify({"asset": result.data["asset"]})

    @routes.delete("/api/assets/<asset_id>")
    @dependencies.require_auth
    def delete_asset(asset_id: str):
        service = dependencies.get_asset_service()
        current = service.read(asset_id)
        result = service.delete(asset_id)
        if result.code == "ASSET_NOT_FOUND":
            return jsonify({"error": "Asset not found."}), 404
        file_url = str(current.data.get("asset", {}).get("file_url", ""))
        media_deleted = remove_unreferenced_managed_file(file_url)
        return jsonify({"ok": True, "media_deleted": media_deleted})

    @routes.post("/api/assets/<asset_id>/upload")
    @dependencies.require_auth
    def upload_asset(asset_id: str):
        upload = request.files.get("asset")
        if not upload or not upload.filename:
            return jsonify({"error": "Choose a file to upload."}), 400

        suffix = Path(upload.filename).suffix.lower()
        if not dependencies.extension_allowed(upload.filename):
            return jsonify({"error": "Unsupported asset file type."}), 400

        duplicate_action = str(
            request.form.get("duplicate_action", "prompt")
        ).lower()
        service = dependencies.get_asset_service()
        current_result = service.read(asset_id)
        if current_result.code == "ASSET_NOT_FOUND":
            return jsonify(
                {"error": "Save the asset record before uploading."}
            ), 404

        upload_dir = dependencies.get_upload_dir()
        upload_dir.mkdir(parents=True, exist_ok=True)
        safe_id = dependencies.normalize_asset_id(asset_id)
        temp = upload_dir / (
            f".upload-{dependencies.token_hex(8)}{suffix}"
        )
        upload.save(temp)
        sha256 = service.file_hash(temp)
        duplicate = service.duplicate_by_hash(
            sha256,
            exclude_id=asset_id,
        )

        if duplicate and duplicate_action == "prompt":
            temp.unlink(missing_ok=True)
            return jsonify(
                {"error": "DUPLICATE_ASSET", "duplicate_asset": duplicate}
            ), 409

        if duplicate and duplicate_action == "reuse":
            temp.unlink(missing_ok=True)
            result = service.reuse_duplicate(
                asset_id,
                str(duplicate.get("id", "")),
            )
            return jsonify(
                {
                    "file_url": result.data["asset"].get("file_url", ""),
                    **result.data,
                }
            )

        if duplicate and duplicate_action == "replace":
            existing_url = str(duplicate.get("file_url", ""))
            existing_name = (
                existing_url.rsplit("/", 1)[-1]
                if existing_url.startswith("/asset-files/")
                else f"{duplicate['id']}{suffix}"
            )
            target = upload_dir / existing_name
            temp.replace(target)
            result = service.replace_duplicate(
                asset_id,
                str(duplicate.get("id", "")),
                file_url=f"/asset-files/{target.name}",
                sha256=sha256,
                original_filename=upload.filename,
            )
            return jsonify(
                {
                    "file_url": result.data["asset"]["file_url"],
                    **result.data,
                }
            )

        filename = f"{safe_id}-{int(dependencies.clock())}{suffix}"
        target = upload_dir / filename
        temp.replace(target)
        previous_url = str(
            current_result.data.get("asset", {}).get("file_url", "")
        )
        result = service.attach_file(
            asset_id,
            file_url=f"/asset-files/{filename}",
            sha256=sha256,
            original_filename=upload.filename,
        )
        if previous_url and previous_url != result.data["asset"]["file_url"]:
            remove_unreferenced_managed_file(previous_url, exclude_id=asset_id)
        return jsonify(
            {
                "file_url": result.data["asset"]["file_url"],
                "duplicate_asset": duplicate,
                "duplicate_kept": bool(duplicate),
            }
        )

    @routes.get("/asset-files/<filename>")
    def asset_file(filename: str):
        return send_from_directory(dependencies.get_upload_dir(), filename)

    return routes
