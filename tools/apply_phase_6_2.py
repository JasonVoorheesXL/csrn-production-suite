from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_FILE = ROOT / "app.py"
LAUNCHER_FILE = ROOT / "RUN_CSRN_COMMAND_CENTER.bat"
PHASE5_ARCHITECTURE_FILE = ROOT / "phase5_architecture.py"


SERVICE_IMPORT = "from recovery_service import RecoveryService\n"
ROUTE_IMPORT = '''from routes.recovery_routes import (
    RecoveryRoutesDependencies,
    create_recovery_blueprint,
)
'''
CONSTANT = 'GAME_DAY_RECOVERY_DIR = DATA_DIR / "Backups" / "Recovery"\n'

SERVICE_AND_ROUTES = '''RECOVERY_SERVICE: RecoveryService | None = None


def get_recovery_service() -> RecoveryService:
    global RECOVERY_SERVICE
    if RECOVERY_SERVICE is None:
        RECOVERY_SERVICE = RecoveryService(
            safety_service=get_game_day_safety_service(),
            data_dir=DATA_DIR,
            backup_root=GAME_DAY_BACKUP_DIR,
            recovery_root=GAME_DAY_RECOVERY_DIR,
            state_file=STATE_FILE,
            security_file=SECURITY_FILE,
            version_file=VERSION_FILE,
            load_state=load_state,
            clock=time.time,
            transaction_lock=lock,
        )
    return RECOVERY_SERVICE


RECOVERY_ROUTES_BLUEPRINT = create_recovery_blueprint(
    RecoveryRoutesDependencies(
        require_auth=require_auth,
        get_recovery_service=lambda: get_recovery_service(),
    )
)
APPLICATION_BLUEPRINTS.append(RECOVERY_ROUTES_BLUEPRINT)


'''

LAUNCHER_BLOCK = '''echo Recording game-day application startup...
".venv\\Scripts\\python.exe" tools\\game_day_recovery.py startup
if errorlevel 1 (
  echo.
  echo Recovery startup tracking failed. The application was not started.
  pause
  exit /b 1
)

echo.
echo Starting CSRN Production Suite - Command Center...
".venv\\Scripts\\python.exe" app.py
set "CSRN_EXIT=%ERRORLEVEL%"
if "%CSRN_EXIT%"=="0" (
  echo Recording clean application shutdown...
  ".venv\\Scripts\\python.exe" tools\\game_day_recovery.py shutdown
) else (
  echo.
  echo WARNING: CSRN ended unexpectedly. The recovery marker was retained.
)
pause
exit /b %CSRN_EXIT%
'''


def apply_app(path: Path = APP_FILE) -> bool:
    text = path.read_text(encoding="utf-8")
    if "RECOVERY_ROUTES_BLUEPRINT = " in text:
        return False

    service_marker = "from game_day_safety_service import GameDaySafetyService\n"
    if service_marker not in text:
        raise RuntimeError("GameDaySafetyService import marker was not found.")
    text = text.replace(service_marker, service_marker + SERVICE_IMPORT, 1)

    route_marker = '''from routes.game_day_safety_routes import (
    GameDaySafetyRoutesDependencies,
    create_game_day_safety_blueprint,
)
'''
    if route_marker not in text:
        raise RuntimeError("Game-day safety route import marker was not found.")
    text = text.replace(route_marker, route_marker + ROUTE_IMPORT, 1)

    constant_marker = 'GAME_DAY_BACKUP_DIR = DATA_DIR / "Backups" / "GameDay"\n'
    if constant_marker not in text:
        raise RuntimeError("Game-day backup constant marker was not found.")
    text = text.replace(constant_marker, constant_marker + CONSTANT, 1)

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
    if "tools\\game_day_recovery.py startup" in text:
        return False
    marker = '''echo.
echo Starting CSRN Production Suite - Command Center...
".venv\\Scripts\\python.exe" app.py
pause
'''
    if marker not in text:
        raise RuntimeError("Launcher application-start marker was not found.")
    text = text.replace(marker, LAUNCHER_BLOCK, 1)
    path.write_text(text, encoding="utf-8")
    return True


def apply_phase5_audit(path: Path = PHASE5_ARCHITECTURE_FILE) -> bool:
    text = path.read_text(encoding="utf-8")
    if '    "recovery_routes",\n' in text:
        return False
    marker = '    "roster_routes",\n'
    if marker not in text:
        raise RuntimeError("Phase 5 Blueprint audit marker was not found.")
    text = text.replace(marker, '    "recovery_routes",\n' + marker, 1)
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
        print("Phase 6.2 recovery and rollback integration applied.")
    else:
        print("Phase 6.2 recovery and rollback integration was already present.")


if __name__ == "__main__":
    main()
