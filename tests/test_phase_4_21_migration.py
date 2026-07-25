from __future__ import annotations

from pathlib import Path

from tools.apply_phase_4_21 import apply


LEGACY_APP = '''from statistics_service import StatisticsService


@app.post("/api/score")
@require_auth
def update_score():
    data = request.get_json(force=True)
    team = data.get("team")
    delta = int(data.get("delta", 0))
    with lock:
        state = load_state()
        state["home_score"] = delta
        save_state(state)
    return jsonify(state)


@app.post("/api/set")
@require_auth
def set_value():
    return jsonify(apply_change(request.get_json(force=True) or {}))


@app.get("/roster-headshots/<filename>")
def roster_headshot_file(filename: str):
    return filename


@app.post("/api/toggle-scorebug")
@require_auth
def toggle_scorebug():
    state = load_state()
    state["scorebug_visible"] = not state.get("scorebug_visible")
    save_state(state)
    return jsonify(state)


@app.post("/api/toggle-halftime")
@require_auth
def toggle_halftime():
    return jsonify(load_state())


@app.post("/api/end-game")
@require_auth
def end_game():
    return jsonify(load_state())


@app.post("/api/reset-data")
@require_auth
def reset_data():
    return jsonify(DEFAULT_STATE)


@app.post("/api/new-broadcast")
@require_auth
def new_broadcast():
    return jsonify(DEFAULT_STATE)


def spot_to_coord(value: Any) -> int:
    return 50
'''


def test_phase_4_21_migration_integrates_game_operations_service(
    tmp_path: Path,
) -> None:
    target = tmp_path / "app.py"
    target.write_text(LEGACY_APP, encoding="utf-8")

    assert apply(target) is True
    migrated = target.read_text(encoding="utf-8")

    assert "from game_operations_service import GameOperationsService" in migrated
    assert "GAME_OPERATIONS_SERVICE: GameOperationsService | None = None" in migrated
    assert "get_game_operations_service().score" in migrated
    assert "get_game_operations_service().set_values" in migrated
    assert "get_game_operations_service().toggle_scorebug" in migrated
    assert "get_game_operations_service().toggle_halftime" in migrated
    assert "get_game_operations_service().end_game" in migrated
    assert "get_game_operations_service().reset_data" in migrated
    assert "get_game_operations_service().new_broadcast" in migrated
    assert 'delta = int(data.get("delta", 0))' not in migrated
    assert 'state["scorebug_visible"] = not state.get("scorebug_visible")' not in migrated
    assert apply(target) is False
