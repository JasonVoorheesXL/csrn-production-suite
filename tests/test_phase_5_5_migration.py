from __future__ import annotations

from pathlib import Path

from tools.apply_phase_5_5 import apply


LEGACY_APP = '''from routes.venue_routes import (
    VenueRoutesDependencies,
    create_venue_blueprint,
)


@app.get("/api/sponsors")
@require_auth
def api_sponsors_list():
    return jsonify([])


@app.get("/api/assets")
@require_auth
def api_assets_list():
    return jsonify([])


@app.get("/asset-files/<filename>")
def asset_file(filename: str):
    return send_from_directory(ASSET_UPLOAD_DIR, filename)


@app.get("/overlay")
def overlay():
    return render_template("overlay.html")


def _hex(rgb):
    return LogoService._hex(rgb)


@app.get("/school-logos/<school_id>/<filename>")
def school_logo_file(school_id: str, filename: str):
    return send_from_directory(DATA_DIR, filename)


@app.post("/api/schools/<school_id>/logo/process")
@require_auth
def process_school_logo(school_id: str):
    return jsonify({})


@app.get("/api/logos")
@require_auth
def list_logos():
    return jsonify([])


UPGRADE_SERVICE: UpgradeService | None = None
'''


def test_phase_5_5_migration_registers_media_blueprints(
    tmp_path: Path,
) -> None:
    target = tmp_path / "app.py"
    target.write_text(LEGACY_APP, encoding="utf-8")

    assert apply(target) is True
    migrated = target.read_text(encoding="utf-8")

    assert "from routes.asset_routes import (" in migrated
    assert "from routes.logo_routes import (" in migrated
    assert "from routes.sponsor_routes import (" in migrated
    assert "SPONSOR_ROUTES_BLUEPRINT = create_sponsor_blueprint(" in migrated
    assert "ASSET_ROUTES_BLUEPRINT = create_asset_blueprint(" in migrated
    assert "LOGO_ROUTES_BLUEPRINT = create_logo_blueprint(" in migrated
    assert "app.register_blueprint(SPONSOR_ROUTES_BLUEPRINT)" in migrated
    assert "app.register_blueprint(ASSET_ROUTES_BLUEPRINT)" in migrated
    assert "app.register_blueprint(LOGO_ROUTES_BLUEPRINT)" in migrated
    assert '@app.get("/overlay")' in migrated
    assert "def _hex(rgb):" in migrated
    assert '@app.get("/api/sponsors")' not in migrated
    assert '@app.get("/api/assets")' not in migrated
    assert '@app.get("/asset-files/<filename>")' not in migrated
    assert '@app.get("/school-logos/<school_id>/<filename>")' not in migrated
    assert '@app.post("/api/schools/<school_id>/logo/process")' not in migrated
    assert '@app.get("/api/logos")' not in migrated
    assert apply(target) is False
