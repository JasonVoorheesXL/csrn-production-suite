from __future__ import annotations

import copy
import threading
from pathlib import Path
from typing import Any, Callable, Mapping

from persistence_engine import JsonPersistenceEngine, PersistencePolicy


Validator = Callable[[Any], bool]


class RepositoryValidationError(ValueError):
    """Raised when a repository receives invalid domain data."""


def _deep_merge(defaults: Mapping[str, Any], incoming: Mapping[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = copy.deepcopy(dict(defaults))
    for key, value in incoming.items():
        if isinstance(value, Mapping) and isinstance(merged.get(key), Mapping):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _is_json_dict(value: Any) -> bool:
    return isinstance(value, dict)


class JsonObjectRepository:
    """Repository for a single JSON object backed by JsonPersistenceEngine."""

    def __init__(
        self,
        engine: JsonPersistenceEngine,
        path: Path,
        defaults: Mapping[str, Any],
        *,
        validator: Validator | None = None,
        policy: PersistencePolicy | None = None,
    ) -> None:
        self.engine = engine
        self.path = Path(path)
        self.defaults = copy.deepcopy(dict(defaults))
        self.validator = validator or _is_json_dict
        self.policy = policy or PersistencePolicy(backup_count=10)

    def load(self) -> dict[str, Any]:
        raw = self.engine.load(
            self.path,
            self.defaults,
            validator=self.validator,
            create_if_missing=True,
            restore_recovered_file=True,
        )
        if not isinstance(raw, dict):
            raise RepositoryValidationError(f"Expected an object in {self.path}.")
        return copy.deepcopy(raw)

    def save(self, value: Mapping[str, Any], *, force: bool = False) -> dict[str, Any]:
        candidate = copy.deepcopy(dict(value))
        if not self.validator(candidate):
            raise RepositoryValidationError(f"Invalid data for {self.path}.")
        self.engine.save(
            self.path,
            candidate,
            validator=self.validator,
            policy=self.policy,
            force=force,
        )
        return copy.deepcopy(candidate)

    def reset(self) -> dict[str, Any]:
        return self.save(self.defaults, force=True)


class ConfigurationRepository(JsonObjectRepository):
    """Configuration storage with recursive default merging and migration hooks."""

    def __init__(
        self,
        engine: JsonPersistenceEngine,
        path: Path,
        defaults: Mapping[str, Any],
        *,
        runtime_identity: Mapping[str, str] | None = None,
        migrations: Mapping[str, Callable[[dict[str, Any]], dict[str, Any]]] | None = None,
    ) -> None:
        super().__init__(engine, path, defaults, validator=self.validate)
        self.runtime_identity = dict(runtime_identity or {})
        self.migrations = dict(migrations or {})

    @staticmethod
    def validate(value: Any) -> bool:
        if not isinstance(value, dict):
            return False
        required_sections = ("organization", "broadcast_defaults", "folders", "obs", "application")
        if any(section in value and not isinstance(value[section], dict) for section in required_sections):
            return False
        application = value.get("application", {})
        if application and any(
            key in application and not isinstance(application[key], str)
            for key in ("version", "build")
        ):
            return False
        return True

    def load(self) -> dict[str, Any]:
        raw = super().load()
        merged = _deep_merge(self.defaults, raw)
        merged = self._apply_migrations(merged)
        application = merged.setdefault("application", {})
        for key in ("version", "build"):
            if self.runtime_identity.get(key):
                application[key] = self.runtime_identity[key]
        return merged

    def save(self, value: Mapping[str, Any], *, force: bool = False) -> dict[str, Any]:
        merged = _deep_merge(self.defaults, dict(value))
        application = merged.setdefault("application", {})
        for key in ("version", "build"):
            if self.runtime_identity.get(key):
                application[key] = self.runtime_identity[key]
        return super().save(merged, force=force)

    def update(self, patch: Mapping[str, Any]) -> dict[str, Any]:
        current = self.load()
        updated = _deep_merge(current, patch)
        return self.save(updated)

    def _apply_migrations(self, config: dict[str, Any]) -> dict[str, Any]:
        current = copy.deepcopy(config)
        application = current.setdefault("application", {})
        migration_id = str(application.get("schema_version", ""))
        visited: set[str] = set()
        while migration_id in self.migrations and migration_id not in visited:
            visited.add(migration_id)
            current = self.migrations[migration_id](copy.deepcopy(current))
            if not self.validate(current):
                raise RepositoryValidationError(
                    f"Configuration migration {migration_id!r} produced invalid data."
                )
            migration_id = str(current.setdefault("application", {}).get("schema_version", ""))
        return current


class StateRepository(JsonObjectRepository):
    """Active application and broadcast state storage."""

    def __init__(self, engine: JsonPersistenceEngine, path: Path, defaults: Mapping[str, Any]) -> None:
        super().__init__(engine, path, defaults, validator=self.validate)

    @staticmethod
    def validate(value: Any) -> bool:
        if not isinstance(value, dict):
            return False
        numeric_fields = ("home_score", "visitor_score", "next_play_number")
        if any(field in value and (not isinstance(value[field], int) or isinstance(value[field], bool)) for field in numeric_fields):
            return False
        list_fields = ("history", "events", "correction_log")
        if any(field in value and not isinstance(value[field], list) for field in list_fields):
            return False
        if "crew" in value and not isinstance(value["crew"], dict):
            return False
        if "broadcast_id" in value and not isinstance(value["broadcast_id"], str):
            return False
        return True

    def load(self) -> dict[str, Any]:
        return _deep_merge(self.defaults, super().load())

    def replace(self, state: Mapping[str, Any]) -> dict[str, Any]:
        return self.save(_deep_merge(self.defaults, state))

    def update(self, patch: Mapping[str, Any]) -> dict[str, Any]:
        current = self.load()
        return self.save(_deep_merge(current, patch))


class LocalMirroredStateRepository:
    """Local game-day state authority with an asynchronous project mirror."""

    def __init__(
        self,
        engine: JsonPersistenceEngine,
        *,
        authority_path: Path,
        mirror_path: Path,
        defaults: Mapping[str, Any],
    ) -> None:
        self.engine = engine
        self.path = Path(authority_path)
        self.mirror_path = Path(mirror_path)
        self.defaults = copy.deepcopy(dict(defaults))
        self._authority = StateRepository(engine, self.path, defaults)
        self._mirror = StateRepository(engine, self.mirror_path, defaults)
        self._mirror_lock = threading.Lock()
        self._mirror_pending: dict[str, Any] | None = None
        self._mirror_worker: threading.Thread | None = None
        self._recover_authority()

    @staticmethod
    def _revision(state: Mapping[str, Any] | None) -> int:
        if not isinstance(state, Mapping):
            return 0
        try:
            return int(state.get("state_revision", 0) or 0)
        except (TypeError, ValueError):
            return 0

    def _load_existing(self, repository: StateRepository) -> dict[str, Any] | None:
        if not repository.path.exists():
            return None
        try:
            return repository.load()
        except Exception:
            return None

    def _recover_authority(self) -> None:
        local = self._load_existing(self._authority)
        mirror = self._load_existing(self._mirror)
        local_revision = self._revision(local)
        mirror_revision = self._revision(mirror)
        if local is None and mirror is None:
            self._authority.replace(self.defaults)
            self._queue_mirror(self.defaults)
            return
        if mirror is not None and mirror_revision > local_revision:
            self._authority.replace(mirror)
            return
        if local is not None:
            self._queue_mirror(local)

    def load(self) -> dict[str, Any]:
        return self._authority.load()

    def replace(self, state: Mapping[str, Any]) -> dict[str, Any]:
        stored = self._authority.replace(state)
        self._queue_mirror(stored)
        return stored

    def update(self, patch: Mapping[str, Any]) -> dict[str, Any]:
        current = self.load()
        return self.replace(_deep_merge(current, patch))

    def _queue_mirror(self, state: Mapping[str, Any]) -> None:
        snapshot = copy.deepcopy(dict(state))
        with self._mirror_lock:
            self._mirror_pending = snapshot
            if self._mirror_worker is not None:
                return
            self._mirror_worker = threading.Thread(
                target=self._mirror_loop,
                name="csrn-state-drive-mirror",
                daemon=True,
            )
            self._mirror_worker.start()

    def _mirror_loop(self) -> None:
        while True:
            with self._mirror_lock:
                snapshot = self._mirror_pending
                self._mirror_pending = None
            if snapshot is None:
                with self._mirror_lock:
                    if self._mirror_pending is None:
                        self._mirror_worker = None
                        return
                continue
            try:
                self._mirror.replace(snapshot)
            except Exception:
                pass


class SecurityRepository(JsonObjectRepository):
    """Security metadata storage. Secret values are preserved exactly as supplied."""

    def __init__(self, engine: JsonPersistenceEngine, path: Path, defaults: Mapping[str, Any]) -> None:
        super().__init__(engine, path, defaults, validator=self.validate)

    @staticmethod
    def validate(value: Any) -> bool:
        if not isinstance(value, dict):
            return False
        for field in ("pin_hash", "secret_key"):
            if field in value and not isinstance(value[field], str):
                return False
        for field in ("failed_attempts", "locked_until"):
            if field in value and (not isinstance(value[field], (int, float)) or isinstance(value[field], bool)):
                return False
        if "failed_attempts" in value and value["failed_attempts"] < 0:
            return False
        return True

    def load(self) -> dict[str, Any]:
        return _deep_merge(self.defaults, super().load())

    def record_failed_attempt(
        self,
        *,
        max_attempts: int | None = None,
        locked_until: float | None = None,
    ) -> dict[str, Any]:
        """Record a failed login and apply lockout at the attempt limit."""

        if max_attempts is not None and max_attempts < 1:
            raise ValueError("max_attempts must be at least 1.")

        security = self.load()
        attempts = int(security.get("failed_attempts", 0)) + 1
        security["failed_attempts"] = attempts

        if max_attempts is not None and attempts >= max_attempts:
            security["failed_attempts"] = 0
            if locked_until is not None:
                security["locked_until"] = locked_until
        elif max_attempts is None and locked_until is not None:
            security["locked_until"] = locked_until

        return self.save(security)

    def clear_failed_attempts(self) -> dict[str, Any]:
        security = self.load()
        security["failed_attempts"] = 0
        security["locked_until"] = 0
        return self.save(security)

    def update_credentials(self, *, pin_hash: str | None = None, secret_key: str | None = None) -> dict[str, Any]:
        security = self.load()
        if pin_hash is not None:
            security["pin_hash"] = pin_hash
        if secret_key is not None:
            security["secret_key"] = secret_key
        return self.save(security)
