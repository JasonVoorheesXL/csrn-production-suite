from __future__ import annotations

import copy
from pathlib import Path
from threading import RLock
from typing import Any, Mapping

from file_cache_signature import FileCacheSignature, file_cache_signature
from persistence_engine import (
    DataCorruptionError,
    JsonPersistenceEngine,
    PersistencePolicy,
)


class SocialPostRepositoryValidationError(ValueError):
    """Raised when social-post data cannot be safely persisted."""


class SocialPostRepository:
    """Persistence boundary for social drafts, attempts, and audit history."""

    VALID_STATUSES = {"draft", "partial", "failed", "published", "cancelled"}

    def __init__(
        self,
        engine: JsonPersistenceEngine,
        path: Path,
        *,
        policy: PersistencePolicy | None = None,
    ) -> None:
        self.engine = engine
        self.path = Path(path)
        self.policy = policy or PersistencePolicy(backup_count=30)
        self._lock = RLock()
        self._cache: list[dict[str, Any]] | None = None
        self._cache_signature: FileCacheSignature | None = None

    @staticmethod
    def _extract(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            items = payload
        elif isinstance(payload, Mapping):
            items = payload.get("posts", [])
        else:
            raise SocialPostRepositoryValidationError(
                "Social post database must be a list or an object containing 'posts'."
            )
        if not isinstance(items, list):
            raise SocialPostRepositoryValidationError("The 'posts' value must be a list.")
        if any(not isinstance(item, dict) for item in items):
            raise SocialPostRepositoryValidationError(
                "Every social post record must be a JSON object."
            )
        return copy.deepcopy(items)

    @classmethod
    def validate_payload(cls, payload: Any) -> bool:
        try:
            items = cls._extract(payload)
        except SocialPostRepositoryValidationError:
            return False
        return cls.validate_items(items)

    @classmethod
    def validate_items(cls, items: list[dict[str, Any]]) -> bool:
        ids: set[str] = set()
        for item in items:
            post_id = str(item.get("id", "")).strip()
            if not post_id or post_id in ids:
                return False
            ids.add(post_id)
            if str(item.get("status", "draft")) not in cls.VALID_STATUSES:
                return False
            platforms = item.get("platforms", [])
            if not isinstance(platforms, list):
                return False
            attempts = item.get("attempts", [])
            if not isinstance(attempts, list):
                return False
        return True

    def _signature(self) -> FileCacheSignature | None:
        return file_cache_signature(self.path)

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
            if not self.validate_items(items):
                raise SocialPostRepositoryValidationError(
                    "Social post records failed validation."
                )
            if not isinstance(payload, list):
                self.save(items, force=not bool(items))
            else:
                self._cache = copy.deepcopy(items)
                self._cache_signature = self._signature()
            return copy.deepcopy(items)

    def save(
        self,
        posts: list[dict[str, Any]],
        *,
        force: bool = False,
    ) -> list[dict[str, Any]]:
        if not isinstance(posts, list) or not self.validate_items(posts):
            raise SocialPostRepositoryValidationError(
                "Social post database failed validation."
            )
        with self._lock:
            normalized = copy.deepcopy(posts)
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

    def get(self, post_id: str) -> dict[str, Any] | None:
        target = str(post_id or "").strip()
        return next(
            (
                copy.deepcopy(item)
                for item in self.load()
                if str(item.get("id", "")) == target
            ),
            None,
        )

    def invalidate_cache(self) -> None:
        with self._lock:
            self._cache = None
            self._cache_signature = None
