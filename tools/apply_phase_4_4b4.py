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
        "from association_import_service import AssociationImportService\n",
        (
            "from association_supplement_service import "
            "AssociationSupplementService\n"
        ),
        "association supplement import",
    )

    service_anchor = (
        "def get_association_import_service() -> AssociationImportService:\n"
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
    service_addition = (
        "\n\nASSOCIATION_SUPPLEMENT_SERVICE: "
        "AssociationSupplementService | None = None\n"
        "\n\ndef get_association_supplement_service() "
        "-> AssociationSupplementService:\n"
        "    global ASSOCIATION_SUPPLEMENT_SERVICE\n"
        "\n"
        "    if ASSOCIATION_SUPPLEMENT_SERVICE is None:\n"
        "        ASSOCIATION_SUPPLEMENT_SERVICE = AssociationSupplementService(\n"
        "            load_schools=load_schools,\n"
        "            save_schools=save_schools,\n"
        "            load_venues=load_venues,\n"
        "            save_venues=save_venues,\n"
        "        )\n"
        "\n"
        "    return ASSOCIATION_SUPPLEMENT_SERVICE\n"
    )
    source = insert_once(
        source,
        service_anchor,
        service_addition,
        "association supplement runtime",
    )

    route_start = '@app.get("/api/imports/mhsaa/5A/branding/analyze")\n'
    route_end = "def _hex(rgb: tuple[int, int, int]) -> str:\n"
    start_index = source.find(route_start)
    end_index = source.find(route_end, start_index)
    if start_index < 0 or end_index < 0:
        raise RuntimeError("MHSAA branding/enrichment route block not found")

    replacement = '''@app.get("/api/imports/mhsaa/5A/branding/analyze")
@require_auth
def analyze_mhsaa_5a_branding():
    manifest = load_json(MHSAA_5A_BRANDING_FILE, {"schools": []})
    result = get_association_supplement_service().analyze_branding(
        manifest.get("schools", []),
        source=manifest.get("source", {}),
    )
    if not result.ok:
        return jsonify({"error": result.code}), 400
    return jsonify(result.data)


@app.post("/api/imports/mhsaa/5A/branding")
@require_auth
def import_mhsaa_5a_branding():
    manifest = load_json(MHSAA_5A_BRANDING_FILE, {"schools": []})
    result = get_association_supplement_service().apply_branding(
        manifest.get("schools", []),
        source=manifest.get("source", {}),
    )
    if not result.ok:
        return jsonify({"error": result.code}), 400
    return jsonify(result.data)


@app.get("/api/imports/mhsaa/5A/enrichment/analyze")
@require_auth
def analyze_mhsaa_5a_enrichment():
    manifest = load_json(MHSAA_5A_ENRICHMENT_FILE, {"schools": []})
    result = get_association_supplement_service().analyze_enrichment(
        manifest.get("schools", []),
        source=manifest.get("source", {}),
        classification=str(manifest.get("classification", "5A")),
    )
    if not result.ok:
        return jsonify({"error": result.code}), 400
    return jsonify(result.data)


@app.post("/api/imports/mhsaa/5A/enrichment")
@require_auth
def enrich_mhsaa_5a():
    manifest = load_json(MHSAA_5A_ENRICHMENT_FILE, {"schools": []})
    result = get_association_supplement_service().apply_enrichment(
        manifest.get("schools", []),
        source=manifest.get("source", {}),
        venue_sport="Football",
    )
    if not result.ok:
        return jsonify({"error": result.code}), 400
    return jsonify(result.data)


'''
    source = source[:start_index] + replacement + source[end_index:]

    APP_PATH.write_text(source, encoding="utf-8")
    print("Phase 4.4B4 association supplement routes wired.")


if __name__ == "__main__":
    main()
