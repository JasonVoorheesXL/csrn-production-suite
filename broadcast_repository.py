from __future__ import annotations

import copy
from pathlib import Path
from threading import RLock
from typing import Any, Callable, Mapping

from file_cache_signature import FileCacheSignature, file_cache_signature
from persistence_engine import (
    DataCorruptionError,
    JsonPersistenceEngine,
    PersistencePolicy,
)


BroadcastNormalizer = Callable[[list[dict[str, Any]]], bool]


class BroadcastRepositoryValidationError(ValueError):
    """Raised when broadcast index data cannot be safely persisted."""


class BroadcastRepository:
    """Persistence boundary for the broadcast index.

    Legacy list payloads and wrapped ``{"broadcasts": [...]}`` payloads are
    accepted. The canonical on-disk representation remains a JSON list.

    Broadcast lifecycle and game-domain rules remain injectable so the
    repository does not become responsible for scoring, graphics, scheduling,
    or operator workflow behavior.
    """

    def __init__(
        self,
        engine: JsonPersistenceEngine,
        path: Path,
        *,
        normalizer: BroadcastNormalizer | None = None,
        policy: PersistencePolicy | None = None,
    ) -> None:
        self.engine = engine
        self.path = Path(path)
        self.normalizer = normalizer
        self.policy = policy or PersistencePolicy(backup_count=50)

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

            live_state = broadcast.get("live_state")

            if live_state is not None and not isinstance(
                live_state,
                dict,
            ):
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
