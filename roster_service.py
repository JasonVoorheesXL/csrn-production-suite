from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field
from typing import Any, Callable


Roster = dict[str, Any]
School = dict[str, Any]
Player = dict[str, Any]
RosterLoader = Callable[[], list[Roster]]
RosterSaver = Callable[[list[Roster]], None]
SchoolLoader = Callable[[], list[School]]
Clock = Callable[[], float]


@dataclass(frozen=True)
class RosterResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.code == "OK"


class RosterService:
    """Roster-domain behavior independent of Flask routes."""

    UPDATE_FIELDS = (
        "school_id",
        "sport",
        "season",
        "level",
        "division",
    )
    PLAYER_STRING_FIELDS = (
        "number",
        "first_name",
        "last_name",
        "preferred_name",
        "position",
        "secondary_position",
        "grade",
        "height",
        "weight",
        "pronunciation",
        "headshot",
    )
    PLAYER_BOOLEAN_FIELDS = (
        "captain",
        "starter",
        "pronunciation_verified",
    )

    def __init__(
        self,
        *,
        load_rosters: RosterLoader,
        save_rosters: RosterSaver,
        load_schools: SchoolLoader,
        clock: Clock | None = None,
    ) -> None:
        self._load_rosters = load_rosters
        self._save_rosters = save_rosters
        self._load_schools = load_schools
        self._clock = clock or time.time

    @staticmethod
    def normalize_roster_id(value: str) -> str:
        cleaned = "".join(
            character.lower() if character.isalnum() else "-"
            for character in str(value or "").strip()
        )
        while "--" in cleaned:
            cleaned = cleaned.replace("--", "-")
        return cleaned.strip("-") or "roster"

    @classmethod
    def normalize_player_id(cls, value: str) -> str:
        return cls.normalize_roster_id(value)

    @staticmethod
    def summary(
        roster: Roster,
        schools: list[School] | None = None,
    ) -> Roster:
        school_list = schools or []
        school = next(
            (
                item
                for item in school_list
                if str(item.get("id", ""))
                == str(roster.get("school_id", ""))
            ),
            {},
        )
        players = (
            roster.get("players", [])
            if isinstance(roster.get("players"), list)
            else []
        )
        payload = copy.deepcopy(roster)
        payload.update(
            {
                "school_name": (
                    school.get("broadcast_name")
                    or school.get("official_name")
                    or roster.get("school_id", "Unknown School")
                ),
                "active_count": sum(
                    1
                    for player in players
                    if str(player.get("status", "active")).lower()
                    == "active"
                ),
                "inactive_count": sum(
                    1
                    for player in players
                    if str(player.get("status", "active")).lower()
                    == "inactive"
                ),
                "player_count": len(players),
            }
        )
        return payload

    def list_rosters(self) -> list[Roster]:
        schools = self._load_schools()
        return [
            self.summary(roster, schools)
            for roster in self._load_rosters()
        ]

    def read(self, roster_id: str) -> RosterResult:
        roster = self._find(self._load_rosters(), roster_id)
        if roster is None:
            return RosterResult("ROSTER_NOT_FOUND")
        return RosterResult(
            "OK",
            {"roster": self.summary(roster, self._load_schools())},
        )

    def create(self, incoming: Roster) -> RosterResult:
        incoming = copy.deepcopy(incoming)
        school_id = str(incoming.get("school_id", "")).strip()
        sport = str(incoming.get("sport", "Football")).strip() or "Football"
        season = str(incoming.get("season", "")).strip()
        level = str(incoming.get("level", "Varsity")).strip() or "Varsity"
        division = str(incoming.get("division", "Boys")).strip() or "Boys"

        if not school_id or not season:
            return RosterResult("SCHOOL_AND_SEASON_REQUIRED")

        rosters = self._load_rosters()
        schools = self._load_schools()
        duplicate = next(
            (
                roster
                for roster in rosters
                if str(roster.get("school_id", "")) == school_id
                and str(roster.get("sport", "")).lower() == sport.lower()
                and str(roster.get("season", "")) == season
                and str(roster.get("level", "")).lower() == level.lower()
                and str(roster.get("division", "")).lower()
                == division.lower()
            ),
            None,
        )
        if duplicate is not None:
            return RosterResult(
                "ROSTER_ALREADY_EXISTS",
                {"roster": self.summary(duplicate, schools)},
            )

        roster_id = self.normalize_roster_id(
            f"{school_id}-{sport}-{season}-{level}-{division}"
        )
        base_id = roster_id
        suffix = 2
        while any(roster.get("id") == roster_id for roster in rosters):
            roster_id = f"{base_id}-{suffix}"
            suffix += 1

        now = int(self._clock())
        record: Roster = {
            "id": roster_id,
            "school_id": school_id,
            "sport": sport,
            "season": season,
            "level": level,
            "division": division,
            "players": [],
            "created_at": now,
            "updated_at": now,
        }
        rosters.append(record)
        self._save_rosters(rosters)
        return RosterResult(
            "OK",
            {"roster": self.summary(record, schools)},
        )

    def update(self, roster_id: str, incoming: Roster) -> RosterResult:
        rosters = self._load_rosters()
        roster = self._find(rosters, roster_id)
        if roster is None:
            return RosterResult("ROSTER_NOT_FOUND")

        for field_name in self.UPDATE_FIELDS:
            if field_name in incoming:
                roster[field_name] = str(incoming[field_name]).strip()
        roster["updated_at"] = int(self._clock())
        self._save_rosters(rosters)
        return RosterResult(
            "OK",
            {"roster": self.summary(roster, self._load_schools())},
        )

    def delete(self, roster_id: str) -> RosterResult:
        rosters = self._load_rosters()
        if self._find(rosters, roster_id) is None:
            return RosterResult("ROSTER_NOT_FOUND")
        self._save_rosters(
            [
                roster
                for roster in rosters
                if str(roster.get("id", "")) != str(roster_id)
            ]
        )
        return RosterResult("OK", {"ok": True})

    def create_player(
        self,
        roster_id: str,
        incoming: Player,
    ) -> RosterResult:
        rosters = self._load_rosters()
        roster = self._find(rosters, roster_id)
        if roster is None:
            return RosterResult("ROSTER_NOT_FOUND")

        first_name = str(incoming.get("first_name", "")).strip()
        last_name = str(incoming.get("last_name", "")).strip()
        number = str(incoming.get("number", "")).strip()
        if not first_name and not last_name:
            return RosterResult("PLAYER_NAME_REQUIRED")

        players = roster.setdefault("players", [])
        player_id = self._unique_player_id(
            players,
            incoming.get("id") or f"{number}-{first_name}-{last_name}",
        )
        duplicate_number = self._duplicate_number(players, number)
        player = self._player_record(
            incoming,
            player_id=player_id,
            first_name=first_name,
            last_name=last_name,
            number=number,
        )
        players.append(player)
        roster["updated_at"] = int(self._clock())
        self._save_rosters(rosters)
        return RosterResult(
            "OK",
            {
                "player": copy.deepcopy(player),
                "warning": (
                    "DUPLICATE_JERSEY_NUMBER" if duplicate_number else ""
                ),
            },
        )

    def update_player(
        self,
        roster_id: str,
        player_id: str,
        incoming: Player,
    ) -> RosterResult:
        rosters = self._load_rosters()
        roster = self._find(rosters, roster_id)
        if roster is None:
            return RosterResult("ROSTER_NOT_FOUND")

        players = roster.get("players", [])
        player = self._find_player(players, player_id)
        if player is None:
            return RosterResult("PLAYER_NOT_FOUND")

        number = str(incoming.get("number", player.get("number", ""))).strip()
        duplicate_number = self._duplicate_number(
            players,
            number,
            exclude_id=player_id,
        )

        for field_name in self.PLAYER_STRING_FIELDS:
            if field_name in incoming:
                player[field_name] = str(incoming[field_name]).strip()
        for field_name in self.PLAYER_BOOLEAN_FIELDS:
            if field_name in incoming:
                player[field_name] = bool(incoming[field_name])
        if "status" in incoming:
            player["status"] = (
                "inactive"
                if str(incoming["status"]).lower() == "inactive"
                else "active"
            )

        roster["updated_at"] = int(self._clock())
        self._save_rosters(rosters)
        return RosterResult(
            "OK",
            {
                "player": copy.deepcopy(player),
                "warning": (
                    "DUPLICATE_JERSEY_NUMBER" if duplicate_number else ""
                ),
            },
        )

    def delete_player(self, roster_id: str, player_id: str) -> RosterResult:
        rosters = self._load_rosters()
        roster = self._find(rosters, roster_id)
        if roster is None:
            return RosterResult("ROSTER_NOT_FOUND")

        players = roster.get("players", [])
        if self._find_player(players, player_id) is None:
            return RosterResult("PLAYER_NOT_FOUND")
        roster["players"] = [
            player
            for player in players
            if str(player.get("id", "")) != str(player_id)
        ]
        roster["updated_at"] = int(self._clock())
        self._save_rosters(rosters)
        return RosterResult("OK", {"ok": True})

    def import_players(
        self,
        roster_id: str,
        rows: Any,
    ) -> RosterResult:
        if not isinstance(rows, list):
            return RosterResult("INVALID_PLAYER_LIST")

        rosters = self._load_rosters()
        roster = self._find(rosters, roster_id)
        if roster is None:
            return RosterResult("ROSTER_NOT_FOUND")

        players = roster.setdefault("players", [])
        added = 0
        warnings: list[str] = []

        for row in rows:
            if not isinstance(row, dict):
                continue
            first_name = str(row.get("first_name", "")).strip()
            last_name = str(row.get("last_name", "")).strip()
            if not first_name and not last_name:
                continue

            number = str(row.get("number", "")).strip()
            if self._duplicate_number(players, number):
                warnings.append(f"Duplicate jersey number {number}")
            player_id = self._unique_player_id(
                players,
                f"{number}-{first_name}-{last_name}",
            )
            player = self._player_record(
                row,
                player_id=player_id,
                first_name=first_name,
                last_name=last_name,
                number=number,
                imported=True,
            )
            players.append(player)
            added += 1

        roster["updated_at"] = int(self._clock())
        self._save_rosters(rosters)
        return RosterResult(
            "OK",
            {
                "added": added,
                "warnings": warnings,
                "roster": self.summary(roster, self._load_schools()),
            },
        )

    @classmethod
    def _player_record(
        cls,
        incoming: Player,
        *,
        player_id: str,
        first_name: str,
        last_name: str,
        number: str,
        imported: bool = False,
    ) -> Player:
        def flag(name: str) -> bool:
            value = incoming.get(name, False)
            if imported:
                return str(value).lower() in ("1", "true", "yes", "y")
            return bool(value)

        return {
            "id": player_id,
            "number": number,
            "first_name": first_name,
            "last_name": last_name,
            "preferred_name": str(incoming.get("preferred_name", "")).strip(),
            "position": str(incoming.get("position", "")).strip(),
            "secondary_position": str(
                incoming.get("secondary_position", "")
            ).strip(),
            "grade": str(incoming.get("grade", "")).strip(),
            "height": str(incoming.get("height", "")).strip(),
            "weight": str(incoming.get("weight", "")).strip(),
            "captain": flag("captain"),
            "starter": flag("starter"),
            "status": (
                "inactive"
                if str(incoming.get("status", "active")).lower() == "inactive"
                else "active"
            ),
            "pronunciation": str(incoming.get("pronunciation", "")).strip(),
            "pronunciation_verified": flag("pronunciation_verified"),
            "headshot": str(incoming.get("headshot", "")).strip(),
        }

    @classmethod
    def _unique_player_id(
        cls,
        players: list[Player],
        value: Any,
    ) -> str:
        player_id = cls.normalize_player_id(str(value or ""))
        base_id = player_id
        suffix = 2
        while any(player.get("id") == player_id for player in players):
            player_id = f"{base_id}-{suffix}"
            suffix += 1
        return player_id

    @staticmethod
    def _duplicate_number(
        players: list[Player],
        number: str,
        *,
        exclude_id: str = "",
    ) -> bool:
        if not number:
            return False
        return any(
            str(player.get("id", "")) != str(exclude_id)
            and str(player.get("number", "")).strip() == number
            for player in players
        )

    @staticmethod
    def _find_player(
        players: list[Player],
        player_id: str,
    ) -> Player | None:
        target = str(player_id or "")
        return next(
            (
                player
                for player in players
                if str(player.get("id", "")) == target
            ),
            None,
        )

    @staticmethod
    def _find(rosters: list[Roster], roster_id: str) -> Roster | None:
        target = str(roster_id or "")
        return next(
            (
                roster
                for roster in rosters
                if str(roster.get("id", "")) == target
            ),
            None,
        )
