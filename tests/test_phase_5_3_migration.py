from __future__ import annotations

from pathlib import Path

from tools.apply_phase_5_3 import apply


LEGACY_APP = '''from routes.security_upgrade_routes import (
    SecurityUpgradeRoutesDependencies,
    create_security_upgrade_blueprint,
)


def roster_boundary() -> None:
    pass


@app.get("/api/schools")
@require_auth
def list_schools():
    return jsonify(get_school_service().list_schools())


@app.post("/api/schools")
@require_auth
def create_school():
    return jsonify({})


def _association_error_status(code: str) -> int:
    return 400


@app.get("/api/imports/associations/profiles")
@require_auth
def list_association_profiles():
    return jsonify({})


@app.post("/api/imports/associations/preview")
@require_auth
def preview_association_import():
    return jsonify({})


@app.post("/api/imports/mhsaa/5A")
@require_auth
def import_mhsaa_5a():
    return jsonify({})


def _hex(rgb: tuple[int, int, int]) -> str:
    return "#000000"
'''


def test_phase_5_3_migration_registers_school_and_association_blueprints(
    tmp_path: Path,
) -> None:
    target = tmp_path / "app.py"
    target.write_text(LEGACY_APP, encoding="utf-8")

    assert apply(target) is True
    migrated = target.read_text(encoding="utf-8")

    assert "from routes.school_routes import (" in migrated
    assert "from routes.association_routes import (" in migrated
    assert "SCHOOL_ROUTES_BLUEPRINT = create_school_blueprint(" in migrated
    assert "ASSOCIATION_ROUTES_BLUEPRINT = create_association_blueprint(" in migrated
    assert "app.register_blueprint(SCHOOL_ROUTES_BLUEPRINT)" in migrated
    assert "app.register_blueprint(ASSOCIATION_ROUTES_BLUEPRINT)" in migrated
    assert "get_school_service=get_school_service" in migrated
    assert "get_profile_service=get_association_profile_service" in migrated
    assert "load_mhsaa_manifest=lambda: load_json(" in migrated
    assert "def roster_boundary()" in migrated
    assert "def _hex(rgb: tuple[int, int, int])" in migrated
    assert '@app.get("/api/schools")' not in migrated
    assert '@app.get("/api/imports/associations/profiles")' not in migrated
    assert '@app.post("/api/imports/mhsaa/5A")' not in migrated
    assert "def _association_error_status(" not in migrated
    assert apply(target) is False
