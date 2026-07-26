from __future__ import annotations

from pathlib import Path

import pytest

from tools.apply_phase_6_4 import MigrationError, apply


APP_FIXTURE = '''from commissioning_service import HardwareOBSCommissioningService
from routes.commissioning_routes import (
    CommissioningRoutesDependencies,
    create_commissioning_blueprint,
)
COMMISSIONING_FILE = DATA_DIR / "Settings" / "hardware_commissioning.json"
COMMISSIONING_ROUTES_BLUEPRINT = create_commissioning_blueprint(
    CommissioningRoutesDependencies(
        require_auth=require_auth,
        get_commissioning_service=lambda: get_commissioning_service(),
    )
)
APPLICATION_BLUEPRINTS.append(COMMISSIONING_ROUTES_BLUEPRINT)
'''

ARCHITECTURE_FIXTURE = '''EXPECTED_BLUEPRINTS = {
    "broadcast_routes",
    "commissioning_routes",
}
PUBLIC_ENDPOINTS = {
    "asset_routes.asset_file",
}
'''


def write_fixture(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text(APP_FIXTURE, encoding="utf-8")
    (tmp_path / "phase5_architecture.py").write_text(
        ARCHITECTURE_FIXTURE,
        encoding="utf-8",
    )


def test_apply_adds_caption_composition_and_audit(tmp_path: Path) -> None:
    write_fixture(tmp_path)
    apply(tmp_path)
    app_text = (tmp_path / "app.py").read_text(encoding="utf-8")
    audit_text = (tmp_path / "phase5_architecture.py").read_text(encoding="utf-8")
    assert "from caption_service import CaptionService" in app_text
    assert "def get_caption_service()" in app_text
    assert "APPLICATION_BLUEPRINTS.append(CAPTION_ROUTES_BLUEPRINT)" in app_text
    assert '"caption_routes"' in audit_text
    assert '"caption_routes.caption_overlay_state"' in audit_text


def test_apply_is_idempotent(tmp_path: Path) -> None:
    write_fixture(tmp_path)
    apply(tmp_path)
    first = (tmp_path / "app.py").read_text(encoding="utf-8")
    apply(tmp_path)
    assert (tmp_path / "app.py").read_text(encoding="utf-8") == first


def test_apply_fails_when_anchor_is_missing(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("", encoding="utf-8")
    (tmp_path / "phase5_architecture.py").write_text(
        ARCHITECTURE_FIXTURE,
        encoding="utf-8",
    )
    with pytest.raises(MigrationError):
        apply(tmp_path)
