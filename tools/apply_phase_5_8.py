from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_FILE = ROOT / "app.py"


ROUTE_IMPORT = '''from routes.live_game_routes import (
    LiveGameRoutesDependencies,
    create_live_game_blueprint,
)
'''

ROUTE_REGISTRATION = '''LIVE_GAME_ROUTES_BLUEPRINT = create_live_game_blueprint(
    LiveGameRoutesDependencies(
        require_auth=require_auth,
        get_game_operations_service=lambda: get_game_operations_service(),
        get_event_service=lambda: get_event_service(),
        get_rules_service=lambda: get_rules_service(),
        get_statistics_service=lambda: get_statistics_service(),
        load_state=lambda: load_state(),
    )
)
app.register_blueprint(LIVE_GAME_ROUTES_BLUEPRINT)


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
    if "LIVE_GAME_ROUTES_BLUEPRINT = create_live_game_blueprint(" in text:
        return False

    import_marker = '''from routes.obs_routes import (
    OBSRoutesDependencies,
    create_obs_blueprint,
)
'''
    if import_marker not in text:
        raise RuntimeError("OBS route import marker was not found.")
    text = text.replace(import_marker, import_marker + ROUTE_IMPORT, 1)

    text = _remove_until(
        text,
        '@app.post("/api/score")\n',
        "SUPPORT_MEDIA_SERVICE: SupportMediaService | None = None\n",
    )
    support_marker = "SUPPORT_MEDIA_SERVICE: SupportMediaService | None = None\n"
    text = text.replace(
        support_marker,
        ROUTE_REGISTRATION + support_marker,
        1,
    )

    text = _remove_until(
        text,
        '@app.get("/api/statistics")\n',
        "EVENT_SERVICE: EventService | None = None\n",
    )

    text = _remove_until(
        text,
        '@app.post("/api/control-source")\n',
        '@app.get("/api/connection-info")\n',
    )

    text = _remove_until(
        text,
        '@app.post("/api/toggle-scorebug")\n',
        "def spot_to_coord(value: Any) -> int:\n",
    )

    text = _remove_until(
        text,
        '@app.post("/api/clock-control")\n',
        "def local_ip() -> str:\n",
    )

    path.write_text(text, encoding="utf-8")
    return True


def main() -> None:
    changed = apply()
    if changed:
        print("Phase 5.8 live-game route integration applied.")
    else:
        print("Phase 5.8 live-game route integration was already present.")


if __name__ == "__main__":
    main()
