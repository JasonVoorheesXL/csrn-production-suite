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
        "from association_import_service import AssociationImportService\n",
        "association service import",
    )

    source = insert_once(
        source,
        "MHSAA_5A_BRANDING_FILE = IMPORTS_DIR / \"mhsaa_5a_branding.json\"\n",
        (
            "MHSAA_5A_PROFILE_FILE = (\n"
            "    IMPORTS_DIR\n"
            "    / \"Profiles\"\n"
            "    / \"mhsaa_football_5a_2025_27.json\"\n"
            ")\n"
        ),
        "MHSAA profile constant",
    )

    service_anchor = (
        "def save_venues(items: list[dict[str, Any]]) -> None:\n"
        "    ensure_data_architecture()\n"
        "    VENUE_REPOSITORY.save(items)\n"
    )
    service_addition = (
        "\n\nASSOCIATION_IMPORT_SERVICE: AssociationImportService | None = None\n"
        "\n\ndef get_association_import_service() -> AssociationImportService:\n"
        "    global ASSOCIATION_IMPORT_SERVICE\n"
        "\n"
        "    if ASSOCIATION_IMPORT_SERVICE is None:\n"
        "        ASSOCIATION_IMPORT_SERVICE = AssociationImportService(\n"
        "            school_service=get_school_service(),\n"
        "            load_schools=load_schools,\n"
        "            load_venues=load_venues,\n"
        "            save_venues=save_venues,\n"
        "        )\n"
        "\n"
        "    return ASSOCIATION_IMPORT_SERVICE\n"
    )
    source = insert_once(
        source,
        service_anchor,
        service_addition,
        "association service runtime",
    )

    route_start = '@app.get("/api/imports/mhsaa/5A/analyze")\n'
    route_end = '@app.get("/api/imports/mhsaa/5A/branding/analyze")\n'
    start_index = source.find(route_start)
    end_index = source.find(route_end, start_index)
    if start_index < 0 or end_index < 0:
        raise RuntimeError("MHSAA analyze/import route block not found")

    replacement = '''@app.get("/api/imports/mhsaa/5A/analyze")
@require_auth
def analyze_mhsaa_5a():
    profile = load_json(MHSAA_5A_PROFILE_FILE, {})
    manifest = load_json(MHSAA_5A_FILE, {"schools": []})
    result = get_association_import_service().analyze(
        profile,
        manifest.get("schools", []),
    )
    if not result.ok:
        return jsonify({"error": result.code}), 400

    schools = []
    for item in result.data.get("schools", []):
        candidate = dict(item.get("candidate") or {})
        candidate["status"] = item.get("status", "invalid")
        candidate["matches"] = item.get("matches", [])
        schools.append(candidate)

    return jsonify(
        {
            "classification": manifest.get("classification", "5A"),
            "source": manifest.get("source", {}),
            "found": result.data.get("found", len(schools)),
            "new": result.data.get("new", 0),
            "existing": result.data.get("existing", 0),
            "possible_duplicates": result.data.get(
                "possible_duplicates",
                0,
            ),
            "schools": schools,
        }
    )


@app.post("/api/imports/mhsaa/5A")
@require_auth
def import_mhsaa_5a():
    options = request.get_json(silent=True) or {}
    profile = load_json(MHSAA_5A_PROFILE_FILE, {})
    manifest = load_json(MHSAA_5A_FILE, {"schools": []})
    result = get_association_import_service().apply(
        profile,
        manifest.get("schools", []),
        create_venues=bool(options.get("create_venues", True)),
        # The legacy MHSAA importer only blocked exact-name matches.
        # Preserve that behavior while generic imports default to review.
        allow_possible_duplicates=True,
    )
    if not result.ok:
        return jsonify({"error": result.code}), 400

    return jsonify(
        {
            "imported": result.data.get("imported", 0),
            "skipped_existing": (
                result.data.get("enriched_existing", 0)
                + result.data.get("skipped_existing", 0)
            ),
            "created_ids": result.data.get("created_ids", []),
            "total_schools": result.data.get("total_schools", 0),
        }
    )


'''
    source = source[:start_index] + replacement + source[end_index:]

    APP_PATH.write_text(source, encoding="utf-8")
    print("Phase 4.4B2 association import routes wired.")


if __name__ == "__main__":
    main()
