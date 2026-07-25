from __future__ import annotations

from pathlib import Path


APP_PATH = Path("app.py")


PERSONNEL_SERVICE_HELPERS = '''PERSONNEL_SERVICE: PersonnelService | None = None


def get_personnel_service() -> PersonnelService:
    global PERSONNEL_SERVICE

    if PERSONNEL_SERVICE is None:
        PERSONNEL_SERVICE = PersonnelService(
            load_personnel=load_broadcasters,
            save_personnel=save_broadcasters,
        )

    return PERSONNEL_SERVICE


'''


BROADCASTER_ROUTES = '''@app.get("/api/broadcasters")
@require_auth
def list_broadcasters():
    include_inactive = str(
        request.args.get("include_inactive", "true")
    ).strip().lower() not in {"0", "false", "no", "off"}
    result = get_personnel_service().list_records(
        include_inactive=include_inactive,
        category=str(request.args.get("category", "")),
        role=str(request.args.get("role", "")),
        school_id=str(request.args.get("school_id", "")),
    )
    return jsonify(result.data["personnel"])


@app.post("/api/broadcasters")
@require_auth
def create_broadcaster():
    result = get_personnel_service().create(
        request.get_json(force=True) or {}
    )
    if result.code in {"STAFF_NAME_REQUIRED", "INVALID_STAFF_ROLE"}:
        return jsonify({"error": result.code}), 400
    if result.code == "INVALID_SOCIAL_URL":
        return jsonify({"error": result.code, **result.data}), 400
    return jsonify(result.data["personnel"]), 201


@app.put("/api/broadcasters/<broadcaster_id>")
@require_auth
def update_broadcaster(broadcaster_id: str):
    result = get_personnel_service().update(
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


@app.delete("/api/broadcasters/<broadcaster_id>")
@require_auth
def delete_broadcaster(broadcaster_id: str):
    result = get_personnel_service().delete(broadcaster_id)
    if result.code == "BROADCASTER_NOT_FOUND":
        return jsonify({"error": result.code}), 404
    return jsonify({"ok": True})


'''


HEADSHOT_ROUTES = '''@app.get("/personnel-headshots/<filename>")
def personnel_headshot_file(filename: str):
    return send_from_directory(PERSONNEL_HEADSHOTS_DIR, filename)


@app.post("/api/personnel/<personnel_id>/headshot")
@require_auth
def upload_personnel_headshot(personnel_id: str):
    file = request.files.get("file")
    if not file or not file.filename:
        return jsonify({"error": "FILE_REQUIRED"}), 400
    ext = Path(file.filename).suffix.lower()
    if ext not in {".png", ".jpg", ".jpeg", ".webp"}:
        return jsonify({"error": "UNSUPPORTED_IMAGE"}), 400
    PERSONNEL_HEADSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    target = PERSONNEL_HEADSHOTS_DIR / (
        f"{PersonnelService.normalize_id(personnel_id)}{ext}"
    )
    file.save(target)
    relative = "/personnel-headshots/" + target.name
    result = get_personnel_service().attach_headshot(
        personnel_id,
        relative,
    )
    if result.code == "PERSONNEL_NOT_FOUND":
        target.unlink(missing_ok=True)
        return jsonify({"error": result.code}), 404
    return jsonify({"path": result.data["path"]})


@app.post("/api/validate-social")
@require_auth
def validate_social():
    incoming = request.get_json(force=True) or {}
    result = get_personnel_service().validate_social(
        str(incoming.get("platform", "")),
        str(incoming.get("value", "")),
    )
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

    import_line = "from personnel_service import PersonnelService\n"
    if import_line not in source:
        broadcast_import = "from broadcast_service import BroadcastService\n"
        if broadcast_import not in source:
            raise RuntimeError("BroadcastService import marker not found")
        source = source.replace(
            broadcast_import,
            broadcast_import + import_line,
            1,
        )

    if "PERSONNEL_SERVICE: PersonnelService | None = None" not in source:
        marker = "    return normalized, errors\n\n\ndef normalize_state("
        if marker not in source:
            raise RuntimeError("Social-normalizer insertion marker not found")
        source = source.replace(
            marker,
            "    return normalized, errors\n\n\n"
            + PERSONNEL_SERVICE_HELPERS
            + "def normalize_state(",
            1,
        )

    if "result = get_personnel_service().create(" not in source:
        source = replace_between(
            source,
            '@app.get("/api/broadcasters")\n',
            '@app.get("/personnel-headshots/<filename>")\n',
            BROADCASTER_ROUTES,
        )

    if "get_personnel_service().attach_headshot(" not in source:
        source = replace_between(
            source,
            '@app.get("/personnel-headshots/<filename>")\n',
            '@app.get("/api/rosters")\n',
            HEADSHOT_ROUTES,
        )

    APP_PATH.write_text(source, encoding="utf-8")
    print("Phase 4.9 PersonnelService integration applied.")


if __name__ == "__main__":
    main()
