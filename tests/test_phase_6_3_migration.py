from __future__ import annotations

from pathlib import Path

from tools.apply_phase_6_3 import apply_app, apply_phase5_audit


APP_SOURCE = '''from recovery_service import RecoveryService
from routes.recovery_routes import (
    RecoveryRoutesDependencies,
    create_recovery_blueprint,
)
GAME_DAY_RECOVERY_DIR = DATA_DIR / "Backups" / "Recovery"

SUPPORT_MEDIA_SERVICE: SupportMediaService | None = None
'''

AUDIT_SOURCE = '''EXPECTED_BLUEPRINTS = {
    "broadcast_routes",
    "recovery_routes",
}
'''


def test_apply_app_adds_commissioning_composition(tmp_path: Path) -> None:
    path = tmp_path / "app.py"
    path.write_text(APP_SOURCE, encoding="utf-8")
    assert apply_app(path) is True
    text = path.read_text(encoding="utf-8")
    assert "from commissioning_service import HardwareOBSCommissioningService" in text
    assert "create_commissioning_blueprint" in text
    assert "COMMISSIONING_FILE = " in text
    assert "def get_commissioning_service()" in text
    assert "APPLICATION_BLUEPRINTS.append(COMMISSIONING_ROUTES_BLUEPRINT)" in text


def test_apply_app_is_idempotent(tmp_path: Path) -> None:
    path = tmp_path / "app.py"
    path.write_text(APP_SOURCE, encoding="utf-8")
    assert apply_app(path) is True
    first = path.read_text(encoding="utf-8")
    assert apply_app(path) is False
    assert path.read_text(encoding="utf-8") == first


def test_apply_phase5_audit_adds_commissioning_blueprint(tmp_path: Path) -> None:
    path = tmp_path / "phase5_architecture.py"
    path.write_text(AUDIT_SOURCE, encoding="utf-8")
    assert apply_phase5_audit(path) is True
    text = path.read_text(encoding="utf-8")
    assert '    "commissioning_routes",\n' in text
    assert apply_phase5_audit(path) is False
