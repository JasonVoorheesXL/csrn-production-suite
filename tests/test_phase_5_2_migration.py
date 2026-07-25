from __future__ import annotations

from pathlib import Path

from tools.apply_phase_5_2 import apply


LEGACY_APP = '''import time

from routes.system_routes import (
    SystemRoutesDependencies,
    create_system_blueprint,
)


@app.get("/api/security-status")
def security_status():
    return jsonify({})


@app.post("/api/setup-pin")
def setup_pin():
    return jsonify({})


@app.post("/api/login")
def login():
    return jsonify({})


@app.post("/api/logout")
def logout():
    return jsonify({})


@app.get("/api/broadcasters")
@require_auth
def list_broadcasters():
    return jsonify([])


UPGRADE_SERVICE: UpgradeService | None = None


def get_upgrade_service() -> UpgradeService:
    return UPGRADE_SERVICE


@app.get("/api/upgrade/candidate")
def upgrade_candidate():
    return jsonify({})


@app.get("/api/upgrade/status")
def upgrade_status():
    return jsonify({})


@app.post("/api/upgrade/migrate")
def run_upgrade_migration():
    return jsonify({})


@app.get("/api/obs/status")
@require_auth
def obs_status():
    return jsonify({})
'''


def test_phase_5_2_migration_registers_security_upgrade_blueprint(
    tmp_path: Path,
) -> None:
    target = tmp_path / "app.py"
    target.write_text(LEGACY_APP, encoding="utf-8")

    assert apply(target) is True
    migrated = target.read_text(encoding="utf-8")

    assert "from routes.security_upgrade_routes import (" in migrated
    assert "SecurityUpgradeRoutesDependencies" in migrated
    assert (
        "SECURITY_UPGRADE_ROUTES_BLUEPRINT = "
        "create_security_upgrade_blueprint(" in migrated
    )
    assert "app.register_blueprint(SECURITY_UPGRADE_ROUTES_BLUEPRINT)" in migrated
    assert '@app.get("/api/broadcasters")' in migrated
    assert '@app.get("/api/obs/status")' in migrated
    for marker in (
        '@app.get("/api/security-status")',
        '@app.post("/api/setup-pin")',
        '@app.post("/api/login")',
        '@app.post("/api/logout")',
        '@app.get("/api/upgrade/candidate")',
        '@app.get("/api/upgrade/status")',
        '@app.post("/api/upgrade/migrate")',
    ):
        assert marker not in migrated
    assert apply(target) is False
