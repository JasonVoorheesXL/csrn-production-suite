from __future__ import annotations

from pathlib import Path


APP_PATH = Path("app.py")


def insert_once(source: str, anchor: str, addition: str, label: str) -> str:
    if addition.strip() in source:
        return source
    if anchor not in source:
        raise RuntimeError(f"{label} anchor not found")
    return source.replace(anchor, anchor + addition, 1)


def main() -> None:
    source = APP_PATH.read_text(encoding="utf-8")

    source = insert_once(
        source,
        "from school_service import SchoolService\n",
        "from roster_service import RosterService\n",
        "roster service import",
    )

    service_anchor = (
        "def save_rosters(items: list[dict[str, Any]]) -> None:\n"
        "    ensure_data_architecture()\n"
        "    ROSTER_REPOSITORY.save(items)\n"
    )
    service_addition = (
        "\n\nROSTER_SERVICE: RosterService | None = None\n"
        "\n\ndef get_roster_service() -> RosterService:\n"
        "    global ROSTER_SERVICE\n"
        "\n"
        "    if ROSTER_SERVICE is None:\n"
        "        ROSTER_SERVICE = RosterService(\n"
        "            load_rosters=load_rosters,\n"
        "            save_rosters=save_rosters,\n"
        "            load_schools=load_schools,\n"
        "        )\n"
        "\n"
        "    return ROSTER_SERVICE\n"
    )
    source = insert_once(
        source,
        service_anchor,
        service_addition,
        "roster service runtime",
    )

    route_start = '@app.get("/api/rosters")\n'
    route_end = '@app.post("/api/rosters/<roster_id>/players")\n'
    start_index = source.find(route_start)
    end_index = source.find(route_end, start_index)
    if start_index < 0 or end_index < 0:
        raise RuntimeError("Roster CRUD route block not found")

    replacement = '''@app.get("/api/rosters")
@require_auth
def list_rosters():
    return jsonify(get_roster_service().list_rosters())


@app.post("/api/rosters")
@require_auth
def create_roster():
    result = get_roster_service().create(
        request.get_json(force=True) or {}
    )
    if result.code == "SCHOOL_AND_SEASON_REQUIRED":
        return jsonify({"error": result.code}), 400
    if result.code == "ROSTER_ALREADY_EXISTS":
        return jsonify(
            {
                "error": result.code,
                "roster": result.data["roster"],
            }
        ), 409
    return jsonify(result.data["roster"]), 201


@app.put("/api/rosters/<roster_id>")
@require_auth
def update_roster(roster_id: str):
    result = get_roster_service().update(
        roster_id,
        request.get_json(force=True) or {},
    )
    if result.code == "ROSTER_NOT_FOUND":
        return jsonify({"error": result.code}), 404
    return jsonify(result.data["roster"])


@app.delete("/api/rosters/<roster_id>")
@require_auth
def delete_roster(roster_id: str):
    result = get_roster_service().delete(roster_id)
    if result.code == "ROSTER_NOT_FOUND":
        return jsonify({"error": result.code}), 404
    return jsonify({"ok": True})


'''
    source = source[:start_index] + replacement + source[end_index:]

    APP_PATH.write_text(source, encoding="utf-8")
    print("Phase 4.5B roster CRUD routes wired.")


if __name__ == "__main__":
    main()
