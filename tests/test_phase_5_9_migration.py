from __future__ import annotations

from pathlib import Path

from tools.apply_phase_5_9 import apply


LEGACY_APP = '''from routes.live_game_routes import (
    LiveGameRoutesDependencies,
    create_live_game_blueprint,
)


@app.get("/")
def control_panel():
    return render_template("index.html")


BROADCAST_PACKAGE_ROUTES_BLUEPRINT = create_broadcast_package_blueprint(
    BroadcastPackageRoutesDependencies()
)


@app.get("/overlay")
def overlay():
    return render_template("overlay.html")


PERSONNEL_ROUTES_BLUEPRINT = create_personnel_blueprint(
    PersonnelRoutesDependencies()
)


def get_support_media_service():
    return service


@app.get("/roster-headshots/<filename>")
def roster_headshot_file(filename: str):
    return send_from_directory(HEADSHOTS_DIR, filename)


@app.post("/api/rosters/<roster_id>/players/<player_id>/headshot")
@require_auth
def upload_player_headshot(roster_id: str, player_id: str):
    return jsonify({})


def activate_primary_graphic(state: dict[str, Any], active: str) -> None:
    pass


@app.get("/api/connection-info")
@require_auth
def connection_info():
    return jsonify({})


@app.get("/api/connection-qr")
@require_auth
def connection_qr():
    return Response("")


def spot_to_coord(value: Any) -> int:
    return 0
'''


def test_phase_5_9_migration_registers_support_and_page_blueprints(
    tmp_path: Path,
) -> None:
    target = tmp_path / "app.py"
    target.write_text(LEGACY_APP, encoding="utf-8")

    assert apply(target) is True
    migrated = target.read_text(encoding="utf-8")

    assert "from routes.page_routes import (" in migrated
    assert "from routes.support_routes import (" in migrated
    assert "PAGE_ROUTES_BLUEPRINT = create_page_blueprint(" in migrated
    assert "app.register_blueprint(PAGE_ROUTES_BLUEPRINT)" in migrated
    assert "SUPPORT_ROUTES_BLUEPRINT = create_support_blueprint(" in migrated
    assert "app.register_blueprint(SUPPORT_ROUTES_BLUEPRINT)" in migrated
    assert "BROADCAST_PACKAGE_ROUTES_BLUEPRINT" in migrated
    assert "PERSONNEL_ROUTES_BLUEPRINT" in migrated
    assert "def activate_primary_graphic(" in migrated
    assert "def spot_to_coord(" in migrated
    for marker in (
        '@app.get("/")',
        '@app.get("/overlay")',
        '@app.get("/roster-headshots/<filename>")',
        '@app.post("/api/rosters/<roster_id>/players/<player_id>/headshot")',
        '@app.get("/api/connection-info")',
        '@app.get("/api/connection-qr")',
    ):
        assert marker not in migrated
    assert apply(target) is False
