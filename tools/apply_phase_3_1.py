from __future__ import annotations

import argparse
import ast
import shutil
from pathlib import Path


IMPORT_OLD = "from core_repositories import ConfigurationRepository, StateRepository, SecurityRepository"
IMPORT_NEW = IMPORT_OLD + "\nfrom school_repository import SchoolRepository"

REPOSITORY_ANCHOR = "SECURITY_REPOSITORY = SecurityRepository(CORE_PERSISTENCE, SECURITY_FILE, DEFAULT_SECURITY)"

LOAD_OLD = '''def load_schools() -> list[dict[str, Any]]:\n    ensure_data_architecture()\n    if not SCHOOLS_FILE.exists():\n        save_json(SCHOOLS_FILE, {"schools": []})\n    raw = load_json(SCHOOLS_FILE, {"schools": []})\n    if isinstance(raw, list):\n        schools = raw\n    else:\n        schools = raw.get("schools", [])\n    if not isinstance(schools, list):\n        return []\n    changed = reconcile_5a_csrn_ids(schools)\n    for school in schools:\n        before = json.dumps(school, sort_keys=True)\n        ensure_school_schema(school, schools)\n        changed = changed or before != json.dumps(school, sort_keys=True)\n    if changed:\n        save_schools(schools)\n    return schools\n\ndef save_schools(schools: list[dict[str, Any]]) -> None:\n    ensure_data_architecture()\n    SCHOOLS_FILE.write_text(json.dumps(schools, indent=2), encoding="utf-8")\n'''

REPOSITORY_INSERT = '''SCHOOL_REPOSITORY = SchoolRepository(\n    CORE_PERSISTENCE,\n    SCHOOLS_FILE,\n    school_normalizer=ensure_school_schema,\n    collection_normalizer=reconcile_5a_csrn_ids,\n)\n\n'''

LOAD_NEW = REPOSITORY_INSERT + '''def load_schools() -> list[dict[str, Any]]:\n    ensure_data_architecture()\n    return SCHOOL_REPOSITORY.load()\n\ndef save_schools(schools: list[dict[str, Any]]) -> None:\n    ensure_data_architecture()\n    SCHOOL_REPOSITORY.save(schools)\n'''

MARKER = "# Phase 3.1: SchoolRepository integrated"


def transform(source: str) -> str:
    if MARKER in source:
        return source
    missing = [
        name
        for name, anchor in (
            ("core repository import", IMPORT_OLD),
            ("security repository initialization", REPOSITORY_ANCHOR),
            ("school persistence functions", LOAD_OLD),
        )
        if anchor not in source
    ]
    if missing:
        raise RuntimeError("Phase 3.1 cannot be applied; missing anchors: " + ", ".join(missing))

    updated = source.replace(IMPORT_OLD, IMPORT_NEW, 1)
    updated = updated.replace(LOAD_OLD, LOAD_NEW, 1)
    updated = updated.replace("from school_repository import SchoolRepository", "from school_repository import SchoolRepository\n\n" + MARKER, 1)

    ast.parse(updated)
    repository_position = updated.index("SCHOOL_REPOSITORY = SchoolRepository")
    schema_position = updated.index("def ensure_school_schema")
    reconcile_position = updated.index("def reconcile_5a_csrn_ids")
    if repository_position < max(schema_position, reconcile_position):
        raise RuntimeError("SchoolRepository initialization must follow its normalizer definitions.")
    if "SCHOOLS_FILE.write_text" in updated:
        raise RuntimeError("Direct school database write remains after migration.")
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply CSRN Phase 3.1 SchoolRepository integration.")
    parser.add_argument("app", nargs="?", default="app.py")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    path = Path(args.app).resolve()
    source = path.read_text(encoding="utf-8")
    updated = transform(source)

    if args.check:
        print(f"Phase 3.1 migration is applicable: {path}" if updated != source else f"Phase 3.1 already applied: {path}")
        return 0

    if updated == source:
        print(f"Phase 3.1 already applied: {path}")
        return 0

    backup = path.with_name(path.name + ".phase-3.1.bak")
    shutil.copy2(path, backup)
    path.write_text(updated, encoding="utf-8")
    print(f"Phase 3.1 applied: {path}")
    print(f"Backup created: {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
