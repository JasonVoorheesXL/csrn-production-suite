from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_FILE = ROOT / "app.py"


def _replace_block(
    text: str,
    start_marker: str,
    end_marker: str,
    replacement: str,
) -> str:
    start = text.find(start_marker)
    if start < 0:
        raise RuntimeError(f"Missing integration marker: {start_marker!r}")
    end = text.find(end_marker, start)
    if end < 0:
        raise RuntimeError(f"Missing integration marker: {end_marker!r}")
    return text[:start] + replacement + text[end:]


def apply(path: Path = APP_FILE) -> bool:
    text = path.read_text(encoding="utf-8")
    if "RULES_SERVICE: RulesService | None = None" in text:
        return False

    import_marker = "from event_service import EventService\n"
    if import_marker not in text:
        raise RuntimeError("EventService import marker was not found.")
    text = text.replace(
        import_marker,
        import_marker + "from rules_service import RulesService\n",
        1,
    )

    rules_block = '''def spot_to_coord(value: Any) -> int:
    return RulesService.spot_to_coord(value)


def coord_to_spot(coord: int) -> str:
    return RulesService.coord_to_spot(coord)


def team_direction(state: dict[str, Any], team: str) -> int:
    return RulesService.team_direction(state, team)


def opposite(team: str) -> str:
    return RulesService.opposite(team)


def advance_down(down: str) -> str:
    return RulesService.advance_down(down)


RULES_SERVICE: RulesService | None = None


def get_rules_service() -> RulesService:
    global RULES_SERVICE
    if RULES_SERVICE is None:
        RULES_SERVICE = RulesService(
            load_state=load_state,
            save_state=save_state,
            push_history=push_history,
            source_allowed=game_data_source_allowed,
            locked_payload=EventService.locked_payload,
            resolve_player=resolve_game_roster_player,
            show_player_graphic=show_automation_player_graphic,
            transaction_lock=lock,
        )
    return RULES_SERVICE


@app.post("/api/clock-control")
@require_auth
def clock_control():
    result = get_rules_service().clock_control(
        request.get_json(force=True) or {}
    )
    return jsonify(result.data["state"])


@app.post("/api/field-direction")
@require_auth
def field_direction():
    result = get_rules_service().field_direction(
        request.get_json(force=True) or {}
    )
    if result.code == "INVALID_DIRECTION":
        return jsonify({"error": result.code}), 400
    return jsonify(result.data["state"])


@app.post("/api/rules-play")
@require_auth
def rules_play():
    result = get_rules_service().play(request.get_json(force=True) or {})
    if result.code == "INVALID_PLAY":
        return jsonify({"error": result.code}), 400
    if result.code == "NO_ACTIVE_BROADCAST":
        return jsonify({"error": result.code}), 409
    if result.code == "CONTROL_SOURCE_LOCKED":
        return jsonify(result.data), 409
    return jsonify(result.data)


'''
    text = _replace_block(
        text,
        "def spot_to_coord(value: Any) -> int:\n",
        '@app.post("/api/undo")\n',
        rules_block,
    )

    path.write_text(text, encoding="utf-8")
    return True


def main() -> None:
    changed = apply()
    if changed:
        print("Phase 4.19 RulesService integration applied.")
    else:
        print("Phase 4.19 RulesService integration was already present.")


if __name__ == "__main__":
    main()
