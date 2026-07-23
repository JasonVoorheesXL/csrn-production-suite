from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from persistence_engine import JsonPersistenceEngine, PersistencePolicy


SchoolNormalizer = Callable[[dict[str, Any], list[dict[str, Any]]], dict[str, Any]]
CollectionNormalizer = Callable[[list[dict[str, Any]]], bool]


class SchoolRepositoryValidationError(ValueError):
    """Raised when school data cannot be safely persisted."""


class SchoolRepository:
    """Persistence boundary for the school database.

    The repository accepts both legacy list payloads and wrapped
    ``{"schools": [...]}`` payloads, but writes the canonical list format used
    by the current CSRN application. Domain-specific normalization remains
    injectable so existing CSRN ID and logo metadata behavior can be preserved
    without moving business rules into the persistence layer.
    """

    def __init__(
        self,
        engine: JsonPersistenceEngine,
        path: Path,
        *,
        school_normalizer: SchoolNormalizer | None = None,
        collection_normalizer: CollectionNormalizer | None = None,
        policy: PersistencePolicy | None = None,
    ) -> None:
        self.engine = engine
        self.path = Path(path)
        self.school_normalizer = school_normalizer
        self.collection_normalizer = collection_normalizer
        self.policy = policy or PersistencePolicy(backup_count=20)

    @staticmethod
    def _extract(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            items = payload
        elif isinstance(payload, Mapping):
            items = payload.get("schools", [])
        else:
            raise SchoolRepositoryValidationError("School database must be a list or an object containing 'schools'.")

        if not isinstance(items, list):
            raise SchoolRepositoryValidationError("The 'schools' value must be a list.")
        if any(not isinstance(item, dict) for item in items):
            raise SchoolRepositoryValidationError("Every school record must be a JSON object.")
        return copy.deepcopy(items)

    @classmethod
    def validate_payload(cls, payload: Any) -> bool:
        try:
            cls._extract(payload)
        except SchoolRepositoryValidationError:
            return False
        return True

    @staticmethod
    def validate_items(items: Iterable[dict[str, Any]]) -> bool:
        seen: set[str] = set()
        for item in items:
            if not isinstance(item, dict):
                return False
            school_id = str(item.get("id", "")).strip()
            if school_id:
                if school_id in seen:
                    return False
                seen.add(school_id)
        return True

    def _normalize(self, items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], bool]:
        normalized = copy.deepcopy(items)
        changed = False

        if self.collection_normalizer is not None:
            changed = bool(self.collection_normalizer(normalized)) or changed

        if self.school_normalizer is not None:
            for index, school in enumerate(normalized):
                before = copy.deepcopy(school)
                result = self.school_normalizer(school, normalized)
                if not isinstance(result, dict):
                    raise SchoolRepositoryValidationError("School normalizer must return a dictionary.")
                normalized[index] = result
                changed = changed or result != before

        if not self.validate_items(normalized):
            raise SchoolRepositoryValidationError("School records failed validation after normalization.")
        return normalized, changed

    def load(self) -> list[dict[str, Any]]:
        payload = self.engine.load(
            self.path,
            [],
            validator=self.validate_payload,
            create_if_missing=True,
            restore_recovered_file=True,
        )
        items = self._extract(payload)
        normalized, changed = self._normalize(items)
        if changed:
            self.save(normalized)
        return copy.deepcopy(normalized)

    def save(self, schools: list[dict[str, Any]], *, force: bool = False) -> list[dict[str, Any]]:
        if not isinstance(schools, list):
            raise SchoolRepositoryValidationError("School database must be a list.")
        normalized, _ = self._normalize(schools)
        self.engine.save(
            self.path,
            normalized,
            validator=self.validate_payload,
            policy=self.policy,
            force=force,
        )
        return copy.deepcopy(normalized)

    def get(self, school_id: str) -> dict[str, Any] | None:
        target = str(school_id or "").strip()
        return next((copy.deepcopy(item) for item in self.load() if str(item.get("id", "")) == target), None)
