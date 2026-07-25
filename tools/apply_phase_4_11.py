from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "app.py"


class MigrationError(RuntimeError):
    pass


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise MigrationError(f"Expected one {label} marker; found {count}.")
    return text.replace(old, new, 1)


def replace_between(
    text: str,
    start_marker: str,
    end_marker: str,
    replacement: str,
    label: str,
) -> str:
    start = text.find(start_marker)
    if start < 0:
        raise MigrationError(f"Missing {label} start marker.")
    end = text.find(end_marker, start)
    if end < 0:
        raise MigrationError(f"Missing {label} end marker.")
    return text[:start] + replacement + text[end:]


def main() -> None:
    text = APP_PATH.read_text(encoding="utf-8")
    if "from graphics_service import GraphicsService" in text:
        raise MigrationError("GraphicsService integration is already present.")

    text = replace_once(
        text,
        "from asset_service import AssetService\n",
        "from asset_service import AssetService\nfrom graphics_service import GraphicsService\n",
        "AssetService import",
    )

    personnel_anchor = '''PERSONNEL_SERVICE: PersonnelService | None = None


def get_personnel_service() -> PersonnelService:
    global PERSONNEL_SERVICE

    if PERSONNEL_SERVICE is None:
        PERSONNEL_SERVICE = PersonnelService(
            load_personnel=load_broadcasters,
            save_personnel=save_broadcasters,
        )

    return PERSONNEL_SERVICE
'''
    graphics_factory = personnel_anchor + '''

GRAPHICS_SERVICE: GraphicsService | None = None


def get_graphics_service() -> GraphicsService:
    global GRAPHICS_SERVICE

    if GRAPHICS_SERVICE is None:
        GRAPHICS_SERVICE = GraphicsService(
            default_state=lambda: copy.deepcopy(DEFAULT_STATE),
            load_rosters=load_rosters,
            load_schools=load_schools,
            load_personnel=load_broadcasters,
            build_identity=broadcast_identity,
            apply_sponsor=apply_sponsor_to_graphic,
        )

    return GRAPHICS_SERVICE
'''
    text = replace_once(
        text,
        personnel_anchor,
        graphics_factory,
        "PersonnelService factory",
    )

    graphics_routes = '''def activate_primary_graphic(state: dict[str, Any], active: str) -> None:
    """Keep the legacy mutating helper while delegating graphic rules."""
    updated = get_graphics_service().activate_primary(state, active)
    state.clear()
    state.update(updated)


@app.post("/api/graphics/lower-third")
@require_auth
def update_lower_third():
    data = request.get_json(force=True) or {}
    with lock:
        result = get_graphics_service().update_lower_third(load_state(), data)
        state = result.data["state"]
        save_state(state)
    return jsonify(public_state(state))


@app.post("/api/graphics/player")
@require_auth
def update_player_graphic():
    data = request.get_json(force=True) or {}
    with lock:
        result = get_graphics_service().update_player(load_state(), data)
        if result.code == "PLAYER_REQUIRED":
            return jsonify({"error": result.code}), 400
        state = result.data["state"]
        save_state(state)
    response = public_state(state)
    warning = str(result.data.get("sponsor_warning", ""))
    if warning:
        response["sponsor_warning"] = warning
    return jsonify(response)


@app.post("/api/graphics/personnel")
@require_auth
def update_personnel_graphic():
    data = request.get_json(force=True) or {}
    with lock:
        result = get_graphics_service().update_personnel(load_state(), data)
        if result.code == "PERSONNEL_REQUIRED":
            return jsonify({"error": result.code}), 400
        state = result.data["state"]
        save_state(state)
    response = public_state(state)
    warning = str(result.data.get("sponsor_warning", ""))
    if warning:
        response["sponsor_warning"] = warning
    return jsonify(response)


'''
    text = replace_between(
        text,
        "def activate_primary_graphic(state: dict[str, Any], active: str) -> None:",
        "def automation_player(roster_id: str, player_id: str):",
        graphics_routes,
        "primary graphics routes",
    )

    helper_wrappers = '''def player_display(player):
    return GraphicsService.player_display(player)


def normalize_position(value):
    return GraphicsService.normalize_position(value)


def event_position(player, defensive=False):
    return GraphicsService.event_position(player, defensive=defensive)


'''
    text = replace_between(
        text,
        "def player_display(player):",
        "def manual_automation_player(data, team_name):",
        helper_wrappers,
        "graphics helper functions",
    )

    automation_wrapper = '''def show_automation_player_graphic(
    state,
    roster,
    player,
    graphic_type,
    duration,
    defensive=False,
    eyebrow="",
    play_detail="",
):
    result = get_graphics_service().show_automation_player(
        state,
        roster,
        player,
        graphic_type,
        duration,
        defensive=defensive,
        eyebrow=eyebrow,
        play_detail=play_detail,
    )
    state.clear()
    state.update(result.data["state"])


'''
    text = replace_between(
        text,
        "def show_automation_player_graphic(state, roster, player, graphic_type, duration, defensive=False, eyebrow=\"\", play_detail=\"\"):",
        "def canonical_team_key(state: dict[str, Any], value: Any) -> str:",
        automation_wrapper,
        "automation player graphic helper",
    )

    APP_PATH.write_text(text, encoding="utf-8")
    print("Phase 4.11 GraphicsService integration applied.")


if __name__ == "__main__":
    main()
