from __future__ import annotations

from pathlib import Path


APP_PATH = Path("app.py")


ASSET_HELPERS = '''def load_assets() -> list[dict[str, Any]]:
    ensure_data_architecture()
    if not ASSETS_FILE.exists():
        save_json(ASSETS_FILE, [])
        return []
    try:
        data = json.loads(ASSETS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return data if isinstance(data, list) else data.get("assets", [])


def save_assets(items: list[dict[str, Any]]) -> None:
    save_json(ASSETS_FILE, items)


ASSET_SERVICE: AssetService | None = None


def get_asset_service() -> AssetService:
    global ASSET_SERVICE
    if ASSET_SERVICE is None:
        ASSET_SERVICE = AssetService(
            load_assets=load_assets,
            save_assets=save_assets,
        )
    return ASSET_SERVICE


def asset_by_id(asset_id: str) -> dict[str, Any] | None:
    result = get_asset_service().read(asset_id)
    return result.data.get("asset") if result.ok else None


def asset_file_hash(path: Path) -> str:
    return AssetService.file_hash(path)


'''


CLEAN_ASSET_HELPER = '''def clean_asset_record(
    incoming: dict[str, Any],
    existing_id: str = "",
) -> dict[str, Any]:
    existing = asset_by_id(existing_id) if existing_id else None
    return get_asset_service().clean_record(
        incoming,
        existing_id,
        existing=existing,
    )


'''


ASSET_ROUTES = '''@app.get("/api/assets")
@require_auth
def api_assets_list():
    include_inactive = str(
        request.args.get("include_inactive", "true")
    ).strip().lower() not in {"0", "false", "no", "off"}
    result = get_asset_service().list_records(
        include_inactive=include_inactive,
        category=str(request.args.get("category", "")),
        asset_type=str(request.args.get("asset_type", "")),
        rights_status=str(request.args.get("rights_status", "")),
    )
    return jsonify(result.data)


@app.post("/api/assets")
@require_auth
def api_assets_create():
    result = get_asset_service().create(
        request.get_json(silent=True) or {}
    )
    if result.code == "ASSET_NAME_REQUIRED":
        return jsonify({"error": "Asset name is required."}), 400
    return jsonify({"asset": result.data["asset"]})


@app.put("/api/assets/<asset_id>")
@require_auth
def api_assets_update(asset_id: str):
    result = get_asset_service().update(
        asset_id,
        request.get_json(silent=True) or {},
    )
    if result.code == "ASSET_NOT_FOUND":
        return jsonify({"error": "Asset not found."}), 404
    if result.code == "ASSET_NAME_REQUIRED":
        return jsonify({"error": "Asset name is required."}), 400
    return jsonify({"asset": result.data["asset"]})


@app.delete("/api/assets/<asset_id>")
@require_auth
def api_assets_delete(asset_id: str):
    result = get_asset_service().delete(asset_id)
    if result.code == "ASSET_NOT_FOUND":
        return jsonify({"error": "Asset not found."}), 404
    return jsonify({"ok": True})


@app.post("/api/assets/<asset_id>/upload")
@require_auth
def api_asset_upload(asset_id: str):
    upload = request.files.get("asset")
    if not upload or not upload.filename:
        return jsonify({"error": "Choose a file to upload."}), 400
    suffix = Path(upload.filename).suffix.lower()
    if not AssetService.extension_allowed(upload.filename):
        return jsonify({"error": "Unsupported asset file type."}), 400

    duplicate_action = str(
        request.form.get("duplicate_action", "prompt")
    ).lower()
    service = get_asset_service()
    current_result = service.read(asset_id)
    if current_result.code == "ASSET_NOT_FOUND":
        return jsonify({"error": "Save the asset record before uploading."}), 404

    safe_id = AssetService.normalize_id(asset_id)
    temp = ASSET_UPLOAD_DIR / f".upload-{secrets.token_hex(8)}{suffix}"
    upload.save(temp)
    sha256 = service.file_hash(temp)
    duplicate = service.duplicate_by_hash(sha256, exclude_id=asset_id)

    if duplicate and duplicate_action == "prompt":
        temp.unlink(missing_ok=True)
        return jsonify(
            {"error": "DUPLICATE_ASSET", "duplicate_asset": duplicate}
        ), 409

    if duplicate and duplicate_action == "reuse":
        temp.unlink(missing_ok=True)
        result = service.reuse_duplicate(asset_id, str(duplicate.get("id", "")))
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
        target = ASSET_UPLOAD_DIR / existing_name
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

    filename = f"{safe_id}-{int(time.time())}{suffix}"
    target = ASSET_UPLOAD_DIR / filename
    temp.replace(target)
    result = service.attach_file(
        asset_id,
        file_url=f"/asset-files/{filename}",
        sha256=sha256,
        original_filename=upload.filename,
    )
    return jsonify(
        {
            "file_url": result.data["asset"]["file_url"],
            "duplicate_asset": duplicate,
            "duplicate_kept": bool(duplicate),
        }
    )


'''


def replace_between(
    source: str,
    start_marker: str,
    end_marker: str,
    replacement: str,
) -> str:
    start = source.find(start_marker)
    if start < 0:
        raise RuntimeError(f"Start marker not found: {start_marker}")
    end = source.find(end_marker, start)
    if end < 0:
        raise RuntimeError(f"End marker not found: {end_marker}")
    return source[:start] + replacement + source[end:]


def main() -> None:
    source = APP_PATH.read_text(encoding="utf-8")

    import_line = "from asset_service import AssetService\n"
    if import_line not in source:
        personnel_import = "from personnel_service import PersonnelService\n"
        if personnel_import not in source:
            raise RuntimeError("PersonnelService import marker not found")
        source = source.replace(
            personnel_import,
            personnel_import + import_line,
            1,
        )

    if "ASSET_SERVICE: AssetService | None = None" not in source:
        source = replace_between(
            source,
            "def load_assets() -> list[dict[str, Any]]:\n",
            "SPONSOR_REPOSITORY = SponsorRepository(\n",
            ASSET_HELPERS,
        )

    if "return get_asset_service().clean_record(" not in source:
        source = replace_between(
            source,
            "def clean_asset_record(",
            "def load_logos() -> list[dict[str, Any]]:\n",
            CLEAN_ASSET_HELPER,
        )

    if "result = get_asset_service().create(" not in source:
        source = replace_between(
            source,
            '@app.get("/api/assets")\n',
            '@app.get("/asset-files/<filename>")\n',
            ASSET_ROUTES,
        )

    APP_PATH.write_text(source, encoding="utf-8")
    print("Phase 4.10 AssetService integration applied.")


if __name__ == "__main__":
    main()
