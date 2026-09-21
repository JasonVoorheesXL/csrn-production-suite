"""Basketball overlay PANEL feed -- the read-only data the Collegiate Tech
basketball board needs beyond the scorebug fields in
docs/HOOPS_OVERLAY_CONTRACT.md (see docs/BASKETBALL_PANEL_PARITY.md).

The overlay has no operator login and no roster access, and the hoops event
ledger only carries player ids, so "who scored" and "who is playing" cannot be
derived in the browser. This module turns the ledger + the roster into the
plain, already-resolved payload the board renders:

    {
      "leaders":    {"home": {name, number, pts, reb, ast, line} | None, "visitor": ...},
      "team_stats": {"home": {"fg": "12/28", "fg3": "3", "reb": "14"}, "visitor": ...},
      "last_basket": {"team", "points", "name", "number"} | None,
      "on_floor":   {"home": [{"number", "name"}, ...], "visitor": [...]},
    }

Read-only and derived: it never writes, never becomes a second source of truth
(same discipline as hoops_box_score_service.py), and it is deliberately NOT
handbook-precision stat tracking -- the owner's basketball broadcast priority is
the score, who scored, and who is playing. Every field degrades to blank/None
when the operator has not attributed plays to players; the board then shows
dashes rather than wrong numbers.
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable, Iterable, Mapping

from hoops_box_score_service import HoopsBoxScoreService

TEAMS: tuple[str, str] = ("home", "visitor")
ROSTER_TTL_SECONDS = 30.0


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _player_label(player: Mapping[str, Any]) -> str:
    first = _clean(player.get("first_name"))
    last = _clean(player.get("last_name"))
    return " ".join(part for part in (first, last) if part) or _clean(player.get("name"))


def roster_lookup(rosters: Iterable[Mapping[str, Any]], state: Mapping[str, Any]) -> dict[str, dict[str, dict[str, str]]]:
    """{"home": {player_id: {"name", "number"}}, "visitor": {...}} from the
    basketball roster of each team's school. A player id is only ever looked up
    inside its own team's roster, so identical ids across schools cannot cross."""
    by_side: dict[str, dict[str, dict[str, str]]] = {"home": {}, "visitor": {}}
    for side in TEAMS:
        school_id = _clean(state.get(f"{side}_school_id"))
        if not school_id:
            continue
        for roster in rosters or []:
            if _clean(roster.get("school_id")) != school_id:
                continue
            if _clean(roster.get("sport")).lower() != "basketball":
                continue
            for player in roster.get("players") or []:
                pid = _clean(player.get("id"))
                if pid:
                    by_side[side][pid] = {"name": _player_label(player), "number": _clean(player.get("number"))}
    return by_side


def _who(names: Mapping[str, Mapping[str, str]], player_id: str) -> dict[str, str]:
    known = names.get(player_id) or {}
    return {"name": known.get("name", ""), "number": known.get("number", "")}


