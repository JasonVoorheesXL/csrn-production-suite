from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_FILE = ROOT / "app.py"


def apply(path: Path = APP_FILE) -> bool:
    text = path.read_text(encoding="utf-8")
    if "UPGRADE_SERVICE: UpgradeService | None = None" in text:
        return False

    import_marker = "from diagnostics_service import DiagnosticsService\n"
    if import_marker not in text:
        raise RuntimeError("DiagnosticsService import marker was not found.")
    text = text.replace(
        import_marker,
        import_marker + "from upgrade_service import UpgradeService\n",
        1,
    )

    route_start = '@app.get("/api/upgrade/candidate")\n'
    route_end = '@app.get("/api/obs/status")\n'
    start = text.find(route_start)
    end = text.find(route_end, start)
    if start < 0 or end < 0:
        raise RuntimeError("Upgrade route integration markers were not found.")

    replacement = '''UPGRADE_SERVICE: UpgradeService | None = None


def activate_upgrade_secret_key(secret_key: str) -> None:
    app.secret_key = secret_key


def get_upgrade_service() -> UpgradeService:
    global UPGRADE_SERVICE
    if UPGRADE_SERVICE is None:
        UPGRADE_SERVICE = UpgradeService(
            current_dir=BASE_DIR,
            defaults=DEFAULT_CONFIG,
            inspect_candidate=inspect_candidate,
            migrate=migrate,
            load_security=load_security,
            activate_secret_key=activate_upgrade_secret_key,
            report_store=last_upgrade_report,
            migration_lock=upgrade_lock,
        )
    return UPGRADE_SERVICE


@app.get("/api/upgrade/candidate")
def upgrade_candidate():
    result = get_upgrade_service().candidate()
    if result.code == "INSPECTION_FAILED":
        return jsonify(
            {
                "error": result.code,
                "message": result.data.get("message", ""),
            }
        ), 500
    return jsonify(result.data["candidate"])


@app.get("/api/upgrade/status")
def upgrade_status():
    result = get_upgrade_service().status()
    return jsonify(result.data["report"])


@app.post("/api/upgrade/migrate")
def run_upgrade_migration():
    incoming = request.get_json(silent=True) or {}
    result = get_upgrade_service().run(
        incoming.get("include_security", True)
    )
    return jsonify(result.data["report"])


'''
    text = text[:start] + replacement + text[end:]
    path.write_text(text, encoding="utf-8")
    return True


def main() -> None:
    changed = apply()
    if changed:
        print("Phase 4.17 UpgradeService integration applied.")
    else:
        print("Phase 4.17 UpgradeService integration was already present.")


if __name__ == "__main__":
    main()
