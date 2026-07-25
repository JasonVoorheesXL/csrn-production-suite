from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from core_repository_runtime import CoreRepositoryRuntime


def fake_module(tmp_path: Path):
    data_dir = tmp_path / "Data"
    defaults_config = {
        "organization": {},
        "broadcast_defaults": {},
        "folders": {},
        "obs": {},
        "application": {"version": "old", "build": "old"},
    }
    defaults_state = {
        "home_score": 0,
        "visitor_score": 0,
        "next_play_number": 1,
        "history": [],
        "events": [],
        "correction_log": [],
        "crew": {},
        "broadcast_id": "",
    }
    defaults_security = {
        "pin_hash": "",
        "secret_key": "test-key",
        "failed_attempts": 0,
        "locked_until": 0,
    }
    ordinary_file = data_dir / "ordinary.json"

    def original_load(path, default):
        return {"source": "original", "path": str(path), "default": default}

    writes = []

    def original_save(path, data):
        writes.append((Path(path), data))

    app = SimpleNamespace(secret_key=None)
    module = SimpleNamespace(
        DATA_DIR=data_dir,
        CONFIG_FILE=data_dir / "Settings" / "config.json",
        STATE_FILE=tmp_path / "state.json",
        SECURITY_FILE=tmp_path / "security.json",
        DEFAULT_CONFIG=defaults_config,
        DEFAULT_STATE=defaults_state,
        DEFAULT_SECURITY=defaults_security,
        RUNTIME_VERSION="Version 1.13.0-alpha.4g — Venue Service",
        RUNTIME_BUILD="V1.13A4G-VENUE-SERVICE",
        load_json=original_load,
        save_json=original_save,
        ensure_data_architecture=lambda: data_dir.mkdir(parents=True, exist_ok=True),
        app=app,
        ordinary_file=ordinary_file,
        writes=writes,
    )
    return module


def test_install_routes_core_files_to_repositories(tmp_path: Path) -> None:
    module = fake_module(tmp_path)
    runtime = CoreRepositoryRuntime(module).install()

    module.save_json(module.STATE_FILE, {
        **module.DEFAULT_STATE,
        "home_score": 14,
    })
    loaded = module.load_json(module.STATE_FILE, module.DEFAULT_STATE)

    assert loaded["home_score"] == 14
    assert module.app.secret_key == "test-key"
    assert module.CORE_REPOSITORY_RUNTIME is runtime


def test_non_core_files_still_use_original_helpers(tmp_path: Path) -> None:
    module = fake_module(tmp_path)
    CoreRepositoryRuntime(module).install()

    result = module.load_json(module.ordinary_file, {"value": 1})
    module.save_json(module.ordinary_file, {"value": 2})

    assert result["source"] == "original"
    assert module.writes == [(module.ordinary_file, {"value": 2})]


def test_config_identity_is_supplied_by_repository(tmp_path: Path) -> None:
    module = fake_module(tmp_path)
    CoreRepositoryRuntime(module).install()

    config = module.load_config()

    assert config["application"]["build"] == "V1.13A4G-VENUE-SERVICE"
    assert config["application"]["rules_edition"] == "NFHS"


def test_runtime_generates_and_persists_missing_secret_key(
    tmp_path: Path,
) -> None:
    module = fake_module(tmp_path)
    module.DEFAULT_SECURITY = {
        **module.DEFAULT_SECURITY,
        "secret_key": "",
    }

    runtime = CoreRepositoryRuntime(module).install()

    assert module.app.secret_key
    assert (
        runtime.security.load()["secret_key"]
        == module.app.secret_key
    )
