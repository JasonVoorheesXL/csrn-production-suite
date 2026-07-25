from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_FILE = ROOT / "app.py"


def _replace_block(
    text: str,
    start_marker: str,
    end_marker: str,
    replacement: str,
) -> str:
    start = text.find(start_marker)
    if start < 0:
        raise RuntimeError(f"Missing integration marker: {start_marker!r}")
    end = text.find(end_marker, start)
    if end < 0:
        raise RuntimeError(f"Missing integration marker: {end_marker!r}")
    return text[:start] + replacement + text[end:]


def apply(path: Path = APP_FILE) -> bool:
    text = path.read_text(encoding="utf-8")
    if "SUPPORT_MEDIA_SERVICE: SupportMediaService | None = None" in text:
        return False

    import_marker = "from game_operations_service import GameOperationsService\n"
    if import_marker not in text:
        raise RuntimeError("GameOperationsService import marker was not found.")
    text = text.replace(
        import_marker,
        import_marker + "from support_media_service import SupportMediaService\n",
        1,
    )

    headshot_routes = '''SUPPORT_MEDIA_SERVICE: SupportMediaService | None = None


def get_support_media_service() -> SupportMediaService:
    global SUPPORT_MEDIA_SERVICE
    if SUPPORT_MEDIA_SERVICE is None:
        SUPPORT_MEDIA_SERVICE = SupportMediaService(
            headshots_dir=HEADSHOTS_DIR,
            load_rosters=load_rosters,
            save_rosters=save_rosters,
        )
    return SUPPORT_MEDIA_SERVICE


@app.get("/roster-headshots/<filename>")
def roster_headshot_file(filename: str):
    return send_from_directory(HEADSHOTS_DIR, filename)


@app.post("/api/rosters/<roster_id>/players/<player_id>/headshot")
@require_auth
def upload_player_headshot(roster_id: str, player_id: str):
    upload = request.files.get("headshot")
    if not upload or not upload.filename:
        return jsonify({"error": "HEADSHOT_FILE_REQUIRED"}), 400
    result = get_support_media_service().upload_headshot(
        roster_id,
        player_id,
        original_filename=upload.filename,
        raw=upload.read(),
    )
    if result.code in {
        "HEADSHOT_FILE_REQUIRED",
        "UNSUPPORTED_IMAGE_TYPE",
        "INVALID_IMAGE",
        "IMAGE_TOO_SMALL",
    }:
        return jsonify({"error": result.code}), 400
    if result.code in {"ROSTER_NOT_FOUND", "PLAYER_NOT_FOUND"}:
        return jsonify({"error": result.code}), 404
    if result.code == "HEADSHOT_STORAGE_FAILED":
        return jsonify(
            {
                "error": result.code,
                "message": result.data.get("message", ""),
            }
        ), 500
    return jsonify(
        {
            "headshot": result.data["headshot"],
            "player": result.data["player"],
        }
    )


'''
    text = _replace_block(
        text,
        '@app.get("/roster-headshots/<filename>")\n',
        "def activate_primary_graphic(state: dict[str, Any], active: str) -> None:\n",
        headshot_routes,
    )

    address_helper = '''def local_addresses() -> list[str]:
    return get_support_media_service().local_addresses()


'''
    text = _replace_block(
        text,
        "def local_addresses() -> list[str]:\n",
        '@app.get("/api/statistics")\n',
        address_helper,
    )

    connection_routes = '''@app.get("/api/connection-info")
@require_auth
def connection_info():
    result = get_support_media_service().connection_info(5050)
    return jsonify(result.data["connection"])


@app.get("/api/connection-qr")
@require_auth
def connection_qr():
    result = get_support_media_service().qr_svg(
        request.args.get("url", "")
    )
    if result.code == "INVALID_URL":
        return jsonify({"error": result.code}), 400
    if result.code == "QR_GENERATION_FAILED":
        return jsonify(
            {
                "error": result.code,
                "message": result.data.get("message", ""),
            }
        ), 500
    return Response(
        result.data["svg"],
        mimetype=result.data["mimetype"],
        headers=result.data["headers"],
    )


'''
    text = _replace_block(
        text,
        '@app.get("/api/connection-info")\n',
        '@app.post("/api/toggle-scorebug")\n',
        connection_routes,
    )

    local_ip_helper = '''def local_ip() -> str:
    return SupportMediaService.local_ip()


'''
    text = _replace_block(
        text,
        "def local_ip() -> str:\n",
        'if __name__ == "__main__":\n',
        local_ip_helper,
    )

    path.write_text(text, encoding="utf-8")
    return True


def main() -> None:
    changed = apply()
    if changed:
        print("Phase 4.22 SupportMediaService integration applied.")
    else:
        print("Phase 4.22 SupportMediaService integration was already present.")


if __name__ == "__main__":
    main()
