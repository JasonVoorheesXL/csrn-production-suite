from __future__ import annotations

from tools.apply_phase_2_4 import migrate


MINIMAL_APP = '''from upgrade_manager import inspect_candidate, migrate

DEFAULT_STATE = {}
DEFAULT_SECURITY = {}
DEFAULT_CONFIG = {}
DATA_DIR = BASE_DIR / "Data"
CONFIG_FILE = BASE_DIR / "config.json"
STATE_FILE = BASE_DIR / "state.json"
SECURITY_FILE = BASE_DIR / "security.json"

def ensure_data_architecture() -> None:
    pass

def load_config() -> dict[str, Any]:
    return load_json(CONFIG_FILE, DEFAULT_CONFIG)

def save_config(config: dict[str, Any]) -> None:
    save_json(CONFIG_FILE, config)



def application_identity() -> dict[str, str]:
    return {}

def load_state() -> dict[str, Any]:
    state = normalize_state(load_json(STATE_FILE, DEFAULT_STATE))
    save_json(STATE_FILE, normalize_state(state))
    return state

def save_state(state: dict[str, Any]) -> None:
    normalized = normalize_state(state)
    save_json(STATE_FILE, normalized)

def load_security() -> dict[str, Any]:
    sec = load_json(SECURITY_FILE, DEFAULT_SECURITY)
    save_json(SECURITY_FILE, sec)
    return sec

security = load_security()

def login():
    sec = load_security()
    save_json(SECURITY_FILE, sec)
'''


def test_migrates_core_persistence_paths() -> None:
    result = migrate(MINIMAL_APP)
    assert "ConfigurationRepository" in result
    assert "STATE_REPOSITORY.load()" in result
    assert "STATE_REPOSITORY.replace(normalized)" in result
    assert "SECURITY_REPOSITORY.load()" in result
    assert "save_security(sec)" in result
    assert "load_json(STATE_FILE" not in result
    assert "save_json(STATE_FILE" not in result
    assert "load_json(SECURITY_FILE" not in result
    assert "save_json(SECURITY_FILE" not in result


def test_migration_is_idempotent() -> None:
    once = migrate(MINIMAL_APP)
    twice = migrate(once)
    assert twice == once
