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
    if "EVENT_SERVICE: EventService | None = None" in text:
        return False

    import_marker = "from upgrade_service import UpgradeService\n"
    if import_marker not in text:
        raise RuntimeError("UpgradeService import marker was not found.")
    text = text.replace(
        import_marker,
        import_marker + "from event_service import EventService\n",
        1,
    )

    event_block = '''EVENT_SERVICE: EventService | None = None


def get_event_service() -> EventService:
    global EVENT_SERVICE
    if EVENT_SERVICE is None:
        EVENT_SERVICE = EventService(
            load_state=load_state,
            save_state=save_state,
            public_state=public_state,
            push_history=push_history,
            update_linked_status=update_linked_broadcast_status,
            automation_player=automation_player,
            manual_player=manual_automation_player,
            player_display=player_display,
            show_player_graphic=show_automation_player_graphic,
            apply_penalty=apply_penalty_enforcement,
            spot_to_coord=spot_to_coord,
            team_direction=team_direction,
            normalize_state=normalize_state,
            default_player_graphic=lambda: copy.deepcopy(
                DEFAULT_STATE["player_graphic"]
            ),
            transaction_lock=lock,
        )
    return EVENT_SERVICE


def game_data_source_allowed(state: dict[str, Any], source: str) -> bool:
    return EventService.source_allowed(state, source)


def authority_rejection(state: dict[str, Any]):
    return jsonify(EventService.locked_payload(state)), 409


@app.post("/api/control-source")
@require_auth
def set_control_source():
    data = request.get_json(force=True) or {}
    result = get_event_service().set_control_source(data.get("authority", ""))
    if result.code == "INVALID_CONTROL_SOURCE":
        return jsonify({"error": result.code}), 400
    return jsonify(result.data["state"])


@app.post("/api/event-trigger")
@require_auth
def event_trigger():
    result = get_event_service().trigger(request.get_json(force=True) or {})
    if result.code == "INVALID_EVENT":
        return jsonify({"error": result.code}), 400
    if result.code == "NO_ACTIVE_BROADCAST":
        return jsonify({"error": result.code}), 409
    if result.code == "CONTROL_SOURCE_LOCKED":
        return jsonify(result.data), 409
    return jsonify(result.data)


@app.post("/api/game-correction")
@require_auth
def game_correction():
    result = get_event_service().quick_correction(
        request.get_json(force=True) or {}
    )
    if result.code in {"INVALID_DOWN", "INVALID_POSSESSION"}:
        return jsonify({"error": result.code}), 400
    if result.code == "CONTROL_SOURCE_LOCKED":
        return jsonify(result.data), 409
    return jsonify(result.data["state"])


@app.post("/api/events/<event_id>/edit")
@require_auth
def edit_event(event_id: str):
    result = get_event_service().edit(
        event_id,
        request.get_json(force=True) or {},
    )
    if result.code == "EVENT_NOT_FOUND":
        return jsonify({"error": result.code}), 404
    if result.code == "CONTROL_SOURCE_LOCKED":
        return jsonify(result.data), 409
    return jsonify(result.data)


@app.get("/api/corrections")
@require_auth
def corrections_report():
    result = get_event_service().corrections()
    return jsonify(result.data["corrections"])


'''
    text = _replace_block(
        text,
        "def game_data_source_allowed(state: dict[str, Any], source: str) -> bool:\n",
        '@app.get("/api/connection-info")\n',
        event_block,
    )

    undo_block = '''@app.post("/api/undo")
@require_auth
def undo():
    result = get_event_service().undo()
    return jsonify(result.data["state"])


'''
    text = _replace_block(
        text,
        '@app.post("/api/undo")\n',
        "def local_ip() -> str:\n",
        undo_block,
    )

    path.write_text(text, encoding="utf-8")
    return True


def main() -> None:
    changed = apply()
    if changed:
        print("Phase 4.18 EventService integration applied.")
    else:
        print("Phase 4.18 EventService integration was already present.")


if __name__ == "__main__":
    main()
