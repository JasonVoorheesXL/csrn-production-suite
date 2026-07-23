from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Callable

from persistence_engine import JsonPersistenceEngine, PersistencePolicy


ROSTER_POLICY = PersistencePolicy(
    backup_count=10,
    block_empty_replacement=True,
    block_large_count_drop=True,
    max_count_drop_ratio=0.75,
)


def validate_rosters(data: Any) -> bool:
    """Validate the persisted roster collection without enforcing UI policy."""
    if isinstance(data, dict):
        data = data.get("rosters")
    if not isinstance(data, list):
        return False

    roster_ids: set[str] = set()
    for roster in data:
        if not isinstance(roster, dict):
            return False
        roster_id = str(roster.get("id", "")).strip()
        if not roster_id or roster_id in roster_ids:
            return False
        roster_ids.add(roster_id)

        players = roster.get("players", [])
        if not isinstance(players, list):
            return False
        player_ids: set[str] = set()
        for player in players:
            if not isinstance(player, dict):
                return False
            player_id = str(player.get("id", "")).strip()
            if not player_id or player_id in player_ids:
                return False
            player_ids.add(player_id)
    return True


class RosterStore:
    """Roster-specific persistence with destructive-write protection."""

    def __init__(self, path: Path, backup_root: Path) -> None:
        self.path = Path(path)
        self.engine = JsonPersistenceEngine(backup_root=Path(backup_root))

    def load(
        self,
        *,
        normalizer: Callable[[list[dict[str, Any]]], bool] | None = None,
    ) -> list[dict[str, Any]]:
        data = self.engine.load(self.path, [], validator=validate_rosters)
        items = data if isinstance(data, list) else data.get("rosters", [])
        items = copy.deepcopy(items)
        changed = bool(normalizer(items)) if normalizer else False
        if changed:
            self.save(items)
        return items

    def save(self, items: list[dict[str, Any]], *, force: bool = False) -> None:
        self.engine.save(
            self.path,
            items,
            validator=validate_rosters,
            policy=ROSTER_POLICY,
            force=force,
        )

    def delete_roster(self, roster_id: str) -> bool:
        items = self.load()
        remaining = [item for item in items if str(item.get("id")) != str(roster_id)]
        if len(remaining) == len(items):
            return False
        # Deleting the final roster is an explicit domain action, not an accidental
        # empty replacement. The persistence engine still snapshots the old file.
        self.save(remaining, force=not remaining)
        return True

    def reset_all(self) -> None:
        """Explicitly clear all roster data while preserving a recoverable backup."""
        self.save([], force=True)
