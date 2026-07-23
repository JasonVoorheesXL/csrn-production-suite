from __future__ import annotations

import copy
from pathlib import Path
from threading import RLock
from typing import Any, Callable, Mapping

from persistence_engine import DataCorruptionError, JsonPersistenceEngine, PersistencePolicy

RosterNormalizer = Callable[[list[dict[str, Any]]], bool]


class RosterRepositoryValidationError(ValueError):
    """Raised when roster data cannot be safely persisted."""


class RosterRepository:
    """Persistence boundary for the roster database.

    Legacy list payloads and wrapped ``{"rosters": [...]}`` payloads are read.
    The canonical on-disk representation remains a JSON list so existing CSRN
    exports and upgrade tooling remain compatible.
    """

    def __init__(
        self,
        engine: JsonPersistenceEngine,
        path: Path,
        *,
        normalizer: RosterNormalizer | None = None,
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
            items = payload.get("rosters", [])
        else:
            raise RosterRepositoryValidationError(
                "Roster database must be a list or an object containing 'rosters'."
            )
        if not isinstance(items, list):
            raise RosterRepositoryValidationError("The 'rosters' value must be a list.")
        if any(not isinstance(item, dict) for item in items):
            raise RosterRepositoryValidationError("Every roster record must be a JSON object.")
        return copy.deepcopy(items)

    @classmethod
    def validate_payload(cls, payload: Any) -> bool:
        try:
            items = cls._extract(payload)
        except RosterRepositoryValidationError:
            return False
        return cls.validate_items(items)

    @staticmethod
    def validate_items(items: list[dict[str, Any]]) -> bool:
        roster_ids: set[str] = set()
        for roster in items:
            roster_id = str(roster.get("id", "")).strip()
            if roster_id:
                if roster_id in roster_ids:
                    return False
                roster_ids.add(roster_id)
            players = roster.get("players", [])
            if not isinstance(players, list) or any(not isinstance(player, dict) for player in players):
                return False
            player_ids: set[str] = set()
            for player in players:
                player_id = str(player.get("id", "")).strip()
                if player_id:
                    if player_id in player_ids:
                        return False
                    player_ids.add(player_id)
        return True

    def _mtime(self) -> int | None:
        try:
            return self.path.stat().st_mtime_ns
        except OSError:
            return None

    def _normalize(self, items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], bool]:
        normalized = copy.deepcopy(items)
        changed = bool(self.normalizer(normalized)) if self.normalizer is not None else False
        if not self.validate_items(normalized):
            raise RosterRepositoryValidationError("Roster records failed validation after normalization.")
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
                # The persistence engine has already quarantined the damaged file.
                # If no valid backup exists, create a safe canonical empty database.
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

    def save(self, rosters: list[dict[str, Any]], *, force: bool = False) -> list[dict[str, Any]]:
        if not isinstance(rosters, list):
            raise RosterRepositoryValidationError("Roster database must be a list.")
        with self._lock:
            normalized, _ = self._normalize(rosters)
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

    def get(self, roster_id: str) -> dict[str, Any] | None:
        target = str(roster_id or "").strip()
        return next(
            (copy.deepcopy(roster) for roster in self.load() if str(roster.get("id", "")) == target),
            None,
        )

    def invalidate_cache(self) -> None:
        with self._lock:
            self._cache = None
            self._cache_mtime_ns = None
