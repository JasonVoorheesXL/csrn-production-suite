from __future__ import annotations

import json
from pathlib import Path

import pytest

from core_repositories import (
    ConfigurationRepository,
    RepositoryValidationError,
    SecurityRepository,
    StateRepository,
)
from persistence_engine import DataCorruptionError, JsonPersistenceEngine


CONFIG_DEFAULTS = {
    "organization": {"name": "CSRN", "primary_color": "#C9203B"},
    "broadcast_defaults": {"sport": "Football", "timezone": "America/Chicago"},
    "folders": {"backups": "Data/Backups"},
    "obs": {"host": "127.0.0.1", "port": 4455},
    "application": {"version": "old", "build": "old-build", "schema_version": "1"},
}

STATE_DEFAULTS = {
    "broadcast_id": "",
    "home_score": 0,
    "visitor_score": 0,
    "next_play_number": 1,
    "history": [],
    "events": [],
    "correction_log": [],
    "crew": {},
}

SECURITY_DEFAULTS = {
    "pin_hash": "",
    "secret_key": "generated-secret",
    "failed_attempts": 0,
    "locked_until": 0,
}


def engine(tmp_path: Path) -> JsonPersistenceEngine:
    return JsonPersistenceEngine(
        tmp_path / "Data" / "Backups" / "Persistence",
        tmp_path / "Data" / "Backups" / "Quarantine",
    )


def test_configuration_load_merges_nested_defaults_without_discarding_user_values(tmp_path: Path) -> None:
    path = tmp_path / "Data" / "Settings" / "config.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps({
            "organization": {"name": "My Network"},
            "obs": {"port": 4466},
            "application": {"schema_version": "1"},
        }),
        encoding="utf-8",
    )
    repository = ConfigurationRepository(
        engine(tmp_path),
        path,
        CONFIG_DEFAULTS,
        runtime_identity={"version": "Version 1.13", "build": "V1.13-FOUNDATION"},
    )

    loaded = repository.load()

    assert loaded["organization"]["name"] == "My Network"
    assert loaded["organization"]["primary_color"] == "#C9203B"
    assert loaded["obs"]["host"] == "127.0.0.1"
    assert loaded["obs"]["port"] == 4466
    assert loaded["application"]["version"] == "Version 1.13"
    assert loaded["application"]["build"] == "V1.13-FOUNDATION"


