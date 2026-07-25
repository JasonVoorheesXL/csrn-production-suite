from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_FILE = ROOT / "app.py"


ROUTE_IMPORT = '''from routes.security_upgrade_routes import (
    SecurityUpgradeRoutesDependencies,
    create_security_upgrade_blueprint,
)
'''

ROUTE_REGISTRATION = '''SECURITY_UPGRADE_ROUTES_BLUEPRINT = create_security_upgrade_blueprint(
    SecurityUpgradeRoutesDependencies(
        get_security_service=lambda: SECURITY_SERVICE,
        load_security=load_security,
        authenticated=authenticated,
        clock=time.time,
        get_upgrade_service=get_upgrade_service,
    )
)
app.register_blueprint(SECURITY_UPGRADE_ROUTES_BLUEPRINT)


'''


def _remove_until(text: str, start_marker: str, end_marker: str) -> str:
    start = text.find(start_marker)
    if start < 0:
        raise RuntimeError(f"Missing route migration marker: {start_marker!r}")
    end = text.find(end_marker, start)
    if end < 0:
        raise RuntimeError(f"Missing route migration marker: {end_marker!r}")
    return text[:start] + text[end:]


def apply(path: Path = APP_FILE) -> bool:
    text = path.read_text(encoding="utf-8")
    if "SECURITY_UPGRADE_ROUTES_BLUEPRINT = create_security_upgrade_blueprint(" in text:
        return False

    import_marker = '''from routes.system_routes import (
    SystemRoutesDependencies,
    create_system_blueprint,
)
'''
    if import_marker not in text:
        raise RuntimeError("System-routes import marker was not found.")
    text = text.replace(import_marker, import_marker + ROUTE_IMPORT, 1)

    text = _remove_until(
        text,
        '@app.get("/api/security-status")\n',
        '@app.get("/api/broadcasters")\n',
    )

    text = _remove_until(
        text,
        '@app.get("/api/upgrade/candidate")\n',
        '@app.get("/api/obs/status")\n',
    )
    obs_marker = '@app.get("/api/obs/status")\n'
    text = text.replace(obs_marker, ROUTE_REGISTRATION + obs_marker, 1)

    path.write_text(text, encoding="utf-8")
    return True


def main() -> None:
    changed = apply()
    if changed:
        print("Phase 5.2 security and upgrade Blueprint integration applied.")
    else:
        print("Phase 5.2 security and upgrade Blueprint integration was already present.")


if __name__ == "__main__":
    main()
