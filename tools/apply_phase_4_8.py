from __future__ import annotations

from pathlib import Path


APP_PATH = Path("app.py")


BROADCAST_HELPERS = '''def save_broadcasts(
    items: list[dict[str, Any]],
) -> None:
    ensure_data_architecture()
    BROADCAST_REPOSITORY.save(items)


def write_broadcast_detail(
    record: dict[str, Any],
    existing_only: bool = False,
) -> None:
    broadcast_id = str(record.get("broadcast_id", "")).strip()
    if not broadcast_id:
        return
    path = DATA_DIR / "Broadcasts" / f"{broadcast_id}.json"
    if existing_only and not path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")


def delete_broadcast_detail(broadcast_id: str) -> None:
    path = DATA_DIR / "Broadcasts" / f"{broadcast_id}.json"
    if path.exists():
        path.unlink()


BROADCAST_SERVICE: BroadcastService | None = None


def get_broadcast_service() -> BroadcastService:
    global BROADCAST_SERVICE

    if BROADCAST_SERVICE is None:
        BROADCAST_SERVICE = BroadcastService(
            load_broadcasts=load_broadcasts,
            save_broadcasts=save_broadcasts,
            get_school=get_school,
            resolve_venue=venue_for_school,
            build_identity=broadcast_identity,
            logo_certification=logo_certification,
            school_monogram=school_monogram,
            load_config=load_config,
            load_state=load_state,
            save_state=save_state,
            default_state=lambda: copy.deepcopy(DEFAULT_STATE),
            write_detail=write_broadcast_detail,
            delete_detail=delete_broadcast_detail,
        )

    return BROADCAST_SERVICE


'''


ID_HELPERS = '''def football_week_code(value: Any) -> str:
    return BroadcastService.football_week_code(value)


def next_broadcast_id(
    sport: str,
    season: str,
    classification: str,
    week: Any,
) -> str:
    return get_broadcast_service().next_id(
        sport,
        season,
        classification,
        week,
    )


'''


LINKED_STATUS_HELPER = '''def update_linked_broadcast_status(
    broadcast_id: str,
    status: str,
    extra: dict[str, Any] | None = None,
) -> None:
    get_broadcast_service().update_linked_status(
        broadcast_id,
        status,
        extra,
    )


'''


RESUME_ROUTE = '''@app.post("/api/resume-broadcast")
@require_auth
def resume_broadcast():
    """Reopen a completed broadcast without discarding its saved game data."""
    with lock:
        state = load_state()
        broadcast_id = str(state.get("broadcast_id", "")).strip()
        if not broadcast_id:
            return jsonify({"error": "NO_ACTIVE_BROADCAST"}), 409
        state["status"] = "live"
        state["broadcast_phase"] = "live"
        state["review_mode"] = False
        # Keep the scorebug hidden until the operator deliberately shows it.
        state["scorebug_visible"] = False
        save_state(state)
        get_broadcast_service().resume_record(broadcast_id)
        return jsonify(public_state(state))


'''


BROADCAST_ROUTES = '''@app.post("/api/create-broadcast")
@require_auth
def create_broadcast():
    result = get_broadcast_service().create(
        request.get_json(force=True) or {}
    )
    return jsonify(result.data)


@app.get("/api/broadcasts")
@require_auth
def list_broadcasts():
    include_archived = str(
        request.args.get("include_archived", "false")
    ).strip().lower() in {"1", "true", "yes", "y", "on"}
    result = get_broadcast_service().list_records(
        include_archived=include_archived
    )
    return jsonify(result.data["broadcasts"])


@app.get("/api/broadcasts/<broadcast_id>")
@require_auth
def get_broadcast_record(broadcast_id: str):
    result = get_broadcast_service().read(broadcast_id)
    if result.code == "NOT_FOUND":
        return jsonify({"error": "NOT_FOUND"}), 404
    return jsonify(result.data["broadcast"])


@app.put("/api/broadcasts/<broadcast_id>")
@require_auth
def update_broadcast_record(broadcast_id: str):
    result = get_broadcast_service().update(
        broadcast_id,
        request.get_json(force=True) or {},
    )
    if result.code == "NOT_FOUND":
        return jsonify({"error": "NOT_FOUND"}), 404
    return jsonify(result.data)


@app.put("/api/broadcasts/<broadcast_id>/status")
@require_auth
def set_broadcast_status(broadcast_id: str):
    incoming = request.get_json(force=True) or {}
    result = get_broadcast_service().set_status(
        broadcast_id,
        incoming.get("status", ""),
    )
    if result.code == "INVALID_STATUS":
        return jsonify({"error": "INVALID_STATUS"}), 400
    if result.code == "NOT_FOUND":
        return jsonify({"error": "NOT_FOUND"}), 404
    return jsonify(result.data["broadcast"])


@app.delete("/api/broadcasts/<broadcast_id>")
@require_auth
def delete_broadcast_record(broadcast_id: str):
    result = get_broadcast_service().delete(broadcast_id)
    if result.code == "NOT_FOUND":
        return jsonify({"error": "NOT_FOUND"}), 404
    return jsonify(result.data)


'''


def replace_between(
    source: str,
    start_marker: str,
    end_marker: str,
    replacement: str,
) -> str:
    start = source.find(start_marker)
    if start < 0:
        raise RuntimeError(f"Start marker not found: {start_marker}")
    end = source.find(end_marker, start)
    if end < 0:
        raise RuntimeError(f"End marker not found: {end_marker}")
    return source[:start] + replacement + source[end:]


def main() -> None:
    source = APP_PATH.read_text(encoding="utf-8")

    import_line = "from broadcast_service import BroadcastService\n"
    if import_line not in source:
        venue_import = "from venue_service import VenueService\n"
        if venue_import not in source:
            raise RuntimeError("VenueService import marker not found")
        source = source.replace(
            venue_import,
            venue_import + import_line,
            1,
        )

    if "BROADCAST_SERVICE: BroadcastService | None = None" not in source:
        source = replace_between(
            source,
            "def save_broadcasts(\n",
            "def normalize_roster_id(value: str) -> str:\n",
            BROADCAST_HELPERS,
        )

    if "return get_broadcast_service().next_id(" not in source:
        source = replace_between(
            source,
            "def football_week_code(value: Any) -> str:\n",
            "def venue_for_school(\n",
            ID_HELPERS,
        )

    if "get_broadcast_service().update_linked_status(" not in source:
        source = replace_between(
            source,
            "def update_linked_broadcast_status(\n",
            "def migrate_venue_names() -> None:\n",
            LINKED_STATUS_HELPER,
        )

    if "get_broadcast_service().resume_record(broadcast_id)" not in source:
        source = replace_between(
            source,
            '@app.post("/api/resume-broadcast")\n',
            '@app.post("/api/create-broadcast")\n',
            RESUME_ROUTE,
        )

    if "result = get_broadcast_service().create(" not in source:
        source = replace_between(
            source,
            '@app.post("/api/create-broadcast")\n',
            '@app.get("/api/build-journal")\n',
            BROADCAST_ROUTES,
        )

    APP_PATH.write_text(source, encoding="utf-8")
    print("Phase 4.8 BroadcastService integration applied.")


if __name__ == "__main__":
    main()