def test_configuration_update_is_recursive_and_persisted(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    repository = ConfigurationRepository(engine(tmp_path), path, CONFIG_DEFAULTS)

    updated = repository.update({"obs": {"port": 4477}})

    assert updated["obs"]["host"] == "127.0.0.1"
    assert updated["obs"]["port"] == 4477
    assert json.loads(path.read_text(encoding="utf-8"))["obs"]["port"] == 4477


def test_configuration_migration_hook_advances_schema(tmp_path: Path) -> None:
    def migrate_v1(config: dict) -> dict:
        config["application"]["schema_version"] = "2"
        config["broadcast_defaults"]["visual_mode"] = "graphic"
        return config

    path = tmp_path / "config.json"
    repository = ConfigurationRepository(
        engine(tmp_path),
        path,
        CONFIG_DEFAULTS,
        migrations={"1": migrate_v1},
    )

    loaded = repository.load()

    assert loaded["application"]["schema_version"] == "2"
    assert loaded["broadcast_defaults"]["visual_mode"] == "graphic"

def test_configuration_runtime_identity_overrides_stale_saved_values(
    tmp_path: Path,
) -> None:
    path = tmp_path / "config.json"
    path.write_text(
        json.dumps(
            {
                "application": {
                    "version": "stale-version",
                    "build": "stale-build",
                }
            }
        ),
        encoding="utf-8",
    )

    repository = ConfigurationRepository(
        engine(tmp_path),
        path,
        CONFIG_DEFAULTS,
        runtime_identity={
            "version": "current-version",
            "build": "current-build",
        },
    )

    loaded = repository.load()

    assert loaded["application"]["version"] == "current-version"
    assert loaded["application"]["build"] == "current-build"

    repository.save(loaded)

    persisted = json.loads(path.read_text(encoding="utf-8"))

    assert persisted["application"]["version"] == "current-version"
    assert persisted["application"]["build"] == "current-build"


def test_corrupt_configuration_is_not_silently_replaced_without_backup(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text("{damaged", encoding="utf-8")
    repository = ConfigurationRepository(engine(tmp_path), path, CONFIG_DEFAULTS)

    with pytest.raises(DataCorruptionError):
        repository.load()

    assert path.read_text(encoding="utf-8") == "{damaged"
    assert list((tmp_path / "Data" / "Backups" / "Quarantine").glob("config-corrupt-*.json"))


def test_state_update_preserves_defaults_and_existing_values(tmp_path: Path) -> None:
    repository = StateRepository(engine(tmp_path), tmp_path / "state.json", STATE_DEFAULTS)
    repository.replace({"broadcast_id": "game-1", "home_score": 7})

    updated = repository.update({"visitor_score": 3})

    assert updated["broadcast_id"] == "game-1"
    assert updated["home_score"] == 7
    assert updated["visitor_score"] == 3
    assert updated["next_play_number"] == 1


def test_state_rejects_invalid_score_type(tmp_path: Path) -> None:
    repository = StateRepository(engine(tmp_path), tmp_path / "state.json", STATE_DEFAULTS)

    with pytest.raises(RepositoryValidationError):
        repository.save({**STATE_DEFAULTS, "home_score": "seven"})


def test_security_failed_attempt_workflow(tmp_path: Path) -> None:
    repository = SecurityRepository(engine(tmp_path), tmp_path / "security.json", SECURITY_DEFAULTS)

    failed = repository.record_failed_attempt(locked_until=1234.5)
    cleared = repository.clear_failed_attempts()

    assert failed["failed_attempts"] == 1
    assert failed["locked_until"] == 1234.5
    assert cleared["failed_attempts"] == 0
    assert cleared["locked_until"] == 0
    assert cleared["secret_key"] == "generated-secret"

def test_security_attempt_limit_resets_counter_and_sets_lockout(
    tmp_path: Path,
) -> None:
    repository = SecurityRepository(
        engine(tmp_path),
        tmp_path / "security.json",
        SECURITY_DEFAULTS,
    )

    first = repository.record_failed_attempt(
        max_attempts=3,
        locked_until=500,
    )
    second = repository.record_failed_attempt(
        max_attempts=3,
        locked_until=500,
    )
    third = repository.record_failed_attempt(
        max_attempts=3,
        locked_until=500,
    )

    assert first["failed_attempts"] == 1
    assert first["locked_until"] == 0

    assert second["failed_attempts"] == 2
    assert second["locked_until"] == 0

    assert third["failed_attempts"] == 0
    assert third["locked_until"] == 500
    assert third["secret_key"] == "generated-secret"


def test_security_credentials_are_updated_without_resetting_lockout_metadata(tmp_path: Path) -> None:
    repository = SecurityRepository(engine(tmp_path), tmp_path / "security.json", SECURITY_DEFAULTS)
    repository.record_failed_attempt(locked_until=500)

    updated = repository.update_credentials(pin_hash="hash", secret_key="new-secret")

    assert updated["pin_hash"] == "hash"
    assert updated["secret_key"] == "new-secret"
    assert updated["failed_attempts"] == 1
    assert updated["locked_until"] == 500


def test_security_rejects_negative_failed_attempts(tmp_path: Path) -> None:
    repository = SecurityRepository(engine(tmp_path), tmp_path / "security.json", SECURITY_DEFAULTS)

    with pytest.raises(RepositoryValidationError):
        repository.save({**SECURITY_DEFAULTS, "failed_attempts": -1})
