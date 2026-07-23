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


SponsorNormalizer = Callable[[list[dict[str, Any]]], bool]

_TRANSIENT_FIELDS = frozenset(
    {
        "effective_status",
        "contract_expired",
    }
)


class SponsorRepositoryValidationError(ValueError):
    """Raised when sponsor data cannot be safely persisted."""


class SponsorRepository:
    """Persistence boundary for the sponsor database.

    Legacy list payloads and wrapped ``{"sponsors": [...]}`` payloads are
    accepted. The canonical on-disk representation is a JSON list.

    Runtime-only calculated fields are removed before persistence so values
    such as contract status are recalculated by the application instead of
    becoming stale data.
    """

    def __init__(
        self,
        engine: JsonPersistenceEngine,
        path: Path,
        *,
        normalizer: SponsorNormalizer | None = None,
        policy: PersistencePolicy | None = None,
    ) -> None:
        self.engine = engine
        self.path = Path(path)
        self.normalizer = normalizer
        self.policy = policy or PersistencePolicy(backup_count=30)

        self._lock = RLock()
        self._cache: list[dict[str, Any]] | None = None
        self._cache_mtime_ns: int | None = None

    @staticmethod
    def _extract(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            items = payload
        elif isinstance(payload, Mapping):
            items = payload.get("sponsors", [])
        else:
            raise SponsorRepositoryValidationError(
                "Sponsor database must be a list or an object containing "
                "'sponsors'."
            )

        if not isinstance(items, list):
            raise SponsorRepositoryValidationError(
                "The 'sponsors' value must be a list."
            )

        if any(not isinstance(item, dict) for item in items):
            raise SponsorRepositoryValidationError(
                "Every sponsor record must be a JSON object."
            )

        return copy.deepcopy(items)

    @classmethod
    def validate_payload(cls, payload: Any) -> bool:
        try:
            items = cls._extract(payload)
        except SponsorRepositoryValidationError:
            return False

        return cls.validate_items(items)

    @staticmethod
    def validate_items(items: list[dict[str, Any]]) -> bool:
        sponsor_ids: set[str] = set()

        for sponsor in items:
            if not isinstance(sponsor, dict):
                return False

            sponsor_id = str(sponsor.get("id", "")).strip()

            if sponsor_id:
                if sponsor_id in sponsor_ids:
                    return False
                sponsor_ids.add(sponsor_id)

        return True

    def _mtime(self) -> int | None:
        try:
            return self.path.stat().st_mtime_ns
        except OSError:
            return None

    def _normalize(
        self,
        items: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], bool]:
        normalized = copy.deepcopy(items)
        changed = False

        for sponsor in normalized:
            for field in _TRANSIENT_FIELDS:
                if field in sponsor:
                    sponsor.pop(field, None)
                    changed = True

        if self.normalizer is not None:
            changed = bool(self.normalizer(normalized)) or changed

        if not self.validate_items(normalized):
            raise SponsorRepositoryValidationError(
                "Sponsor records failed validation after normalization."
            )

        return normalized, changed

    def load(self) -> list[dict[str, Any]]:
        with self._lock:
            mtime = self._mtime()

            if self._cache is not None and self._cache_mtime_ns == mtime:
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
                self._cache_mtime_ns = self._mtime()

            return copy.deepcopy(normalized)

    def save(
        self,
        sponsors: list[dict[str, Any]],
        *,
        force: bool = False,
    ) -> list[dict[str, Any]]:
        if not isinstance(sponsors, list):
            raise SponsorRepositoryValidationError(
                "Sponsor database must be a list."
            )

        with self._lock:
            normalized, _ = self._normalize(sponsors)

            self.engine.save(
                self.path,
                normalized,
                validator=self.validate_payload,
                policy=self.policy,
                force=force,
            )

            self._cache = copy.deepcopy(normalized)
            self._cache_mtime_ns = self._mtime()

            return copy.deepcopy(normalized)

    def get(self, sponsor_id: str) -> dict[str, Any] | None:
        target = str(sponsor_id or "").strip()

        return next(
            (
                copy.deepcopy(sponsor)
                for sponsor in self.load()
                if str(sponsor.get("id", "")).strip() == target
            ),
            None,
        )

    def invalidate_cache(self) -> None:
        with self._lock:
            self._cache = None
            self._cache_mtime_ns = None