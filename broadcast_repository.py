from __future__ import annotations

import copy
from pathlib import Path
from threading import RLock
from typing import Any, Callable, Mapping

from broadcast_detail_store import HEAVY_BROADCAST_FIELDS, has_heavy_fields
from file_cache_signature import FileCacheSignature, file_cache_signature
from persistence_engine import (
    DataCorruptionError,
    JsonPersistenceEngine,
    PersistencePolicy,
)


BroadcastNormalizer = Callable[[list[dict[str, Any]]], bool]
# Moves one row's heavy fields (live_state / final_state_archive) into its
# detail file and verifies them there. ``migrating`` is True when the row came
# from a legacy on-disk index rather than from a caller's save().
HeavyFieldSpiller = Callable[[dict[str, Any], bool], None]
# Copies the legacy index file somewhere safe before the first migration.
MigrationBackup = Callable[[Path], None]


class BroadcastRepositoryValidationError(ValueError):
    """Raised when broadcast index data cannot be safely persisted."""


class BroadcastRepository:
    """Persistence boundary for the broadcast index.

    Legacy list payloads and wrapped ``{"broadcasts": [...]}`` payloads are
    accepted. The canonical on-disk representation remains a JSON list.

    Broadcast lifecycle and game-domain rules remain injectable so the
    repository does not become responsible for scoring, graphics, scheduling,
    or operator workflow behavior.

    When ``spill_heavy`` is supplied the index is kept lightweight: a row's
    live_state / final_state_archive are handed to ``spill_heavy`` (which
    writes them to the broadcast's detail file) and stripped before the index
    is written. A legacy index that still embeds them is migrated the same way
    on load, after ``backup_before_migration`` has copied it. If the backup or
    any spill fails, the legacy rows are returned unchanged and the file is
    left alone, so no game state is ever dropped.
    """

    def __init__(
        self,
        engine: JsonPersistenceEngine,
        path: Path,
        *,
        normalizer: BroadcastNormalizer | None = None,
        policy: PersistencePolicy | None = None,
        spill_heavy: HeavyFieldSpiller | None = None,
        backup_before_migration: MigrationBackup | None = None,
    ) -> None:
        self.engine = engine
        self.path = Path(path)
        self.normalizer = normalizer
        self.spill_heavy = spill_heavy
        self.backup_before_migration = backup_before_migration
        self.policy = policy or PersistencePolicy(
            backup_count=50,
            # Confirmed no legitimate workflow relies on saving an empty/
            # drastically-smaller broadcast database without force=True --
            # every save call site (broadcast_service.py) only adds,
            # updates, or single-item-deletes a broadcast.
            block_empty_replacement=True,
            block_large_count_drop=True,
        )

        self._lock = RLock()
        self._cache: list[dict[str, Any]] | None = None
        self._cache_signature: FileCacheSignature | None = None

    @staticmethod
    def _extract(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            items = payload
        elif isinstance(payload, Mapping):
            items = payload.get("broadcasts", [])
        else:
            raise BroadcastRepositoryValidationError(
                "Broadcast index must be a list or an object containing "
                "'broadcasts'."
            )

        if not isinstance(items, list):
            raise BroadcastRepositoryValidationError(
                "The 'broadcasts' value must be a list."
            )

        if any(not isinstance(item, dict) for item in items):
            raise BroadcastRepositoryValidationError(
                "Every broadcast record must be a JSON object."
            )

        return copy.deepcopy(items)

    @classmethod
    def validate_payload(cls, payload: Any) -> bool:
        try:
            items = cls._extract(payload)
        except BroadcastRepositoryValidationError:
            return False

        return cls.validate_items(items)

    @staticmethod
    def validate_items(items: list[dict[str, Any]]) -> bool:
        broadcast_ids: set[str] = set()

        for broadcast in items:
            if not isinstance(broadcast, dict):
                return False

            broadcast_id = str(
                broadcast.get("broadcast_id", "")
            ).strip()

            if broadcast_id:
                if broadcast_id in broadcast_ids:
                    return False

                broadcast_ids.add(broadcast_id)

            # Legacy rows may still embed the heavy state fields; when they
            # do, each must be an object.
            for field in HEAVY_BROADCAST_FIELDS:
                value = broadcast.get(field)

                if value is not None and not isinstance(value, dict):
                    return False

        return True

    def _signature(self) -> FileCacheSignature | None:
        return file_cache_signature(self.path)

    def _normalize(
        self,
        items: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], bool]:
        normalized = copy.deepcopy(items)

        changed = (
            bool(self.normalizer(normalized))
            if self.normalizer is not None
            else False
        )

        if not self.validate_items(normalized):
            raise BroadcastRepositoryValidationError(
                "Broadcast records failed validation after normalization."
            )

        return normalized, changed

    def load(self) -> list[dict[str, Any]]:
        with self._lock:
            signature = self._signature()

            if (
                self._cache is not None
                and self._cache_signature == signature
            ):
                return copy.deepcopy(self._cache)

            try:
                payload = self.engine.load(
                    self.path,
                    [],
                    validator=self.validate_payload,
                    create_if_missing=True,
                    restore_recovered_file=True,
                )
            except DataCorruptionError:
                self.engine.save(
                    self.path,
                    [],
                    validator=self.validate_payload,
                    policy=self.policy,
                    force=True,
                )
                payload = []

            items = self._extract(payload)
            normalized, changed = self._normalize(items)

            if self.spill_heavy is not None and any(
                self._needs_spill(row) for row in normalized
            ):
                migrated = self._migrate_heavy_rows(normalized)

                if migrated is None:
                    # Leave the legacy file and cache untouched; callers
                    # still get the full rows, so nothing is lost.
                    return copy.deepcopy(normalized)

                return self.save(migrated)

            if changed or not isinstance(payload, list):
                self.save(
                    normalized,
                    force=not bool(normalized),
                )
            else:
                self._cache = copy.deepcopy(normalized)
                self._cache_signature = self._signature()

            return copy.deepcopy(normalized)

    def save(
        self,
        broadcasts: list[dict[str, Any]],
        *,
        force: bool = False,
    ) -> list[dict[str, Any]]:
        if not isinstance(broadcasts, list):
            raise BroadcastRepositoryValidationError(
                "Broadcast index must be a list."
            )

        with self._lock:
            normalized, _ = self._normalize(broadcasts)

            if self.spill_heavy is not None:
                normalized = [
                    self._spill_row(row, migrating=False)
                    for row in normalized
                ]

            self.engine.save(
                self.path,
                normalized,
                validator=self.validate_payload,
                policy=self.policy,
                force=force,
            )

            self._cache = copy.deepcopy(normalized)
            self._cache_signature = self._signature()

            return copy.deepcopy(normalized)

    @staticmethod
    def _needs_spill(row: Mapping[str, Any]) -> bool:
        # A row without an id has no detail file to hold its state, so it
        # keeps whatever it carries.
        return has_heavy_fields(row) and bool(
            str(row.get("broadcast_id", "")).strip()
        )

    def _spill_row(
        self,
        row: dict[str, Any],
        *,
        migrating: bool,
    ) -> dict[str, Any]:
        if not self._needs_spill(row):
            return row

        assert self.spill_heavy is not None
        self.spill_heavy(copy.deepcopy(row), migrating)

        return {
            key: value
            for key, value in row.items()
            if key not in HEAVY_BROADCAST_FIELDS
        }

    def _migrate_heavy_rows(
        self,
        items: list[dict[str, Any]],
    ) -> list[dict[str, Any]] | None:
        try:
            if self.backup_before_migration is not None:
                self.backup_before_migration(self.path)

            return [
                self._spill_row(row, migrating=True)
                for row in items
            ]
        except Exception:
            return None

    def get(
        self,
        broadcast_id: str,
    ) -> dict[str, Any] | None:
        target = str(broadcast_id or "").strip()

        return next(
            (
                copy.deepcopy(broadcast)
                for broadcast in self.load()
                if str(
                    broadcast.get("broadcast_id", "")
                ).strip()
                == target
            ),
            None,
        )

    def invalidate_cache(self) -> None:
        with self._lock:
            self._cache = None
            self._cache_signature = None
