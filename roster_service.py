from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field
from typing import Any, Callable


Roster = dict[str, Any]
School = dict[str, Any]
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
