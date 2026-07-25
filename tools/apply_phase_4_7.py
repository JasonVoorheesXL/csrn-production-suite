from __future__ import annotations

from pathlib import Path


APP_PATH = Path("app.py")


VENUE_HELPERS = '''VENUE_REPOSITORY = VenueRepository(
    CORE_PERSISTENCE,
    VENUES_FILE,
)


def load_venues() -> list[dict[str, Any]]:
    ensure_data_architecture()
    return VENUE_REPOSITORY.load()


def save_venues(items: list[dict[str, Any]]) -> None:
    ensure_data_architecture()
    VENUE_REPOSITORY.save(items)


VENUE_SERVICE: VenueService | None = None


def get_venue_service() -> VenueService:
    global VENUE_SERVICE

    if VENUE_SERVICE is None:
        VENUE_SERVICE = VenueService(
            load_venues=load_venues,
            save_venues=save_venues,
            load_schools=load_schools,
            load_broadcasts=load_broadcasts,
        )

    return VENUE_SERVICE


'''


VENUE_FOR_SCHOOL = '''def venue_for_school(
    school: dict[str, Any] | None,
    sport: str = "",
) -> dict[str, Any] | None:
    return get_venue_service().for_school(school, sport)


'''


VENUE_MIGRATION = '''def migrate_venue_names() -> None:
    get_venue_service().migrate_legacy_names()


'''


VENUE_ROUTES = '''@app.get("/api/venues")
@require_auth
def list_venues():
    include_inactive = str(
        request.args.get("include_inactive", "true")
    ).strip().lower() not in {"0", "false", "no", "off"}
    result = get_venue_service().list_venues(
        school_id=str(request.args.get("school_id", "")),
        sport=str(request.args.get("sport", "")),
        include_inactive=include_inactive,
    )
    return jsonify(result.data["venues"])


@app.get("/api/venues/<venue_id>")
@require_auth
def read_venue(venue_id: str):
    result = get_venue_service().read(venue_id)
    if result.code == "VENUE_NOT_FOUND":
        return jsonify({"error": result.code}), 404
    return jsonify(result.data["venue"])


@app.post("/api/venues")
@require_auth
def create_venue():
    result = get_venue_service().create(
        request.get_json(silent=True) or {}
    )
    if result.code == "VENUE_NAME_REQUIRED":
        return jsonify({"error": result.code}), 400
    if result.code == "DUPLICATE_VENUE":
        return jsonify(
            {
                "error": result.code,
                "duplicate_venue": result.data["duplicate_venue"],
            }
        ), 409
    return jsonify(result.data["venue"]), 201


@app.put("/api/venues/<venue_id>")
@require_auth
def update_venue(venue_id: str):
    result = get_venue_service().update(
        venue_id,
        request.get_json(silent=True) or {},
    )
    if result.code == "VENUE_NOT_FOUND":
        return jsonify({"error": result.code}), 404
    if result.code == "VENUE_NAME_REQUIRED":
        return jsonify({"error": result.code}), 400
    if result.code == "DUPLICATE_VENUE":
        return jsonify(
            {
                "error": result.code,
                "duplicate_venue": result.data["duplicate_venue"],
            }
        ), 409
    return jsonify(result.data["venue"])


@app.delete("/api/venues/<venue_id>")
@require_auth
def delete_venue(venue_id: str):
    result = get_venue_service().delete(venue_id)
    if result.code == "VENUE_NOT_FOUND":
        return jsonify({"error": result.code}), 404
    if result.code == "VENUE_IN_USE":
        return jsonify({"error": result.code, **result.data}), 409
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

    import_line = "from venue_service import VenueService\n"
    if import_line not in source:
        sponsor_import = "from sponsor_service import SponsorService\n"
        if sponsor_import not in source:
            raise RuntimeError("SponsorService import marker not found")
        source = source.replace(
            sponsor_import,
            sponsor_import + import_line,
            1,
        )

    if "VENUE_SERVICE: VenueService | None = None" not in source:
        source = replace_between(
            source,
            "VENUE_REPOSITORY = VenueRepository(\n",
            "ASSOCIATION_IMPORT_SERVICE: AssociationImportService | None = None\n",
            VENUE_HELPERS,
        )

    if "return get_venue_service().for_school(school, sport)" not in source:
        source = replace_between(
            source,
            "def venue_for_school(",
            "def school_duplicate_candidates(",
            VENUE_FOR_SCHOOL,
        )

    if "get_venue_service().migrate_legacy_names()" not in source:
        source = replace_between(
            source,
            "def migrate_venue_names() -> None:\n",
            "def readiness_payload() -> dict[str, Any]:\n",
            VENUE_MIGRATION,
        )

    if '@app.get("/api/venues/<venue_id>")' not in source:
        source = replace_between(
            source,
            '@app.get("/api/venues")\n',
            '@app.get("/api/logos")\n',
            VENUE_ROUTES,
        )

    source = source.replace(
        "venue = venue_for_school(home_school)\n",
        "venue = venue_for_school(home_school, sport)\n",
        1,
    )

    APP_PATH.write_text(source, encoding="utf-8")
    print("Phase 4.7 VenueService integration applied.")


if __name__ == "__main__":
    main()
