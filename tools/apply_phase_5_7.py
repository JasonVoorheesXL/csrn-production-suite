from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_FILE = ROOT / "app.py"


ROUTE_IMPORTS = '''from routes.graphics_routes import (
    GraphicsRoutesDependencies,
    create_graphics_blueprint,
)
from routes.obs_routes import (
    OBSRoutesDependencies,
    create_obs_blueprint,
)
'''

OBS_REGISTRATION = '''OBS_ROUTES_BLUEPRINT = create_obs_blueprint(
    OBSRoutesDependencies(
        require_auth=require_auth,
        get_obs_service=lambda: get_obs_service(),
    )
)
app.register_blueprint(OBS_ROUTES_BLUEPRINT)


'''

GRAPHICS_REGISTRATION = '''GRAPHICS_ROUTES_BLUEPRINT = create_graphics_blueprint(
    GraphicsRoutesDependencies(
        require_auth=require_auth,
        get_graphics_service=lambda: get_graphics_service(),
        load_state=lambda: load_state(),
        save_state=lambda state: save_state(state),
        public_state=lambda state: public_state(state),
        transaction_lock=lock,
    )
)
app.register_blueprint(GRAPHICS_ROUTES_BLUEPRINT)


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
        "OBS_ROUTES_BLUEPRINT = create_obs_blueprint(" in text
        and "GRAPHICS_ROUTES_BLUEPRINT = create_graphics_blueprint(" in text
    ):
        return False

    import_marker = '''from routes.broadcast_routes import (
    BroadcastRoutesDependencies,
    create_broadcast_blueprint,
)
'''
    if import_marker not in text:
        raise RuntimeError("Broadcast route import marker was not found.")
    text = text.replace(import_marker, import_marker + ROUTE_IMPORTS, 1)

    text = _remove_until(
        text,
        '@app.get("/api/obs/status")\n',
        "def command_scorebug_visibility(visible: bool) -> dict[str, Any]:\n",
    )
    command_marker = "def command_scorebug_visibility(visible: bool) -> dict[str, Any]:\n"
    text = text.replace(
        command_marker,
        OBS_REGISTRATION + command_marker,
        1,
    )

    text = _remove_until(
        text,
        '@app.post("/api/obs/scorebug-visibility")\n',
        "def update_linked_broadcast_status(\n",
    )

    text = _remove_until(
        text,
        '@app.post("/api/graphics/lower-third")\n',
        "def automation_player(roster_id: str, player_id: str):\n",
    )
    automation_marker = "def automation_player(roster_id: str, player_id: str):\n"
    text = text.replace(
        automation_marker,
        GRAPHICS_REGISTRATION + automation_marker,
        1,
    )

    path.write_text(text, encoding="utf-8")
    return True


def main() -> None:
    changed = apply()
    if changed:
        print("Phase 5.7 graphics and OBS route integration applied.")
    else:
        print("Phase 5.7 route integration was already present.")


if __name__ == "__main__":
    main()
