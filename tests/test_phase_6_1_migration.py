from __future__ import annotations

from pathlib import Path

from tools.apply_phase_6_1 import (
    apply_app,
    apply_launcher,
    apply_phase5_audit,
)


LEGACY_APP = '''from support_media_service import SupportMediaService
from routes.support_routes import (
    SupportRoutesDependencies,
    create_support_blueprint,
)

BASE_DIR = Path(__file__).resolve().parent
STATE_FILE = BASE_DIR / "state.json"
SECURITY_FILE = BASE_DIR / "security.json"
DATA_DIR = BASE_DIR / "Data"
CONFIG_FILE = DATA_DIR / "Settings" / "config.json"
VERSION_FILE = BASE_DIR / "VERSION.txt"
APPLICATION_BLUEPRINTS = []


def require_auth(view):
    return view


SUPPORT_MEDIA_SERVICE: SupportMediaService | None = None
'''

LEGACY_LAUNCHER = '''@echo off
echo Installing required packages...
echo Starting CSRN Production Suite - Command Center...
".venv\\Scripts\\python.exe" app.py
pause
'''

LEGACY_AUDIT = '''EXPECTED_BLUEPRINTS = {
    "asset_routes",
    "graphics_routes",
    "support_routes",
}
'''


def test_phase_6_1_migration_integrates_service_routes_and_launcher(
    tmp_path: Path,
) -> None:
    app_path = tmp_path / "app.py"
    launcher_path = tmp_path / "RUN_CSRN_COMMAND_CENTER.bat"
    audit_path = tmp_path / "phase5_architecture.py"
    app_path.write_text(LEGACY_APP, encoding="utf-8")
    launcher_path.write_text(LEGACY_LAUNCHER, encoding="utf-8")
    audit_path.write_text(LEGACY_AUDIT, encoding="utf-8")

    assert apply_app(app_path) is True
    assert apply_launcher(launcher_path) is True
    assert apply_phase5_audit(audit_path) is True

    app_source = app_path.read_text(encoding="utf-8")
    assert "from game_day_safety_service import GameDaySafetyService" in app_source
    assert "from routes.game_day_safety_routes import (" in app_source
    assert 'GAME_DAY_BACKUP_DIR = DATA_DIR / "Backups" / "GameDay"' in app_source
    assert "def get_game_day_safety_service()" in app_source
    assert "GAME_DAY_SAFETY_ROUTES_BLUEPRINT = " in app_source
    assert (
        "APPLICATION_BLUEPRINTS.append(GAME_DAY_SAFETY_ROUTES_BLUEPRINT)"
        in app_source
    )

    launcher = launcher_path.read_text(encoding="utf-8")
    assert "tools\\game_day_preflight.py" in launcher
    assert launcher.index("tools\\game_day_preflight.py") < launcher.index("app.py")
    assert "Game-day preflight failed" in launcher

    audit = audit_path.read_text(encoding="utf-8")
    assert audit.count('"game_day_safety_routes"') == 1

    assert apply_app(app_path) is False
    assert apply_launcher(launcher_path) is False
    assert apply_phase5_audit(audit_path) is False
