from __future__ import annotations

from pathlib import Path


APP_PATH = Path("app.py")
START_MARKER = '@app.post("/api/rosters/<roster_id>/players")\n'
END_MARKER = '@app.get("/api/schools")\n'


ROUTES = '''@app.post("/api/rosters/<roster_id>/players")
@require_auth
def create_roster_player(roster_id: str):
    result = get_roster_service().create_player(
        roster_id,
        request.get_json(force=True) or {},
    )
    if result.code == "ROSTER_NOT_FOUND":
        return jsonify({"error": result.code}), 404
    if result.code == "PLAYER_NAME_REQUIRED":
        return jsonify({"error": result.code}), 400
    return jsonify(result.data), 201


@app.put("/api/rosters/<roster_id>/players/<player_id>")
@require_auth
def update_roster_player(roster_id: str, player_id: str):
    result = get_roster_service().update_player(
        roster_id,
        player_id,
        request.get_json(force=True) or {},
    )
    if result.code in {"ROSTER_NOT_FOUND", "PLAYER_NOT_FOUND"}:
        return jsonify({"error": result.code}), 404
    return jsonify(result.data)


@app.delete("/api/rosters/<roster_id>/players/<player_id>")
@require_auth
def delete_roster_player(roster_id: str, player_id: str):
    result = get_roster_service().delete_player(roster_id, player_id)
    if result.code in {"ROSTER_NOT_FOUND", "PLAYER_NOT_FOUND"}:
        return jsonify({"error": result.code}), 404
    return jsonify({"ok": True})


@app.post("/api/rosters/<roster_id>/players/import")
@require_auth
def import_roster_players(roster_id: str):
    incoming = request.get_json(force=True) or {}
    result = get_roster_service().import_players(
        roster_id,
        incoming.get("players", []),
    )
    if result.code == "INVALID_PLAYER_LIST":
        return jsonify({"error": result.code}), 400
    if result.code == "ROSTER_NOT_FOUND":
        return jsonify({"error": result.code}), 404
    return jsonify(result.data)


'''


def main() -> None:
    source = APP_PATH.read_text(encoding="utf-8")

    if "get_roster_service().create_player(" in source:
        print("Phase 4.5D roster player routes already wired.")
        return

    start = source.find(START_MARKER)
    end = source.find(END_MARKER, start)
    if start < 0:
        raise RuntimeError("Roster player route start marker not found")
    if end < 0:
        raise RuntimeError("School route end marker not found")

    updated = source[:start] + ROUTES + source[end:]
    APP_PATH.write_text(updated, encoding="utf-8")
    print("Phase 4.5D roster player routes wired.")


if __name__ == "__main__":
    main()
