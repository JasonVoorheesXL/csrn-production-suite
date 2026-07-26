from __future__ import annotations

from pathlib import Path

from tools.apply_phase_6_2 import apply_app, apply_launcher, apply_phase5_audit


def test_phase_6_2_migration_applies_and_is_idempotent(tmp_path: Path) -> None:
    app_file = tmp_path / "app.py"
    app_file.write_text(
        '''from game_day_safety_service import GameDaySafetyService
from routes.game_day_safety_routes import (
    GameDaySafetyRoutesDependencies,
    create_game_day_safety_blueprint,
)
GAME_DAY_BACKUP_DIR = DATA_DIR / "Backups" / "GameDay"
SUPPORT_MEDIA_SERVICE: SupportMediaService | None = None
''',
        encoding="utf-8",
    )
    launcher = tmp_path / "RUN_CSRN_COMMAND_CENTER.bat"
    launcher.write_text(
        '''echo.
echo Starting CSRN Production Suite - Command Center...
".venv\\Scripts\\python.exe" app.py
pause
''',
        encoding="utf-8",
    )
    audit = tmp_path / "phase5_architecture.py"
    audit.write_text('    "roster_routes",\n', encoding="utf-8")

    assert apply_app(app_file) is True
    assert apply_launcher(launcher) is True
    assert apply_phase5_audit(audit) is True
    assert apply_app(app_file) is False
    assert apply_launcher(launcher) is False
    assert apply_phase5_audit(audit) is False

    app_text = app_file.read_text(encoding="utf-8")
    assert "def get_recovery_service()" in app_text
    assert "APPLICATION_BLUEPRINTS.append(RECOVERY_ROUTES_BLUEPRINT)" in app_text
    assert "tools\\game_day_recovery.py startup" in launcher.read_text(encoding="utf-8")
    assert '"recovery_routes"' in audit.read_text(encoding="utf-8")
