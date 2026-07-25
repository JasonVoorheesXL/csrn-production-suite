from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_FILE = ROOT / "app.py"


ROUTE_IMPORT = (
    "from routes.system_routes import (\n"
    "    SystemRoutesDependencies,\n"
    "    create_system_blueprint,\n"
    ")\n"
)

ROUTE_REGISTRATION = '''SYSTEM_ROUTES_BLUEPRINT = create_system_blueprint(
    SystemRoutesDependencies(
        require_auth=require_auth,
        get_configuration_service=get_configuration_service,
        diagnostic_status=diagnostic_status,
        load_state=load_state,
        public_state=public_state,
        readiness_payload=readiness_payload,
        load_build_journal=load_build_journal,
    )
)
app.register_blueprint(SYSTEM_ROUTES_BLUEPRINT)


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
    if "SYSTEM_ROUTES_BLUEPRINT = create_system_blueprint(" in text:
        return False

    import_marker = (
        "from broadcast_lifecycle_service import BroadcastLifecycleService\n"
    )
    if import_marker not in text:
        raise RuntimeError("BroadcastLifecycleService import marker was not found.")
    text = text.replace(import_marker, import_marker + ROUTE_IMPORT, 1)

    text = _remove_until(
        text,
        '@app.get("/api/config")\n',
        "def update_linked_broadcast_status(\n",
    )

    text = _remove_until(
        text,
        '@app.get("/api/readiness")\n',
        "BROADCAST_LIFECYCLE_SERVICE: BroadcastLifecycleService | None = None\n",
    )
    lifecycle_marker = (
        "BROADCAST_LIFECYCLE_SERVICE: BroadcastLifecycleService | None = None\n"
    )
    text = text.replace(
        lifecycle_marker,
        ROUTE_REGISTRATION + lifecycle_marker,
        1,
    )

    text = _remove_until(
        text,
        '@app.get("/api/build-journal")\n',
        "GAME_OPERATIONS_SERVICE: GameOperationsService | None = None\n",
    )

    path.write_text(text, encoding="utf-8")
    return True


def main() -> None:
    changed = apply()
    if changed:
        print("Phase 5.1 system-routes Blueprint integration applied.")
    else:
        print("Phase 5.1 system-routes Blueprint integration was already present.")


if __name__ == "__main__":
    main()
