from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_FILE = ROOT / "app.py"


ROUTE_IMPORTS = '''from routes.broadcast_lifecycle_routes import (
    BroadcastLifecycleRoutesDependencies,
    create_broadcast_lifecycle_blueprint,
)
from routes.broadcast_package_routes import (
    BroadcastPackageRoutesDependencies,
    create_broadcast_package_blueprint,
)
from routes.broadcast_routes import (
    BroadcastRoutesDependencies,
    create_broadcast_blueprint,
)
'''

PACKAGE_REGISTRATION = '''BROADCAST_PACKAGE_ROUTES_BLUEPRINT = create_broadcast_package_blueprint(
    BroadcastPackageRoutesDependencies(
        require_auth=require_auth,
        get_package_service=get_broadcast_package_service,
        public_state=lambda state: public_state(state),
    )
)
app.register_blueprint(BROADCAST_PACKAGE_ROUTES_BLUEPRINT)


'''

BROADCAST_REGISTRATION = '''BROADCAST_LIFECYCLE_ROUTES_BLUEPRINT = create_broadcast_lifecycle_blueprint(
    BroadcastLifecycleRoutesDependencies(
        require_auth=require_auth,
        get_lifecycle_service=get_broadcast_lifecycle_service,
    )
)
app.register_blueprint(BROADCAST_LIFECYCLE_ROUTES_BLUEPRINT)

BROADCAST_ROUTES_BLUEPRINT = create_broadcast_blueprint(
    BroadcastRoutesDependencies(
        require_auth=require_auth,
        get_broadcast_service=get_broadcast_service,
    )
)
app.register_blueprint(BROADCAST_ROUTES_BLUEPRINT)


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
    if "BROADCAST_PACKAGE_ROUTES_BLUEPRINT = create_broadcast_package_blueprint(" in text:
        return False

    import_marker = '''from routes.sponsor_routes import (
    SponsorRoutesDependencies,
    create_sponsor_blueprint,
)
'''
    if import_marker not in text:
        raise RuntimeError("Sponsor route import marker was not found.")
    text = text.replace(import_marker, import_marker + ROUTE_IMPORTS, 1)

    text = _remove_until(
        text,
        '@app.get("/api/packages")\n',
        "SPONSOR_ROUTES_BLUEPRINT = create_sponsor_blueprint(\n",
    )
    sponsor_marker = "SPONSOR_ROUTES_BLUEPRINT = create_sponsor_blueprint(\n"
    text = text.replace(
        sponsor_marker,
        PACKAGE_REGISTRATION + sponsor_marker,
        1,
    )

    text = _remove_until(
        text,
        '@app.post("/api/broadcasts/<broadcast_id>/load")\n',
        "GAME_OPERATIONS_SERVICE: GameOperationsService | None = None\n",
    )
    game_marker = "GAME_OPERATIONS_SERVICE: GameOperationsService | None = None\n"
    text = text.replace(
        game_marker,
        BROADCAST_REGISTRATION + game_marker,
        1,
    )

    path.write_text(text, encoding="utf-8")
    return True


def main() -> None:
    changed = apply()
    if changed:
        print("Phase 5.6 broadcast package and lifecycle route integration applied.")
    else:
        print("Phase 5.6 route integration was already present.")


if __name__ == "__main__":
    main()
