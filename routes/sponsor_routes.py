from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from flask import Blueprint, jsonify, request, send_from_directory


RouteDecorator = Callable[[Callable[..., Any]], Callable[..., Any]]


@dataclass(frozen=True)
class SponsorRoutesDependencies:
    require_auth: RouteDecorator
    get_sponsor_service: Callable[[], Any]
    load_sponsors: Callable[[], list[dict[str, Any]]]
    load_assets: Callable[[], list[dict[str, Any]]]
    save_assets: Callable[[list[dict[str, Any]]], None]
    clean_asset_record: Callable[[dict[str, Any], str], dict[str, Any]]
    asset_file_hash: Callable[[Path], str]
    get_asset_upload_dir: Callable[[], Path]
    get_sponsor_upload_dir: Callable[[], Path]
    clock: Callable[[], float]
    token_hex: Callable[[int], str]


def create_sponsor_blueprint(
    dependencies: SponsorRoutesDependencies,
) -> Blueprint:
    routes = Blueprint("sponsor_routes", __name__)

    @routes.get("/api/sponsors")
    @dependencies.require_auth
    def list_sponsors():
        return jsonify(dependencies.get_sponsor_service().list_payload())

    @routes.post("/api/sponsors")
    @dependencies.require_auth
    def create_sponsor():
        result = dependencies.get_sponsor_service().create(
            request.get_json(silent=True) or {}
        )
        if result.code == "SPONSOR_NAME_REQUIRED":
            return jsonify({"error": "Sponsor name is required."}), 400
        if result.code == "DUPLICATE_SPONSOR":
            return jsonify(
                {
                    "error": result.code,
                    "duplicate_sponsor": result.data["duplicate_sponsor"],
                }
            ), 409
        return jsonify({"sponsor": result.data["sponsor"]})

    @routes.put("/api/sponsors/<sponsor_id>")
    @dependencies.require_auth
    def update_sponsor(sponsor_id: str):
        result = dependencies.get_sponsor_service().update(
            sponsor_id,
            request.get_json(silent=True) or {},
        )
        if result.code == "SPONSOR_NOT_FOUND":
            return jsonify({"error": "Sponsor not found."}), 404
        if result.code == "DUPLICATE_SPONSOR":
            return jsonify(
                {
                    "error": result.code,
                    "duplicate_sponsor": result.data["duplicate_sponsor"],
                }
            ), 409
        return jsonify({"sponsor": result.data["sponsor"]})

    @routes.delete("/api/sponsors/<sponsor_id>")
    @dependencies.require_auth
    def delete_sponsor(sponsor_id: str):
        result = dependencies.get_sponsor_service().delete(sponsor_id)
        if result.code == "SPONSOR_NOT_FOUND":
            return jsonify({"error": "Sponsor not found."}), 404
        return jsonify({"ok": True})

    @routes.post("/api/sponsors/<sponsor_id>/logo")
    @dependencies.require_auth
    def upload_sponsor_logo(sponsor_id: str):
        upload = request.files.get("logo")
        if not upload or not upload.filename:
            return jsonify({"error": "Choose a logo file."}), 400

        suffix = Path(upload.filename).suffix.lower()
        if suffix not in {".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif"}:
            return jsonify({"error": "Unsupported logo type."}), 400

        duplicate_action = str(
            request.form.get("duplicate_action", "prompt")
        ).lower()
        sponsor = next(
            (
                item
                for item in dependencies.load_sponsors()
                if str(item.get("id")) == sponsor_id
            ),
            None,
        )
        if not sponsor:
            return jsonify({"error": "Save the sponsor first."}), 404

        upload_dir = dependencies.get_asset_upload_dir()
        upload_dir.mkdir(parents=True, exist_ok=True)
        temp = upload_dir / (
            f".upload-{dependencies.token_hex(8)}{suffix}"
        )
        upload.save(temp)
        sha256 = dependencies.asset_file_hash(temp)
        assets = dependencies.load_assets()
        existing = next(
            (
                item
                for item in assets
                if item.get("sha256") == sha256 and item.get("active", True)
            ),
            None,
        )

        if existing and duplicate_action == "prompt":
            temp.unlink(missing_ok=True)
            return jsonify(
                {"error": "DUPLICATE_ASSET", "duplicate_asset": existing}
            ), 409

        if existing and duplicate_action == "reuse":
            temp.unlink(missing_ok=True)
            asset = existing
        elif existing and duplicate_action == "replace":
            current_url = str(existing.get("file_url", ""))
            current_name = (
                current_url.rsplit("/", 1)[-1]
                if current_url.startswith("/asset-files/")
                else ""
            )
            target = (
                upload_dir / current_name
                if current_name
                else upload_dir / f"{existing['id']}{suffix}"
            )
            temp.replace(target)
            existing.update(
                {
                    "file_url": f"/asset-files/{target.name}",
                    "sha256": sha256,
                    "original_filename": upload.filename,
                    "updated_at": int(dependencies.clock()),
                }
            )
            dependencies.save_assets(assets)
            asset = existing
        else:
            asset_id = (
                f"asset-{int(dependencies.clock() * 1000)}-"
                f"{dependencies.token_hex(2)}"
            )
            filename = f"{asset_id}{suffix}"
            target = upload_dir / filename
            temp.replace(target)
            asset = dependencies.clean_asset_record(
                {
                    "id": asset_id,
                    "name": f"{sponsor.get('name', 'Sponsor')} Logo",
                    "category": "Sponsor",
                    "asset_type": "Logo",
                    "file_url": f"/asset-files/{filename}",
                    "rights_status": "Unverified",
                    "rights_owner": sponsor.get("name", ""),
                    "notes": "Created automatically from Sponsor Engine upload.",
                    "sha256": sha256,
                    "original_filename": upload.filename,
                    "active": True,
                },
                asset_id,
            )
            assets.append(asset)
            dependencies.save_assets(assets)

        result = dependencies.get_sponsor_service().link_asset(
            sponsor_id,
            str(asset.get("id", "")),
        )
        if result.code == "SPONSOR_NOT_FOUND":
            return jsonify({"error": "Save the sponsor first."}), 404

        return jsonify(
            {
                "logo_url": result.data["sponsor"].get("logo_url", ""),
                "asset": asset,
                "duplicate_reused": bool(
                    existing and duplicate_action == "reuse"
                ),
                "sponsor": result.data["sponsor"],
            }
        )

    @routes.put("/api/sponsors/<sponsor_id>/asset")
    @dependencies.require_auth
    def link_sponsor_asset(sponsor_id: str):
        asset_id = str(
            (request.get_json(silent=True) or {}).get("asset_id", "")
        ).strip()
        result = dependencies.get_sponsor_service().link_asset(
            sponsor_id,
            asset_id,
        )
        if result.code == "INVALID_SPONSOR_LOGO_ASSET":
            return jsonify(
                {"error": "Choose a valid Sponsor Logo asset."}
            ), 400
        if result.code == "SPONSOR_NOT_FOUND":
            return jsonify({"error": "Sponsor not found."}), 404
        return jsonify(result.data)

    @routes.get("/sponsor-logos/<filename>")
    def sponsor_logo_file(filename: str):
        return send_from_directory(
            dependencies.get_sponsor_upload_dir(),
            filename,
        )

    return routes
