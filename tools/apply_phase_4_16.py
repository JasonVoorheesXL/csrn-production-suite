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
    if "DIAGNOSTICS_SERVICE: DiagnosticsService | None = None" in text:
        return False

    import_marker = "from state_service import StateService\n"
    if import_marker not in text:
        raise RuntimeError("StateService import marker was not found.")
    text = text.replace(
        import_marker,
        import_marker + "from diagnostics_service import DiagnosticsService\n",
        1,
    )

    diagnostics_block = '''DIAGNOSTICS_SERVICE: DiagnosticsService | None = None


def get_diagnostics_service() -> DiagnosticsService:
    global DIAGNOSTICS_SERVICE
    if DIAGNOSTICS_SERVICE is None:
        DIAGNOSTICS_SERVICE = DiagnosticsService(
            base_dir=BASE_DIR,
            data_dir=DATA_DIR,
            config_file=CONFIG_FILE,
            schools_file=SCHOOLS_FILE,
            broadcasters_file=BROADCASTERS_FILE,
            rosters_file=ROSTERS_FILE,
            venues_file=VENUES_FILE,
            logos_file=LOGOS_FILE,
            packages_file=PACKAGES_FILE,
            assets_file=ASSETS_FILE,
            sponsors_file=SPONSORS_FILE,
            load_config=load_config,
            load_state=load_state,
            public_state=public_state,
            load_obs_status=load_obs_status,
            authenticated=authenticated,
            migrate_venues=migrate_venue_names,
        )
    return DIAGNOSTICS_SERVICE


def diagnostic_status() -> dict[str, Any]:
    return get_diagnostics_service().diagnostics().data["diagnostics"]


'''
    text = _replace_block(
        text,
        "def diagnostic_status() -> dict[str, Any]:\n",
        "def normalize_school_id(value: str) -> str:\n",
        diagnostics_block,
    )

    readiness_block = '''def readiness_payload() -> dict[str, Any]:
    return get_diagnostics_service().readiness().data["readiness"]


'''
    text = _replace_block(
        text,
        "def readiness_payload() -> dict[str, Any]:\n",
        '@app.get("/api/readiness")\n',
        readiness_block,
    )

    old_route = '''def readiness():
    migrate_venue_names()
    return jsonify(readiness_payload())
'''
    new_route = '''def readiness():
    return jsonify(readiness_payload())
'''
    if old_route not in text:
        raise RuntimeError("Readiness route marker was not found.")
    text = text.replace(old_route, new_route, 1)

    path.write_text(text, encoding="utf-8")
    return True


def main() -> None:
    changed = apply()
    if changed:
        print("Phase 4.16 DiagnosticsService integration applied.")
    else:
        print("Phase 4.16 DiagnosticsService integration was already present.")


if __name__ == "__main__":
    main()
