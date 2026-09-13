"""Lightweight basketball lineup (docs/BASKETBALL_ENGINE_SCOPING_PLAN.md
Sec.6 / Sec.10 P2 row: "Lightweight lineup (5 + bench, free subs, DQ
tracking)"). Deliberately much smaller than baseball's lineup_service --
Sec.6: "Basketball has no batting order, no re-entry limit (players sub
freely), no DH/DP-FLEX." This module owns exactly what basketball
substitution needs: setting the starting five, free (unlimited)
substitution, and surfacing when a disqualified player is still on the
floor -- the one real gate Sec.3.1 states: "must sub for a disqualified
player before resuming."

Both operations append a real ledger event (LINEUP_SET / SUBSTITUTION)
and apply via hoops_state_service's own structural interpreters, same
reducer discipline as every other mutation in this engine -- so a
lineup correction/undo through hoops_event_service replays correctly
too, not just in-game plays.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from hoops_state_service import TEAMS, HoopsStateFoundation


@dataclass(frozen=True)
class LineupResult:
    code: str
    state: dict[str, Any]
    data: dict[str, Any]

    @property
    def ok(self) -> bool:
        return self.code == "OK"


class HoopsLineupService:
    @classmethod
    def set_starting_five(cls, state: dict[str, Any], team: str, player_ids: list[str]) -> LineupResult:
        """Pre-game: exactly 5 distinct players, none already
        disqualified (can't happen before a game starts, but this module
        never assumes a caller's ordering discipline)."""
        if team not in TEAMS:
            raise ValueError(f"unknown team: {team}")
        unique = list(dict.fromkeys(player_ids))
        if len(unique) != 5:
            return LineupResult("INVALID_ROSTER_SIZE", state, {"count": len(unique), "player_ids": unique})
        hoops = state.setdefault("hoops", {})
        disqualified = set(hoops.get("disqualified", []))
        already_disqualified = sorted(disqualified.intersection(unique))
        if already_disqualified:
            return LineupResult("DISQUALIFIED_PLAYER_STARTING", state, {"player_ids": already_disqualified})

        payload = {"team": team, "playerIds": unique}
        HoopsStateFoundation.apply_lineup_set(state, hoops, payload)
        event = HoopsStateFoundation.append_event(hoops, "LINEUP_SET", payload)
        return LineupResult("OK", state, {"on_floor": unique, "event": event})

    @classmethod
    def players_needing_substitution(cls, state: Mapping[str, Any], team: str) -> list[str]:
        """Which of `team`'s ON-FLOOR players are disqualified and must be
        subbed out before play resumes (Sec.3.1). A caller (or a future
        UI) checks this before allowing the clock to start; this module
        does not itself gate the clock -- that would be reaching into
        hoops_period_service's/the operator UI's own responsibility."""
        if team not in TEAMS:
            raise ValueError(f"unknown team: {team}")
        hoops = state.get("hoops") or {}
        on_floor = hoops.get(f"{team}_on_floor", [])
        disqualified = set(hoops.get("disqualified", []))
        return [p for p in on_floor if p in disqualified]

    @classmethod
    def substitute(cls, state: dict[str, Any], team: str, out_player_id: str, in_player_id: str) -> LineupResult:
        """Free, unlimited substitution (Sec.6: no re-entry limit, no
        DH/DP-FLEX-style restriction) -- the only real gates are
        structural: `out_player_id` must actually be on the floor,
        `in_player_id` must not already be on it, and a disqualified
        player (foul-out, ejection) can never re-enter, ever."""
        if team not in TEAMS:
            raise ValueError(f"unknown team: {team}")
        hoops = state.setdefault("hoops", {})
        on_floor = list(hoops.get(f"{team}_on_floor", []))
        if out_player_id not in on_floor:
            return LineupResult("PLAYER_NOT_ON_FLOOR", state, {"player_id": out_player_id})
        if in_player_id in on_floor:
            return LineupResult("PLAYER_ALREADY_ON_FLOOR", state, {"player_id": in_player_id})
        disqualified = set(hoops.get("disqualified", []))
        if in_player_id in disqualified:
            return LineupResult("PLAYER_DISQUALIFIED", state, {"player_id": in_player_id})

        payload = {"team": team, "outPlayerId": out_player_id, "inPlayerId": in_player_id}
        HoopsStateFoundation.apply_substitution(state, hoops, payload)
        event = HoopsStateFoundation.append_event(hoops, "SUBSTITUTION", payload)
        return LineupResult(
            "OK", state,
            {"on_floor": list(hoops.get(f"{team}_on_floor", [])), "out": out_player_id, "in": in_player_id, "event": event},
        )
