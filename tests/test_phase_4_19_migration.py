from __future__ import annotations

from pathlib import Path

from tools.apply_phase_4_19 import apply


LEGACY_APP = '''from event_service import EventService


def spot_to_coord(value: Any) -> int:
    return 50


def coord_to_spot(coord: int) -> str:
    return "50"


def team_direction(state: dict[str, Any], team: str) -> int:
    return 1


def opposite(team: str) -> str:
    return "visitor"


def advance_down(down: str) -> str:
    return "2nd"


@app.post("/api/clock-control")
@require_auth
def clock_control():
    data=request.get_json(force=True) or {}
    state=load_state(); action=str(data.get("action","")).lower()
    return jsonify(state)


@app.post("/api/field-direction")
@require_auth
def field_direction():
    return jsonify(load_state())


@app.post("/api/rules-play")
@require_auth
def rules_play():
    return jsonify({"state": load_state(), "play": {}})


@app.post("/api/undo")
@require_auth
def undo():
    return jsonify({})
'''


def test_phase_4_19_migration_integrates_rules_service(tmp_path: Path) -> None:
    target = tmp_path / "app.py"
    target.write_text(LEGACY_APP, encoding="utf-8")

    assert apply(target) is True
    migrated = target.read_text(encoding="utf-8")

    assert "from rules_service import RulesService" in migrated
    assert "RULES_SERVICE: RulesService | None = None" in migrated
    assert "get_rules_service().clock_control" in migrated
    assert "get_rules_service().field_direction" in migrated
    assert "get_rules_service().play" in migrated
    assert 'state=load_state(); action=str(data.get("action","")).lower()' not in migrated
    assert apply(target) is False
