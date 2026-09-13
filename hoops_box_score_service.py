"""Per-player statistics + team totals derived from the event ledger
(docs/BASKETBALL_ENGINE_SCOPING_PLAN.md Sec.2/Sec.10 P2 row:
"box_score_service (PTS/REB/AST/STL/BLK/TO/PF, FG/3P/FT splits, team
totals)"). Read-only reporting layer, same discipline as baseball's
box_score_service.py: never a second source of truth. Team totals
(score, team fouls, bonus, timeouts) come straight from
hoops_state_service's own canonical fields; per-player attribution comes
from each event's own payload.

report(state) always rebuilds from the ledger first
(HoopsStateFoundation.rebuild()) rather than trusting whatever a live
event's own stamps might carry -- so a box score is correct whether
requested mid-game or after a correction (undo/redo/correct_event).

STL/BLK attribution rides as OPTIONAL, additive fields on the TURNOVER
and SHOT payloads (stealPlayerId / blockPlayerId) -- Sec.5.1 groups
"Turnover / steal / block" as one operator-entry row, but a steal/block
has no canonical-state effect beyond what the turnover/missed-shot
already has, so it was never its own structural interpreter in
hoops_state_service. This is the same "additive attribution field, not a
new event type" pattern baseball's box_score_service uses for
batterId/pitcherId/resultCode on PLATE_APPEARANCE.
"""

from __future__ import annotations

from typing import Any, Mapping

from hoops_state_service import HoopsStateFoundation


def _empty_line() -> dict[str, int]:
    return {
        "pts": 0, "reb": 0, "ast": 0, "stl": 0, "blk": 0, "to": 0, "pf": 0,
        "fgm": 0, "fga": 0, "fg3m": 0, "fg3a": 0, "ftm": 0, "fta": 0,
    }


class HoopsBoxScoreService:
    @classmethod
    def team_totals(cls, state: Mapping[str, Any]) -> dict[str, Any]:
        hoops = state.get("hoops") or {}
        return {
            "home": {
                "score": int(state.get("home_score", 0) or 0),
                "team_fouls": int(hoops.get("home_team_fouls", 0) or 0),
                "bonus": str(hoops.get("home_bonus", "NONE")),
                "timeouts_remaining": int(hoops.get("home_timeouts", 0) or 0),
            },
            "visitor": {
                "score": int(state.get("visitor_score", 0) or 0),
                "team_fouls": int(hoops.get("visitor_team_fouls", 0) or 0),
                "bonus": str(hoops.get("visitor_bonus", "NONE")),
                "timeouts_remaining": int(hoops.get("visitor_timeouts", 0) or 0),
            },
        }

    @classmethod
    def _rebuilt_events(cls, state: Mapping[str, Any]) -> list[dict[str, Any]]:
        hoops = state.get("hoops") or {}
        rebuilt = HoopsStateFoundation.rebuild(state, hoops.get("hoops_events", []))
        return [e for e in (rebuilt.get("hoops") or {}).get("hoops_events", []) if not e.get("voided")]

    @classmethod
    def player_box(cls, state: Mapping[str, Any]) -> dict[str, dict[str, int]]:
        box: dict[str, dict[str, int]] = {}

        def line(player_id: str) -> dict[str, int]:
            return box.setdefault(player_id, _empty_line())

        for event in cls._rebuilt_events(state):
            event_type = event.get("event_type")
            payload = event.get("payload") or {}

            if event_type == "SHOT":
                shooter = str(payload.get("shooterId", "")).strip()
                points = int(payload.get("points", 2) or 2)
                made = bool(payload.get("made"))
                if shooter:
                    row = line(shooter)
                    row["fga"] += 1
                    if points == 3:
                        row["fg3a"] += 1
                    if made:
                        row["fgm"] += 1
                        row["pts"] += points
                        if points == 3:
                            row["fg3m"] += 1
                        assist = str(payload.get("assistId", "")).strip()
                        if assist:
                            line(assist)["ast"] += 1
                blocker = str(payload.get("blockPlayerId", "")).strip()
                if not made and blocker:
                    line(blocker)["blk"] += 1

            elif event_type == "FREE_THROW":
                shooter = str(payload.get("shooterId", "")).strip()
                if shooter:
                    row = line(shooter)
                    row["fta"] += 1
                    if payload.get("made"):
                        row["ftm"] += 1
                        row["pts"] += 1

            elif event_type == "REBOUND":
                player = str(payload.get("playerId", "")).strip()
                if player:
                    line(player)["reb"] += 1

            elif event_type == "FOUL":
                player = str(payload.get("playerId", "")).strip()
                if player and payload.get("countsTowardPersonal"):
                    line(player)["pf"] += 1

            elif event_type == "TURNOVER":
                player = str(payload.get("playerId", "")).strip()
                if player:
                    line(player)["to"] += 1
                stealer = str(payload.get("stealPlayerId", "")).strip()
                if stealer:
                    line(stealer)["stl"] += 1

        return box

    @classmethod
    def report(cls, state: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "team_totals": cls.team_totals(state),
            "players": cls.player_box(state),
        }
