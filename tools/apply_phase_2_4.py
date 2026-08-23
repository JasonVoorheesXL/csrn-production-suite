from __future__ import annotations

import argparse
import shutil
from pathlib import Path


IMPORT_ANCHOR = "from upgrade_manager import inspect_candidate, migrate\n"
REPOSITORY_IMPORTS = (
    "from persistence_engine import JsonPersistenceEngine\n"
    "from core_repositories import ConfigurationRepository, StateRepository, SecurityRepository\n"
)

CONFIG_START = "def load_config() -> dict[str, Any]:\n"
CONFIG_END = "\n\n\ndef application_identity() -> dict[str, str]:\n"
CONFIG_REPLACEMENT = '''CORE_BACKUP_DIR = DATA_DIR / "Backups" / "Core"
CORE_QUARANTINE_DIR = DATA_DIR / "Backups" / "Quarantine"
CORE_PERSISTENCE = JsonPersistenceEngine(CORE_BACKUP_DIR, CORE_QUARANTINE_DIR)
CONFIG_REPOSITORY = ConfigurationRepository(
    CORE_PERSISTENCE,
    CONFIG_FILE,
    DEFAULT_CONFIG,
    runtime_identity={
        "version": "Version 1.13.0-alpha.3h — Roster Performance Stabilization",
        "build": "V1.13A3H-ROSTER-STABILITY",
    },
)
STATE_REPOSITORY = StateRepository(CORE_PERSISTENCE, STATE_FILE, DEFAULT_STATE)
SECURITY_REPOSITORY = SecurityRepository(CORE_PERSISTENCE, SECURITY_FILE, DEFAULT_SECURITY)


def load_config() -> dict[str, Any]:
    ensure_data_architecture()
    config = CONFIG_REPOSITORY.load()
    config.setdefault("application", {})["rules_edition"] = "NFHS"
    return config


def save_config(config: dict[str, Any]) -> None:
    ensure_data_architecture()
    CONFIG_REPOSITORY.save(config)
'''

SECURITY_START = "def load_security() -> dict[str, Any]:\n"
SECURITY_END = "\nsecurity = load_security()\n"
SECURITY_REPLACEMENT = '''def load_security() -> dict[str, Any]:
    sec = SECURITY_REPOSITORY.load()
    if not sec.get("secret_key"):
        sec["secret_key"] = secrets.token_hex(32)
        SECURITY_REPOSITORY.save(sec)
    return sec


def save_security(sec: dict[str, Any]) -> None:
    SECURITY_REPOSITORY.save(sec)
'''


def replace_between(source: str, start: str, end: str, replacement: str) -> str:
    start_at = source.find(start)
    if start_at < 0:
        raise RuntimeError(f"Required start anchor not found: {start.strip()}")
    end_at = source.find(end, start_at)
    if end_at < 0:
        raise RuntimeError(f"Required end anchor not found: {end.strip()}")
    return source[:start_at] + replacement + source[end_at:]


def migrate(source: str) -> str:
    if REPOSITORY_IMPORTS not in source:
        if IMPORT_ANCHOR not in source:
            raise RuntimeError("upgrade_manager import anchor not found")
        source = source.replace(IMPORT_ANCHOR, IMPORT_ANCHOR + REPOSITORY_IMPORTS, 1)

    if "CONFIG_REPOSITORY = ConfigurationRepository(" not in source:
        source = replace_between(source, CONFIG_START, CONFIG_END, CONFIG_REPLACEMENT)

    source = source.replace(
        "state = normalize_state(load_json(STATE_FILE, DEFAULT_STATE))",
        "state = normalize_state(STATE_REPOSITORY.load())",
    )
    source = source.replace(
        "save_json(STATE_FILE, normalize_state(state))",
        "STATE_REPOSITORY.replace(normalize_state(state))",
    )
    source = source.replace(
        "save_json(STATE_FILE, normalized)",
        "STATE_REPOSITORY.replace(normalized)",
    )

    if "def save_security(sec: dict[str, Any])" not in source:
        source = replace_between(source, SECURITY_START, SECURITY_END, SECURITY_REPLACEMENT)
    source = source.replace("save_json(SECURITY_FILE, sec)", "save_security(sec)")

    forbidden = (
        "load_json(STATE_FILE, DEFAULT_STATE)",
        "save_json(STATE_FILE,",
        "load_json(SECURITY_FILE, DEFAULT_SECURITY)",
        "save_json(SECURITY_FILE,",
    )
    remaining = [value for value in forbidden if value in source]
    if remaining:
        raise RuntimeError(f"Direct core persistence remains: {remaining}")
    return source


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply CSRN Phase 2.4 repository integration to app.py")
    parser.add_argument("app", nargs="?", default="app.py", type=Path)
    parser.add_argument("--check", action="store_true", help="Validate the migration without writing")
    args = parser.parse_args()

    app_path = args.app.resolve()
    original = app_path.read_text(encoding="utf-8")
    migrated = migrate(original)

    compile(migrated, str(app_path), "exec")
    if args.check:
        print(f"Phase 2.4 migration is applicable: {app_path}")
        return 0

    backup = app_path.with_suffix(app_path.suffix + ".phase-2.4.bak")
    shutil.copy2(app_path, backup)
    app_path.write_text(migrated, encoding="utf-8", newline="\n")
    print(f"Phase 2.4 applied: {app_path}")
    print(f"Backup created: {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
