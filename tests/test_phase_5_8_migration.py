from __future__ import annotations

from pathlib import Path

from tools.apply_phase_5_8 import apply


LEGACY_APP = '''from routes.obs_routes import (
    OBSRoutesDependencies,
    create_obs_blueprint,
)


def get_game_operations_service():
    return game


@app.post("/api/score")
@require_auth
def update_score():
    return jsonify({})


@app.post("/api/set")
@require_auth
def set_value():
    return jsonify({})


SUPPORT_MEDIA_SERVICE: SupportMediaService | None = None


def get_statistics_service():
    return statistics


@app.get("/api/statistics")
@require_auth
def statistics_report():
    return jsonify({})


EVENT_SERVICE: EventService | None = None


def get_event_service():
    return events


@app.post("/api/control-source")
@require_auth
def set_control_source():
    return jsonify({})


@app.post("/api/event-trigger")
@require_auth
def event_trigger():
    return jsonify({})


@app.post("/api/game-correction")
@require_auth
def game_correction():
    return jsonify({})


@app.post("/api/events/<event_id>/edit")
@require_auth
def edit_event(event_id: str):
    return jsonify({})


@app.get("/api/corrections")
@require_auth
def corrections_report():
    return jsonify([])


@app.get("/api/connection-info")
@require_auth
def connection_info():
    return jsonify({})


@app.post("/api/toggle-scorebug")
@require_auth
def toggle_scorebug():
    return jsonify({})


@app.post("/api/toggle-halftime")
@require_auth
def toggle_halftime():
    return jsonify({})


@app.post("/api/end-game")
@require_auth
def end_game():
    return jsonify({})


@app.post("/api/reset-data")
@require_auth
def reset_data():
    return jsonify({})


@app.post("/api/new-broadcast")
@require_auth
def new_broadcast():
    return jsonify({})


def spot_to_coord(value: Any) -> int:
    return 0


def get_rules_service():
    return rules


@app.post("/api/clock-control")
@require_auth
def clock_control():
    return jsonify({})


@app.post("/api/field-direction")
@require_auth
def field_direction():
    return jsonify({})


@app.post("/api/rules-play")
@require_auth
def rules_play():
    return jsonify({})


@app.post("/api/undo")
@require_auth
def undo():
    return jsonify({})


def local_ip() -> str:
    return "127.0.0.1"
'''


def test_phase_5_8_migration_registers_live_game_blueprint(
    tmp_path: Path,
) -> None:
    target = tmp_path / "app.py"
    target.write_text(LEGACY_APP, encoding="utf-8")

    assert apply(target) is True
    migrated = target.read_text(encoding="utf-8")

    assert "from routes.live_game_routes import (" in migrated
    assert "LIVE_GAME_ROUTES_BLUEPRINT = create_live_game_blueprint(" in migrated
    assert "app.register_blueprint(LIVE_GAME_ROUTES_BLUEPRINT)" in migrated
    assert "SUPPORT_MEDIA_SERVICE: SupportMediaService | None = None" in migrated
    assert "EVENT_SERVICE: EventService | None = None" in migrated
    assert '@app.get("/api/connection-info")' in migrated
    assert "def spot_to_coord(" in migrated
    assert "def local_ip()" in migrated
    for marker in (
        '@app.post("/api/score")',
        '@app.post("/api/set")',
        '@app.get("/api/statistics")',
        '@app.post("/api/control-source")',
        '@app.post("/api/event-trigger")',
        '@app.post("/api/game-correction")',
        '@app.post("/api/events/<event_id>/edit")',
        '@app.get("/api/corrections")',
        '@app.post("/api/toggle-scorebug")',
        '@app.post("/api/toggle-halftime")',
        '@app.post("/api/end-game")',
        '@app.post("/api/reset-data")',
        '@app.post("/api/new-broadcast")',
        '@app.post("/api/clock-control")',
        '@app.post("/api/field-direction")',
        '@app.post("/api/rules-play")',
        '@app.post("/api/undo")',
    ):
        assert marker not in migrated
    assert apply(target) is False