def build_panel(state: Mapping[str, Any], names: Mapping[str, Mapping[str, Mapping[str, str]]] | None = None) -> dict[str, Any]:
    """The panel payload for `state` (a basketball game). `names` is
    roster_lookup()'s output; without it players resolve to blank names."""
    names = names or {"home": {}, "visitor": {}}
    hoops = state.get("hoops") or {}
    events = HoopsBoxScoreService._rebuilt_events(state)

    players: dict[str, dict[str, Any]] = {}
    totals = {side: {"fgm": 0, "fga": 0, "fg3m": 0, "reb": 0} for side in TEAMS}
    last_basket: dict[str, Any] | None = None

    def line(side: str, player_id: str) -> dict[str, Any]:
        return players.setdefault(f"{side}:{player_id}", {"side": side, "id": player_id, "pts": 0, "reb": 0, "ast": 0})

    for event in events:
        kind = event.get("event_type")
        payload = event.get("payload") or {}
        side = _clean(payload.get("team"))
        if side not in TEAMS:
            continue
        if kind == "SHOT":
            points = int(payload.get("points", 2) or 2)
            made = bool(payload.get("made"))
            totals[side]["fga"] += 1
            if made:
                totals[side]["fgm"] += 1
                if points == 3:
                    totals[side]["fg3m"] += 1
                shooter = _clean(payload.get("shooterId"))
                if shooter:
                    line(side, shooter)["pts"] += points
                assist = _clean(payload.get("assistId"))
                if assist:
                    line(side, assist)["ast"] += 1
                last_basket = {"team": side, "points": points, "player_id": shooter}
        elif kind == "FREE_THROW" and payload.get("made"):
            shooter = _clean(payload.get("shooterId"))
            if shooter:
                line(side, shooter)["pts"] += 1
            last_basket = {"team": side, "points": 1, "player_id": shooter}
        elif kind == "REBOUND":
            totals[side]["reb"] += 1
            rebounder = _clean(payload.get("playerId"))
            if rebounder:
                line(side, rebounder)["reb"] += 1

    leaders: dict[str, Any] = {}
    for side in TEAMS:
        scorers = [p for p in players.values() if p["side"] == side and p["pts"] > 0]
        if not scorers:
            leaders[side] = None
            continue
        top = max(scorers, key=lambda p: (p["pts"], p["reb"] + p["ast"]))
        who = _who(names[side], top["id"])
        leaders[side] = {
            **who,
            "pts": top["pts"], "reb": top["reb"], "ast": top["ast"],
            "line": f"{top['pts']} PTS · {top['reb']} REB · {top['ast']} AST",
        }

    team_stats = {
        side: {
            "fg": f"{totals[side]['fgm']}/{totals[side]['fga']}" if totals[side]["fga"] else "",
            "fg3": str(totals[side]["fg3m"]) if totals[side]["fga"] else "",
            "reb": str(totals[side]["reb"]) if totals[side]["reb"] else "",
        }
        for side in TEAMS
    }

    on_floor: dict[str, list[dict[str, str]]] = {}
    for side in TEAMS:
        ids = hoops.get(f"{side}_on_floor") or []
        on_floor[side] = [_who(names[side], _clean(pid)) for pid in ids]

    last = None
    if last_basket:
        last = {"team": last_basket["team"], "points": last_basket["points"], **_who(names[last_basket["team"]], last_basket["player_id"])}

    return {"leaders": leaders, "team_stats": team_stats, "last_basket": last, "on_floor": on_floor}


class HoopsOverlayPanelService:
    """Builds the panel payload, caching the (file-backed) roster lookup so the
    overlay's poll never re-reads roster files on every request."""

    def __init__(self, list_rosters: Callable[[], Iterable[Mapping[str, Any]]], *, now: Callable[[], float] = time.monotonic) -> None:
        self._list_rosters = list_rosters
        self._now = now
        self._lock = threading.Lock()
        self._cached_key: tuple[str, str] | None = None
        self._cached_at = 0.0
        self._cached_names: dict[str, dict[str, dict[str, str]]] = {"home": {}, "visitor": {}}

    def names_for(self, state: Mapping[str, Any]) -> dict[str, dict[str, dict[str, str]]]:
        key = (_clean(state.get("home_school_id")), _clean(state.get("visitor_school_id")))
        with self._lock:
            fresh = self._now() - self._cached_at < ROSTER_TTL_SECONDS
            if self._cached_key == key and fresh:
                return self._cached_names
            try:
                names = roster_lookup(list(self._list_rosters() or []), state)
            except Exception:  # a roster read problem must never take the overlay down
                names = {"home": {}, "visitor": {}}
            self._cached_key, self._cached_at, self._cached_names = key, self._now(), names
            return names

    def panel(self, state: Mapping[str, Any]) -> dict[str, Any]:
        return build_panel(state, self.names_for(state))
