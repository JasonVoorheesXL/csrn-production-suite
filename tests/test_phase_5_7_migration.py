from __future__ import annotations

from pathlib import Path

from tools.apply_phase_5_7 import apply


LEGACY_APP = '''from routes.broadcast_routes import (
    BroadcastRoutesDependencies,
    create_broadcast_blueprint,
)


def get_obs_service():
    return service


@app.get("/api/obs/status")
@require_auth
def obs_status():
    return jsonify({})


@app.post("/api/obs/test")
@require_auth
def test_obs_connection():
    return jsonify({})


def command_scorebug_visibility(visible: bool) -> dict[str, Any]:
    return {}


@app.post("/api/obs/scorebug-visibility")
@require_auth
def obs_scorebug_visibility():
    return jsonify({})


@app.post("/api/obs/program-visual-mode")
@require_auth
def obs_program_visual_mode():
    return jsonify({})


def update_linked_broadcast_status(
    broadcast_id: str,
    status: str,
    extra: dict[str, Any] | None = None,
) -> None:
    pass


def activate_primary_graphic(state: dict[str, Any], active: str) -> None:
    pass


@app.post("/api/graphics/lower-third")
@require_auth
def update_lower_third():
    return jsonify({})


@app.post("/api/graphics/player")
@require_auth
def update_player_graphic():
    return jsonify({})


@app.post("/api/graphics/personnel")
@require_auth
def update_personnel_graphic():
    return jsonify({})


def automation_player(roster_id: str, player_id: str):
    return None, None
'''


def test_phase_5_7_migration_registers_graphics_and_obs_blueprints(
    tmp_path: Path,
) -> None:
    target = tmp_path / "app.py"
    target.write_text(LEGACY_APP, encoding="utf-8")

    assert apply(target) is True
    migrated = target.read_text(encoding="utf-8")

    assert "from routes.graphics_routes import (" in migrated
    assert "from routes.obs_routes import (" in migrated
    assert "OBS_ROUTES_BLUEPRINT = create_obs_blueprint(" in migrated
    assert "app.register_blueprint(OBS_ROUTES_BLUEPRINT)" in migrated
    assert "GRAPHICS_ROUTES_BLUEPRINT = create_graphics_blueprint(" in migrated
    assert "app.register_blueprint(GRAPHICS_ROUTES_BLUEPRINT)" in migrated
    assert "def command_scorebug_visibility(" in migrated
    assert "def update_linked_broadcast_status(" in migrated
    assert "def automation_player(" in migrated
    for marker in (
        '@app.get("/api/obs/status")',
        '@app.post("/api/obs/test")',
        '@app.post("/api/obs/scorebug-visibility")',
        '@app.post("/api/obs/program-visual-mode")',
        '@app.post("/api/graphics/lower-third")',
        '@app.post("/api/graphics/player")',
        '@app.post("/api/graphics/personnel")',
    ):
        assert marker not in migrated
    assert apply(target) is False
