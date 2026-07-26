from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_FILE = ROOT / "app.py"


ROUTE_IMPORTS = '''from routes.page_routes import (
    PageRoutesDependencies,
    create_page_blueprint,
)
from routes.support_routes import (
    SupportRoutesDependencies,
    create_support_blueprint,
)
'''

PAGE_REGISTRATION = '''PAGE_ROUTES_BLUEPRINT = create_page_blueprint(
    PageRoutesDependencies(
        application_identity=lambda: application_identity(),
    )
)
app.register_blueprint(PAGE_ROUTES_BLUEPRINT)


'''

SUPPORT_REGISTRATION = '''SUPPORT_ROUTES_BLUEPRINT = create_support_blueprint(
    SupportRoutesDependencies(
        require_auth=require_auth,
        get_support_media_service=lambda: get_support_media_service(),
        get_headshots_dir=lambda: HEADSHOTS_DIR,
        connection_port=5050,
    )
)
app.register_blueprint(SUPPORT_ROUTES_BLUEPRINT)


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
    if (
        "PAGE_ROUTES_BLUEPRINT = create_page_blueprint(" in text
        and "SUPPORT_ROUTES_BLUEPRINT = create_support_blueprint(" in text
    ):
        return False

    import_marker = '''from routes.live_game_routes import (
    LiveGameRoutesDependencies,
    create_live_game_blueprint,
)
'''
    if import_marker not in text:
        raise RuntimeError("Live-game route import marker was not found.")
    text = text.replace(import_marker, import_marker + ROUTE_IMPORTS, 1)

    text = _remove_until(
        text,
        '@app.get("/")\n',
        "BROADCAST_PACKAGE_ROUTES_BLUEPRINT = create_broadcast_package_blueprint(\n",
    )
    package_marker = (
        "BROADCAST_PACKAGE_ROUTES_BLUEPRINT = create_broadcast_package_blueprint(\n"
    )
    text = text.replace(package_marker, PAGE_REGISTRATION + package_marker, 1)

    text = _remove_until(
        text,
        '@app.get("/overlay")\n',
        "PERSONNEL_ROUTES_BLUEPRINT = create_personnel_blueprint(\n",
    )

    text = _remove_until(
        text,
        '@app.get("/roster-headshots/<filename>")\n',
        "def activate_primary_graphic(state: dict[str, Any], active: str) -> None:\n",
    )
    graphic_marker = (
        "def activate_primary_graphic(state: dict[str, Any], active: str) -> None:\n"
    )
    text = text.replace(
        graphic_marker,
        SUPPORT_REGISTRATION + graphic_marker,
        1,
    )

    text = _remove_until(
        text,
        '@app.get("/api/connection-info")\n',
        "def spot_to_coord(value: Any) -> int:\n",
    )

    path.write_text(text, encoding="utf-8")
    return True


def main() -> None:
    changed = apply()
    if changed:
        print("Phase 5.9 support and page route integration applied.")
    else:
        print("Phase 5.9 route integration was already present.")


if __name__ == "__main__":
    main()
