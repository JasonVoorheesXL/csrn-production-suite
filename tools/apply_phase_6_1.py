from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_FILE = ROOT / "app.py"
LAUNCHER_FILE = ROOT / "RUN_CSRN_COMMAND_CENTER.bat"
PHASE5_ARCHITECTURE_FILE = ROOT / "phase5_architecture.py"


SERVICE_IMPORT = "from game_day_safety_service import GameDaySafetyService\n"
ROUTE_IMPORT = '''from routes.game_day_safety_routes import (
    GameDaySafetyRoutesDependencies,
    create_game_day_safety_blueprint,
)
'''
CONSTANT = 'GAME_DAY_BACKUP_DIR = DATA_DIR / "Backups" / "GameDay"\n'

SERVICE_AND_ROUTES = '''GAME_DAY_SAFETY_SERVICE: GameDaySafetyService | None = None


def get_game_day_safety_service() -> GameDaySafetyService:
    global GAME_DAY_SAFETY_SERVICE
    if GAME_DAY_SAFETY_SERVICE is None:
        GAME_DAY_SAFETY_SERVICE = GameDaySafetyService(
            base_dir=BASE_DIR,
            data_dir=DATA_DIR,
            backup_root=GAME_DAY_BACKUP_DIR,
            state_file=STATE_FILE,
            security_file=SECURITY_FILE,
            config_file=CONFIG_FILE,
            version_file=VERSION_FILE,
            clock=time.time,
        )
    return GAME_DAY_SAFETY_SERVICE


GAME_DAY_SAFETY_ROUTES_BLUEPRINT = create_game_day_safety_blueprint(
    GameDaySafetyRoutesDependencies(
        require_auth=require_auth,
        get_safety_service=lambda: get_game_day_safety_service(),
    )
)
APPLICATION_BLUEPRINTS.append(GAME_DAY_SAFETY_ROUTES_BLUEPRINT)


'''

LAUNCHER_PREFLIGHT = '''echo Running game-day storage preflight and safety snapshot...
".venv\\Scripts\\python.exe" tools\\game_day_preflight.py
if errorlevel 1 (
  echo.
  echo Game-day preflight failed. The application was not started.
  echo Correct the reported storage or data problem and run this launcher again.
  pause
  exit /b 1
)

echo.
'''


def apply_app(path: Path = APP_FILE) -> bool:
    text = path.read_text(encoding="utf-8")
    if "GAME_DAY_SAFETY_ROUTES_BLUEPRINT = " in text:
        return False

    service_marker = "from support_media_service import SupportMediaService\n"
    if service_marker not in text:
        raise RuntimeError("SupportMediaService import marker was not found.")
    text = text.replace(
        service_marker,
        service_marker + SERVICE_IMPORT,
        1,
    )

    route_marker = '''from routes.support_routes import (
    SupportRoutesDependencies,
    create_support_blueprint,
)
'''
    if route_marker not in text:
        raise RuntimeError("Support route import marker was not found.")
    text = text.replace(route_marker, route_marker + ROUTE_IMPORT, 1)

    constant_marker = "VERSION_FILE = BASE_DIR / \"VERSION.txt\"\n"
    if constant_marker not in text:
        raise RuntimeError("VERSION_FILE marker was not found.")
    text = text.replace(
        constant_marker,
        constant_marker + CONSTANT,
        1,
    )

    registration_marker = "SUPPORT_MEDIA_SERVICE: SupportMediaService | None = None\n"
    if registration_marker not in text:
        raise RuntimeError("Support-media service marker was not found.")
    text = text.replace(
        registration_marker,
        SERVICE_AND_ROUTES + registration_marker,
        1,
    )

    path.write_text(text, encoding="utf-8")
    return True


def apply_launcher(path: Path = LAUNCHER_FILE) -> bool:
    text = path.read_text(encoding="utf-8")
    if "tools\\game_day_preflight.py" in text:
        return False
    marker = "echo Starting CSRN Production Suite - Command Center...\n"
    if marker not in text:
        raise RuntimeError("Launcher startup marker was not found.")
    text = text.replace(marker, LAUNCHER_PREFLIGHT + marker, 1)
    path.write_text(text, encoding="utf-8")
    return True


def apply_phase5_audit(path: Path = PHASE5_ARCHITECTURE_FILE) -> bool:
    text = path.read_text(encoding="utf-8")
    if '    "game_day_safety_routes",\n' in text:
        return False
    marker = '    "graphics_routes",\n'
    if marker not in text:
        raise RuntimeError("Phase 5 Blueprint audit marker was not found.")
    text = text.replace(
        marker,
        marker + '    "game_day_safety_routes",\n',
        1,
    )
    path.write_text(text, encoding="utf-8")
    return True


def apply() -> bool:
    changed = False
    changed = apply_app() or changed
    changed = apply_launcher() or changed
    changed = apply_phase5_audit() or changed
    return changed


def main() -> None:
    if apply():
        print("Phase 6.1 game-day safety integration applied.")
    else:
        print("Phase 6.1 game-day safety integration was already present.")


if __name__ == "__main__":
    main()
