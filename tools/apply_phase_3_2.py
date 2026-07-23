from __future__ import annotations

import argparse
import ast
import shutil
from pathlib import Path

IMPORT_OLD = "from school_repository import SchoolRepository"
IMPORT_NEW = IMPORT_OLD + "\nfrom roster_repository import RosterRepository"

WRITE_OLD = '''def _write_rosters_file(items: list[dict[str, Any]], snapshot: bool = True) -> None:
    global _roster_cache, _roster_cache_mtime_ns
    ensure_data_architecture()
    with roster_io_lock:
        existing = _parse_roster_payload(ROSTERS_FILE) if ROSTERS_FILE.exists() else []
        if existing == items:
            _roster_cache = copy.deepcopy(items)
            _roster_cache_mtime_ns = ROSTERS_FILE.stat().st_mtime_ns if ROSTERS_FILE.exists() else None
            return
        if snapshot and ROSTERS_FILE.exists() and _roster_payload_score(existing)[0] > 0:
            snapshot_path = DATA_DIR / "Backups" / "RosterSnapshots" / f"rosters-{int(time.time() * 1000)}.json"
            snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(ROSTERS_FILE, snapshot_path)
            except OSError:
                pass
        temp_path = ROSTERS_FILE.with_suffix(".json.tmp")
        temp_path.write_text(json.dumps(items, indent=2), encoding="utf-8")
        os.replace(temp_path, ROSTERS_FILE)
        _roster_cache = copy.deepcopy(items)
        _roster_cache_mtime_ns = ROSTERS_FILE.stat().st_mtime_ns

def load_rosters() -> list[dict[str, Any]]:
    global _roster_cache, _roster_cache_mtime_ns
    ensure_data_architecture()
    recover_rosters_if_needed()
    if not ROSTERS_FILE.exists():
        return []
    try:
        mtime_ns = ROSTERS_FILE.stat().st_mtime_ns
    except OSError:
        mtime_ns = None
    if _roster_cache is not None and _roster_cache_mtime_ns == mtime_ns:
        return copy.deepcopy(_roster_cache)
    items = _parse_roster_payload(ROSTERS_FILE)
    if _normalize_rosters(items):
        _write_rosters_file(items, snapshot=False)
    else:
        _roster_cache = copy.deepcopy(items)
        _roster_cache_mtime_ns = mtime_ns
    return copy.deepcopy(items)

def save_rosters(items: list[dict[str, Any]]) -> None:
    if not isinstance(items, list):
        raise ValueError("Roster database must be a list")
    _normalize_rosters(items)
    _write_rosters_file(items, snapshot=True)
'''

WRITE_NEW = '''def _write_rosters_file(items: list[dict[str, Any]], snapshot: bool = True) -> None:
    ensure_data_architecture()
    ROSTER_REPOSITORY.save(items)

def load_rosters() -> list[dict[str, Any]]:
    ensure_data_architecture()
    recover_rosters_if_needed()
    return ROSTER_REPOSITORY.load()

def save_rosters(items: list[dict[str, Any]]) -> None:
    ensure_data_architecture()
    ROSTER_REPOSITORY.save(items)
'''

REPOSITORY_BLOCK = '''ROSTER_REPOSITORY = RosterRepository(
    CORE_PERSISTENCE,
    ROSTERS_FILE,
    normalizer=_normalize_rosters,
)

'''

MARKER = "# Phase 3.2: RosterRepository integrated"


def _find_function_line(source: str, function_name: str) -> int:
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name:
            return node.lineno
    raise RuntimeError(f"Phase 3.2 cannot be applied; missing function: {function_name}")


def _line_start_offset(source: str, line_number: int) -> int:
    if line_number <= 1:
        return 0
    offset = 0
    for _ in range(line_number - 1):
        newline = source.find("\n", offset)
        if newline < 0:
            return len(source)
        offset = newline + 1
    return offset


def transform(source: str) -> str:
    if MARKER in source:
        return source

    missing = []
    if IMPORT_OLD not in source:
        missing.append("school repository import")
    if WRITE_OLD not in source:
        missing.append("roster persistence functions")
    try:
        normalizer_line = _find_function_line(source, "_normalize_rosters")
        writer_line = _find_function_line(source, "_write_rosters_file")
    except RuntimeError as exc:
        missing.append(str(exc).split(": ")[-1])
        normalizer_line = writer_line = 0

    if missing:
        raise RuntimeError("Phase 3.2 cannot be applied; missing anchors: " + ", ".join(missing))
    if normalizer_line >= writer_line:
        raise RuntimeError("Phase 3.2 cannot be applied; roster normalizer must precede roster writer.")

    updated = source.replace(IMPORT_OLD, IMPORT_NEW, 1)
    updated = updated.replace(WRITE_OLD, WRITE_NEW, 1)

    writer_line_after = _find_function_line(updated, "_write_rosters_file")
    insert_at = _line_start_offset(updated, writer_line_after)
    updated = updated[:insert_at] + REPOSITORY_BLOCK + updated[insert_at:]
    updated = updated.replace(
        "from roster_repository import RosterRepository",
        "from roster_repository import RosterRepository\n\n" + MARKER,
        1,
    )

    ast.parse(updated)
    forbidden = (
        'temp_path = ROSTERS_FILE.with_suffix(".json.tmp")',
        "os.replace(temp_path, ROSTERS_FILE)",
    )
    if any(token in updated for token in forbidden):
        raise RuntimeError("Direct roster database write remains after migration.")
    repository_pos = updated.index("ROSTER_REPOSITORY = RosterRepository")
    normalizer_pos = updated.index("def _normalize_rosters")
    if repository_pos < normalizer_pos:
        raise RuntimeError("RosterRepository initialization precedes its normalizer definition.")
    return updated


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply CSRN Phase 3.2 RosterRepository integration.")
    parser.add_argument("app", nargs="?", default="app.py")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    path = Path(args.app).resolve()
    source = path.read_text(encoding="utf-8")
    updated = transform(source)
    if args.check:
        print(f"Phase 3.2 migration is applicable: {path}" if updated != source else f"Phase 3.2 already applied: {path}")
        return 0
    if updated == source:
        print(f"Phase 3.2 already applied: {path}")
        return 0

    backup = path.with_name(path.name + ".phase-3.2.bak")
    shutil.copy2(path, backup)
    path.write_text(updated, encoding="utf-8")
    print(f"Phase 3.2 applied: {path}")
    print(f"Backup created: {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
