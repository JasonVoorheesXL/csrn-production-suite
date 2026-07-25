from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "app.py"


class MigrationError(RuntimeError):
    pass


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise MigrationError(f"Expected one {label} marker, found {count}.")
    return text.replace(old, new, 1)


def replace_between(
    text: str,
    start: str,
    end: str,
    replacement: str,
    label: str,
) -> str:
    start_index = text.find(start)
    if start_index < 0:
        raise MigrationError(f"Missing {label} start marker.")
    end_index = text.find(end, start_index)
    if end_index < 0:
        raise MigrationError(f"Missing {label} end marker.")
    return text[:start_index] + replacement + text[end_index:]


def main() -> None:
    text = APP_PATH.read_text(encoding="utf-8")
    if "from logo_service import LogoService" in text:
        print("Phase 4.12 LogoService integration already applied.")
        return

    text = replace_once(
        text,
        "from graphics_service import GraphicsService\n",
        "from graphics_service import GraphicsService\n"
        "from logo_service import LogoService\n",
        "LogoService import",
    )

    text = replace_once(
        text,
        "def save_logos(items: list[dict[str, Any]]) -> None:\n"
        "    save_json(LOGOS_FILE, items)\n\n",
        "def save_logos(items: list[dict[str, Any]]) -> None:\n"
        "    save_json(LOGOS_FILE, items)\n\n\n"
        "LOGO_SERVICE: LogoService | None = None\n\n\n"
        "def get_logo_service() -> LogoService:\n"
        "    global LOGO_SERVICE\n"
        "    if LOGO_SERVICE is None:\n"
        "        LOGO_SERVICE = LogoService(\n"
        "            load_schools=load_schools,\n"
        "            save_schools=save_schools,\n"
        "            load_logos=load_logos,\n"
        "            save_logos=save_logos,\n"
        "            normalize_school_id=normalize_school_id,\n"
        "        )\n"
        "    return LOGO_SERVICE\n\n",
        "LogoService factory",
    )

    helper_replacement = '''def _hex(rgb: tuple[int, int, int]) -> str:\n    return LogoService._hex(rgb)\n\n\ndef extract_logo_colors(image: Image.Image) -> list[str]:\n    return LogoService.extract_colors(image)\n\n\ndef normalize_round_logo(source: Image.Image, size: int) -> Image.Image:\n    return LogoService.normalize_round_logo(source, size)\n\n\n'''
    text = replace_between(
        text,
        "def _hex(rgb: tuple[int, int, int]) -> str:\n",
        '@app.get("/school-logos/<school_id>/<filename>")',
        helper_replacement,
        "legacy logo helpers",
    )

    process_replacement = '''@app.post("/api/schools/<school_id>/logo/process")\n@require_auth\ndef process_school_logo(school_id: str):\n    upload = request.files.get("logo")\n    if not upload or not upload.filename:\n        return jsonify({"error": "LOGO_FILE_REQUIRED"}), 400\n\n    raw = upload.read()\n    normalized_school_id = normalize_school_id(school_id)\n    folder = DATA_DIR / "Logos" / normalized_school_id\n\n    def write_original(extension: str, payload: bytes) -> str:\n        folder.mkdir(parents=True, exist_ok=True)\n        path = folder / f"original{extension}"\n        path.write_bytes(payload)\n        return str(path.relative_to(BASE_DIR)).replace("\\\\", "/")\n\n    def write_master(image: Image.Image) -> str:\n        folder.mkdir(parents=True, exist_ok=True)\n        path = folder / "round-master.png"\n        image.save(path)\n        return f"/school-logos/{normalized_school_id}/round-master.png"\n\n    def write_scorebug(image: Image.Image) -> str:\n        folder.mkdir(parents=True, exist_ok=True)\n        path = folder / "round-scorebug.png"\n        image.save(path)\n        return f"/school-logos/{normalized_school_id}/round-scorebug.png"\n\n    result = get_logo_service().process_candidate(\n        school_id,\n        raw=raw,\n        original_filename=upload.filename,\n        write_original=write_original,\n        write_master=write_master,\n        write_scorebug=write_scorebug,\n    )\n    if result.code == "SCHOOL_NOT_FOUND":\n        return jsonify({"error": result.code}), 404\n    if result.code == "INVALID_IMAGE":\n        return jsonify({"error": result.code}), 400\n    if result.code == "LOGO_STORAGE_FAILED":\n        return jsonify(\n            {\n                "error": result.code,\n                "message": result.data.get("message", ""),\n            }\n        ), 500\n    return jsonify(result.data)\n'''
    text = replace_between(
        text,
        '@app.post("/api/schools/<school_id>/logo/process")',
        '\n\n@app.get("/api/venues")',
        process_replacement,
        "school logo route",
    )

    text = replace_once(
        text,
        '@app.get("/api/logos")\n'
        '@require_auth\n'
        'def list_logos():\n'
        '    return jsonify(load_logos())\n',
        '@app.get("/api/logos")\n'
        '@require_auth\n'
        'def list_logos():\n'
        '    result = get_logo_service().list_records(\n'
        '        school_id=str(request.args.get("school_id", "")),\n'
        '        designation=str(request.args.get("designation", "")),\n'
        '        approval_status=str(request.args.get("approval_status", "")),\n'
        '    )\n'
        '    return jsonify(result.data["logos"])\n',
        "logo list route",
    )

    APP_PATH.write_text(text, encoding="utf-8")
    print("Phase 4.12 LogoService integration applied.")


if __name__ == "__main__":
    try:
        main()
    except MigrationError as exc:
        raise SystemExit(f"ERROR: {exc}") from exc
