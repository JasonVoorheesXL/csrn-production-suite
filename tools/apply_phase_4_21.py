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
    if "GAME_OPERATIONS_SERVICE: GameOperationsService | None = None" in text:
        return False

    import_marker = "from statistics_service import StatisticsService\n"
    if import_marker not in text:
        raise RuntimeError("StatisticsService import marker was not found.")
    text = text.replace(
        import_marker,
        import_marker
        + "from game_operations_service import GameOperationsService\n",
        1,
    )

    score_block = '''GAME_OPERATIONS_SERVICE: GameOperationsService | None = None


def get_game_operations_service() -> GameOperationsService:
    global GAME_OPERATIONS_SERVICE
    if GAME_OPERATIONS_SERVICE is None:
        GAME_OPERATIONS_SERVICE = GameOperationsService(
            load_state=load_state,
            save_state=save_state,
            default_state=lambda: copy.deepcopy(DEFAULT_STATE),
            push_history=push_history,
            source_allowed=EventService.source_allowed,
            locked_payload=EventService.locked_payload,
            update_linked_status=update_linked_broadcast_status,
            load_config=load_config,
            command_scorebug_visibility=command_scorebug_visibility,
            transaction_lock=lock,
        )
    return GAME_OPERATIONS_SERVICE


@app.post("/api/score")
@require_auth
def update_score():
    result = get_game_operations_service().score(
        request.get_json(force=True) or {}
    )
    if result.code == "INVALID_SCORE_REQUEST":
        return jsonify({"error": result.code}), 400
    if result.code == "CONTROL_SOURCE_LOCKED":
        return jsonify(result.data), 409
    return jsonify(result.data["state"])


@app.post("/api/set")
@require_auth
def set_value():
    result = get_game_operations_service().set_values(
        request.get_json(force=True) or {}
    )
    if result.code == "CONTROL_SOURCE_LOCKED":
        return jsonify(result.data), 409
    return jsonify(result.data["state"])


'''
    text = _replace_block(
        text,
        '@app.post("/api/score")\n',
        '@app.get("/roster-headshots/<filename>")\n',
        score_block,
    )

    lifecycle_block = '''@app.post("/api/toggle-scorebug")
@require_auth
def toggle_scorebug():
    result = get_game_operations_service().toggle_scorebug()
    if result.code == "OBS_COMMAND_BLOCKED":
        return jsonify(
            {
                "error": result.code,
                "message": result.data.get("message", ""),
            }
        ), 409
    return jsonify(result.data["state"])


@app.post("/api/toggle-halftime")
@require_auth
def toggle_halftime():
    result = get_game_operations_service().toggle_halftime()
    return jsonify(result.data["state"])


@app.post("/api/end-game")
@require_auth
def end_game():
    result = get_game_operations_service().end_game()
    return jsonify(result.data["state"])


@app.post("/api/reset-data")
@require_auth
def reset_data():
    result = get_game_operations_service().reset_data()
    return jsonify(result.data["state"])


@app.post("/api/new-broadcast")
@require_auth
def new_broadcast():
    result = get_game_operations_service().new_broadcast()
    return jsonify(result.data["state"])


'''
    text = _replace_block(
        text,
        '@app.post("/api/toggle-scorebug")\n',
        "def spot_to_coord(value: Any) -> int:\n",
        lifecycle_block,
    )

    path.write_text(text, encoding="utf-8")
    return True


def main() -> None:
    changed = apply()
    if changed:
        print("Phase 4.21 GameOperationsService integration applied.")
    else:
        print("Phase 4.21 GameOperationsService integration was already present.")


if __name__ == "__main__":
    main()
