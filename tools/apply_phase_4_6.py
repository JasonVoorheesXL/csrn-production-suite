from __future__ import annotations

from pathlib import Path


APP_PATH = Path("app.py")


SPONSOR_HELPERS = '''SPONSOR_REPOSITORY = SponsorRepository(
    CORE_PERSISTENCE,
    SPONSORS_FILE,
)


def load_sponsors() -> list[dict[str, Any]]:
    ensure_data_architecture()
    return SPONSOR_REPOSITORY.load()


def save_sponsors(items: list[dict[str, Any]]) -> None:
    ensure_data_architecture()
    SPONSOR_REPOSITORY.save(items)


SPONSOR_SERVICE: SponsorService | None = None


def get_sponsor_service() -> SponsorService:
    global SPONSOR_SERVICE

    if SPONSOR_SERVICE is None:
        SPONSOR_SERVICE = SponsorService(
            load_sponsors=load_sponsors,
            save_sponsors=save_sponsors,
            load_assets=load_assets,
        )

    return SPONSOR_SERVICE


def sponsor_logo_assets() -> list[dict[str, Any]]:
    return get_sponsor_service().logo_assets()


def sponsor_contract_state(record: dict[str, Any]) -> str:
    return get_sponsor_service().contract_state(record)


def clean_sponsor_record(
    data: dict[str, Any],
    sponsor_id: str | None = None,
) -> dict[str, Any]:
    return get_sponsor_service().clean_record(data, sponsor_id)


def active_sponsor_by_id(sponsor_id: str) -> dict[str, Any] | None:
    return get_sponsor_service().active_sponsor_by_id(sponsor_id)


def apply_sponsor_to_graphic(
    graphic: dict[str, Any],
    incoming: dict[str, Any],
) -> str:
    result = get_sponsor_service().apply_to_graphic(graphic, incoming)
    graphic.clear()
    graphic.update(result.data["graphic"])
    return str(result.data.get("warning", ""))


'''


SPONSOR_ROUTES = '''@app.get("/api/sponsors")
@require_auth
def api_sponsors_list():
    return jsonify(get_sponsor_service().list_payload())


@app.post("/api/sponsors")
@require_auth
def api_sponsors_create():
    result = get_sponsor_service().create(
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


@app.put("/api/sponsors/<sponsor_id>")
@require_auth
def api_sponsors_update(sponsor_id: str):
    result = get_sponsor_service().update(
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


@app.delete("/api/sponsors/<sponsor_id>")
@require_auth
def api_sponsors_delete(sponsor_id: str):
    result = get_sponsor_service().delete(sponsor_id)
    if result.code == "SPONSOR_NOT_FOUND":
        return jsonify({"error": "Sponsor not found."}), 404
    return jsonify({"ok": True})


@app.post("/api/sponsors/<sponsor_id>/logo")
@require_auth
def api_sponsor_logo(sponsor_id: str):
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
            for item in load_sponsors()
            if str(item.get("id")) == sponsor_id
        ),
        None,
    )
    if not sponsor:
        return jsonify({"error": "Save the sponsor first."}), 404

    ASSET_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    temp = ASSET_UPLOAD_DIR / f".upload-{secrets.token_hex(8)}{suffix}"
    upload.save(temp)
    sha256 = asset_file_hash(temp)
    assets = load_assets()
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
            ASSET_UPLOAD_DIR / current_name
            if current_name
            else ASSET_UPLOAD_DIR / f"{existing['id']}{suffix}"
        )
        temp.replace(target)
        existing.update(
            {
                "file_url": f"/asset-files/{target.name}",
                "sha256": sha256,
                "original_filename": upload.filename,
                "updated_at": int(time.time()),
            }
        )
        save_assets(assets)
        asset = existing
    else:
        asset_id = f"asset-{int(time.time()*1000)}-{secrets.token_hex(2)}"
        filename = f"{asset_id}{suffix}"
        target = ASSET_UPLOAD_DIR / filename
        temp.replace(target)
        asset = clean_asset_record(
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
        save_assets(assets)

    result = get_sponsor_service().link_asset(
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


@app.put("/api/sponsors/<sponsor_id>/asset")
@require_auth
def api_sponsor_asset_link(sponsor_id: str):
    asset_id = str(
        (request.get_json(silent=True) or {}).get("asset_id", "")
    ).strip()
    result = get_sponsor_service().link_asset(sponsor_id, asset_id)
    if result.code == "INVALID_SPONSOR_LOGO_ASSET":
        return jsonify(
            {"error": "Choose a valid Sponsor Logo asset."}
        ), 400
    if result.code == "SPONSOR_NOT_FOUND":
        return jsonify({"error": "Sponsor not found."}), 404
    return jsonify(result.data)


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

    import_line = "from sponsor_service import SponsorService\n"
    if import_line not in source:
        roster_import = "from roster_service import RosterService\n"
        if roster_import not in source:
            raise RuntimeError("RosterService import marker not found")
        source = source.replace(
            roster_import,
            roster_import + import_line,
            1,
        )

    if "SPONSOR_SERVICE: SponsorService | None = None" not in source:
        source = replace_between(
            source,
            "def sponsor_logo_assets() -> list[dict[str, Any]]:\n",
            "def clean_asset_record(",
            SPONSOR_HELPERS,
        )

    if "return jsonify(get_sponsor_service().list_payload())" not in source:
        source = replace_between(
            source,
            '@app.get("/api/sponsors")\n',
            '@app.get("/sponsor-logos/<filename>")\n',
            SPONSOR_ROUTES,
        )

    APP_PATH.write_text(source, encoding="utf-8")
    print("Phase 4.6 SponsorService integration applied.")


if __name__ == "__main__":
    main()
