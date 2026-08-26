from __future__ import annotations

import copy
from pathlib import Path
from threading import RLock
from typing import Any, Callable, Mapping

from persistence_engine import (
    DataCorruptionError,
    JsonPersistenceEngine,
    PersistencePolicy,
)


VenueNormalizer = Callable[[list[dict[str, Any]]], bool]


class VenueRepositoryValidationError(ValueError):
    """Raised when venue data cannot be safely persisted."""


class VenueRepository:
    """Persistence boundary for the venue database.

    Legacy list payloads and wrapped ``{"venues": [...]}`` payloads are
    accepted. The canonical on-disk representation is a JSON list.
    """

    def __init__(
        self,
        engine: JsonPersistenceEngine,
        path: Path,
        *,
        normalizer: VenueNormalizer | None = None,
        policy: PersistencePolicy | None = None,
    ) -> None:
        self.engine = engine
        self.path = Path(path)
        self.normalizer = normalizer
        self.policy = policy or PersistencePolicy(
            backup_count=30,
            # Confirmed no legitimate workflow relies on saving an empty/
            # drastically-smaller venue database without force=True --
            # every save call site only adds, updates, or single-item-
            # deletes a venue.
            block_empty_replacement=True,
            block_large_count_drop=True,
        )

        self._lock = RLock()
        self._cache: list[dict[str, Any]] | None = None
        self._cache_signature: tuple[int, int, int] | None = None

    @staticmethod
    def _extract(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            items = payload
        elif isinstance(payload, Mapping):
            items = payload.get("venues", [])
        else:
            raise VenueRepositoryValidationError(
                "Venue database must be a list or an object containing "
                "'venues'."
            )

        if not isinstance(items, list):
            raise VenueRepositoryValidationError(
                "The 'venues' value must be a list."
            )

        if any(not isinstance(item, dict) for item in items):
            raise VenueRepositoryValidationError(
                "Every venue record must be a JSON object."
            )

        return copy.deepcopy(items)

    @classmethod
    def validate_payload(cls, payload: Any) -> bool:
        try:
            items = cls._extract(payload)
        except VenueRepositoryValidationError:
            return False

        return cls.validate_items(items)

    @staticmethod
    def validate_items(items: list[dict[str, Any]]) -> bool:
        venue_ids: set[str] = set()

        for venue in items:
            if not isinstance(venue, dict):
                return False

            venue_id = str(venue.get("id", "")).strip()

            if venue_id:
                if venue_id in venue_ids:
                    return False
                venue_ids.add(venue_id)

        return True

    def _signature(self) -> tuple[int, int, int] | None:
        try:
            stat = self.path.stat()
            return (stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size)
        except OSError:
            return None

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
            raise VenueRepositoryValidationError(
                "Venue records failed validation after normalization."
            )

        return normalized, changed

    def load(self) -> list[dict[str, Any]]:
        with self._lock:
            signature = self._signature()

            if self._cache is not None and self._cache_signature == signature:
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
                self.save(normalized, force=not bool(normalized))
            else:
                self._cache = copy.deepcopy(normalized)
                self._cache_signature = self._signature()

            return copy.deepcopy(normalized)

    def save(
        self,
        venues: list[dict[str, Any]],
        *,
        force: bool = False,
    ) -> list[dict[str, Any]]:
        if not isinstance(venues, list):
            raise VenueRepositoryValidationError(
                "Venue database must be a list."
            )

        with self._lock:
            normalized, _ = self._normalize(venues)

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

    def get(self, venue_id: str) -> dict[str, Any] | None:
        target = str(venue_id or "").strip()

        return next(
            (
                copy.deepcopy(venue)
                for venue in self.load()
                if str(venue.get("id", "")).strip() == target
            ),
            None,
        )

    def invalidate_cache(self) -> None:
        with self._lock:
            self._cache = None
            self._cache_signature = None
