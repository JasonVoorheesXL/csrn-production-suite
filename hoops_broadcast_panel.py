"""What the basketball board shows beyond the score: the shot marker, runs, who is on
the floor, a hot hand, automatic notes, foul-trouble alerts, and the shot chart and
halftime screens. Read-only and worked out from the event ledger each time, like
hoops_overlay_panel.py, which adds it to the panel feed.

Broadcast rules from the owner (2026-11-02): both teams are treated the same, misses
included; facts only; nothing singles out a player for shooting badly. Foul trouble
shows on its own; the shot chart and halftime screens only when the operator asks.
"""

from __future__ import annotations

from typing import Any, Mapping

from hoops_shot_geometry import shots_with_notes

TEAMS: tuple[str, str] = ("home", "visitor")
RUN_SHOWN_FROM = 5
NOTE_RUN_FROM = 6
HOT_HAND_MIN_MADE = 3
FOUL_TROUBLE_AT = 4
DROUGHT_NOTE_SECONDS = 180

ZONE_NAMES = {
    "rim": "At the rim", "paint": "In the paint", "mid_range": "Mid-range", "top_three": "Top of the arc",
    "left_wing_three": "Left wing", "right_wing_three": "Right wing",
    "left_corner_three": "Left corner", "right_corner_three": "Right corner",
}
CHART_ZONES = (
    ("Paint", ("rim", "paint")),
    ("Mid-range", ("mid_range",)),
    ("Left corner 3", ("left_corner_three",)),
    ("Above the arc", ("top_three", "left_wing_three", "right_wing_three")),
    ("Right corner 3", ("right_corner_three",)),
)


def _other(team: str) -> str:
    return "visitor" if team == "home" else "home"


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def attacks_right(state: Mapping[str, Any], team: str) -> bool:
    """Does `team` shoot at the right-hand basket on screen right now? Ends switch at
    halftime and stay switched through overtime."""
    base_right = (state.get("hoops") or {}).get("home_first_half_attacks", "right") != "left"
    first_half = str(state.get("period", "1")) in ("1", "2")
    home_right = base_right if first_half else not base_right
    return home_right if team == "home" else not home_right


def screen_spot(state: Mapping[str, Any], team: str, x: float, y: float) -> dict[str, float]:
    return {"x": x, "y": y} if attacks_right(state, team) else {"x": 84 - x, "y": 50 - y}


class _Names:
    def __init__(self, names: Mapping[str, Mapping[str, Mapping[str, str]]]):
        self.names = names

    def who(self, team: str, player_id: str) -> dict[str, str]:
        known = (self.names.get(team) or {}).get(str(player_id or "")) or {}
        return {"number": known.get("number", ""), "name": known.get("name", ""), "last": known.get("last", "") or known.get("name", "")}

    def short(self, team: str, player_id: str) -> str:
        who = self.who(team, player_id)
        if who["number"] and who["last"]:
            return f"#{who['number']} {who['last']}"
        return who["last"] or (f"#{who['number']}" if who["number"] else "")


def _clock(seconds: Any) -> str:
    total = _int(seconds)
    return f"{total // 60}:{total % 60:02d}"


def _marker(state: Mapping[str, Any], events: list[Mapping[str, Any]], names: _Names, shots_by_id: Mapping[str, Mapping[str, Any]]) -> dict[str, Any] | None:
    """The newest thing to mark on the court. It stays through the rebound, the foul
    and the free throws, and clears on the next shot, a steal, a turnover, a timeout
    or a new quarter."""
    notes: dict[str, dict[str, Any]] = {}
    for event in events:
        if event.get("event_type") == "PLAY_NOTE":
            payload = event.get("payload") or {}
            notes.setdefault(str(payload.get("targetEventId", "")), {}).update(payload)
    for event in reversed(events):
        kind = event.get("event_type")
        payload = event.get("payload") or {}
        team = str(payload.get("team", ""))
        if kind == "SHOT":
            shot = shots_by_id.get(str(event.get("event_id")), payload)
            if shot.get("spotX") is None:
                return None
            who = names.short(team, shot.get("shooterId")) or "Shot"
            where = ZONE_NAMES.get(str(shot.get("zone", "")), "")
            points = _int(shot.get("points")) or 2
            kind_text = str(shot.get("shotType", "")).upper() or f"{points} PT"
            if shot.get("made"):
                parts = [who, kind_text, where]
                label = "Last shot"
                mark = "made"
            else:
                parts = [who, f"Missed {points}", where]
                label = "Last shot"
                mark = "miss"
            return {"id": event.get("event_id"), "kind": mark, "label": label, "text": " · ".join(p for p in parts if p), **screen_spot(state, team, float(shot["spotX"]), float(shot["spotY"]))}
        if kind == "FOUL" and payload.get("spotX") is not None and payload.get("drewFoulOn"):
            shooter_team = _other(team)
            who = names.short(shooter_team, payload.get("drewFoulOn")) or "Shot"
            where = ZONE_NAMES.get(str(payload.get("zone", "")), "")
            return {"id": event.get("event_id"), "kind": "fouled", "label": "Fouled", "text": " · ".join(p for p in (who, where) if p), **screen_spot(state, shooter_team, float(payload["spotX"]), float(payload["spotY"]))}
        if kind == "TURNOVER":
            note = notes.get(str(event.get("event_id")), {})
            stealer = payload.get("stealPlayerId")
            spot_x = note.get("spotX", payload.get("spotX"))
            if not stealer or spot_x is None:
                return None
            stealing = _other(team)
            spot_y = note.get("spotY", payload.get("spotY"))
            return {"id": event.get("event_id"), "kind": "steal", "label": "Steal", "text": names.short(stealing, stealer), **screen_spot(state, stealing, float(spot_x), float(spot_y))}
        if kind in ("TIMEOUT", "PERIOD_TRANSITION", "VIOLATION", "HELD_BALL", "OPENING_TIP"):
            return None
    return None


def _scoring_runs(events: list[Mapping[str, Any]]) -> tuple[dict[str, Any] | None, dict[str, str]]:
    """The run going on now, and each team's longest run of the game."""
    scoring = []
    for event in events:
        payload = event.get("payload") or {}
        kind = event.get("event_type")
        points = (_int(payload.get("points")) or 2) if kind == "SHOT" and payload.get("made") else (1 if kind == "FREE_THROW" and payload.get("made") else 0)
        if points and payload.get("team") in TEAMS:
            scoring.append((str(payload["team"]), points))
    best = {side: (0, 0) for side in TEAMS}
    # A run counts from the first basket after the other team last scored, allowing
    # nothing against it; the longest run reports what the other team had during it.
    i = 0
    current = None
    while i < len(scoring):
        team, total, j = scoring[i][0], 0, i
        while j < len(scoring) and scoring[j][0] == team:
            total += scoring[j][1]
            j += 1
        if total > best[team][0]:
            best[team] = (total, 0)
        current = (team, total)
        i = j
    run = None
    if current and current[1] >= RUN_SHOWN_FROM:
        run = {"team": current[0], "points": current[1]}
    return run, {side: (f"{best[side][0]}-0" if best[side][0] else "-") for side in TEAMS}


def _player_lines(events: list[Mapping[str, Any]]) -> dict[str, dict[str, int]]:
    lines: dict[str, dict[str, int]] = {}

    def line(player_id: Any) -> dict[str, int]:
        return lines.setdefault(str(player_id), {"pts": 0, "reb": 0, "fgm": 0, "fga": 0, "tpm": 0, "tpa": 0, "fouls": 0})

    for event in events:
        payload = event.get("payload") or {}
        kind = event.get("event_type")
        if kind == "SHOT" and payload.get("shooterId"):
            row = line(payload["shooterId"])
            points = _int(payload.get("points")) or 2
            row["fga"] += 1
            row["tpa"] += 1 if points == 3 else 0
            if payload.get("made"):
                row["fgm"] += 1
                row["pts"] += points
                row["tpm"] += 1 if points == 3 else 0
        elif kind == "FREE_THROW" and payload.get("shooterId") and payload.get("made"):
            line(payload["shooterId"])["pts"] += 1
        elif kind == "REBOUND" and payload.get("playerId"):
            line(payload["playerId"])["reb"] += 1
        elif kind == "FOUL" and payload.get("playerId") and payload.get("countsTowardPersonal"):
            line(payload["playerId"])["fouls"] += 1
    return lines


def _team_rows(events: list[Mapping[str, Any]], shots: list[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    out = {side: {"fgm": 0, "fga": 0, "tpm": 0, "tpa": 0, "paint": 0, "second": 0, "off_turnovers": 0, "steals": 0} for side in TEAMS}
    for shot in shots:
        side = str(shot.get("team", ""))
        if side not in TEAMS:
            continue
        points = _int(shot.get("points")) or 2
        row = out[side]
        row["fga"] += 1
        row["tpa"] += 1 if points == 3 else 0
        if shot.get("made"):
            row["fgm"] += 1
            row["tpm"] += 1 if points == 3 else 0
            if shot.get("zone") in ("rim", "paint"):
                row["paint"] += points
            if "off_turnover" in (shot.get("tags") or []):
                row["off_turnovers"] += points
    # Second-chance points: scored after an offensive rebound, before the ball changes hands.
    chance = ""
    for event in events:
        payload = event.get("payload") or {}
        kind = event.get("event_type")
        side = str(payload.get("team", ""))
        if kind == "REBOUND":
            offensive = payload.get("kind") == "offensive" or payload.get("reboundFor") == "offensive"
            chance = side if offensive else ""
        elif kind == "SHOT":
            if payload.get("made") and side == chance and side in TEAMS:
                out[side]["second"] += _int(payload.get("points")) or 2
            if payload.get("made"):
                chance = ""
        elif kind == "FREE_THROW":
            if payload.get("made") and side == chance and side in TEAMS:
                out[side]["second"] += 1
        elif kind in ("TURNOVER", "PERIOD_TRANSITION", "VIOLATION"):
            chance = ""
        if kind == "TURNOVER" and payload.get("stealPlayerId") and side in TEAMS:
            out[_other(side)]["steals"] += 1
    return out


def _pct(made: int, tries: int) -> str:
    return f"{round(made / tries * 100)}%" if tries else "-"


def _hot_hand(side: str, lines: Mapping[str, Mapping[str, int]], shots: list[Mapping[str, Any]], names: _Names, players_on_side: set[str]) -> dict[str, Any] | None:
    pool = [(pid, row) for pid, row in lines.items() if pid in players_on_side and row["fgm"] >= HOT_HAND_MIN_MADE]
    if not pool:
        return None
    pid, row = max(pool, key=lambda item: (item[1]["pts"], item[1]["fgm"]))
    who = names.who(side, pid)
    detail = f"{row['tpm']} of {row['tpa']} from three" if row["tpm"] >= 2 else f"{row['fgm']} of {row['fga']} shooting"
    spots = [{"x": float(s["spotX"]), "y": float(s["spotY"]), "made": bool(s.get("made"))} for s in shots if str(s.get("shooterId")) == pid and s.get("spotX") is not None]
    return {"title": names.short(side, pid), "line": f"{row['pts']} pts · {detail}", "shots": spots, "number": who["number"]}


def _notes(state: Mapping[str, Any], events: list[Mapping[str, Any]], lines: Mapping[str, Mapping[str, int]], run: Mapping[str, Any] | None, names: _Names, side_of: Mapping[str, str]) -> list[str]:
    hoops = state.get("hoops") or {}
    team_name = {side: str(state.get(f"{side}_team", "") or side).upper() for side in TEAMS}
    notes: list[str] = []
    if run and run["points"] >= NOTE_RUN_FROM:
        notes.append(f"{team_name[run['team']]} ON A {run['points']}-0 RUN")
    for pid, row in sorted(lines.items(), key=lambda item: -item[1]["tpm"]):
        side = side_of.get(pid)
        if side and row["tpm"] >= 3:
            notes.append(f"{names.short(side, pid).upper()} {row['tpm']} OF {row['tpa']} FROM THREE")
            break
    scorers = [(pid, row) for pid, row in lines.items() if side_of.get(pid) and row["pts"] >= 10]
    if scorers:
        pid, row = max(scorers, key=lambda item: item[1]["pts"])
        notes.append(f"{names.short(side_of[pid], pid).upper()} LEADS ALL SCORERS WITH {row['pts']}")
    for side in TEAMS:
        fouls = _int(hoops.get(f"{side}_team_fouls"))
        bonus = str(hoops.get(f"{_other(side)}_bonus", "NONE"))
        if bonus != "NONE":
            notes.append(f"{team_name[_other(side)]} IN THE BONUS")
        elif fouls == FOUL_TROUBLE_AT:
            notes.append(f"{team_name[_other(side)]} IN THE BONUS ON THE NEXT FOUL")
    stamped = [e for e in events if (e.get("payload") or {}).get("clockSeconds") is not None and str((e.get("payload") or {}).get("period", "")) == str(state.get("period", ""))]
    if stamped:
        now = _int(stamped[-1]["payload"]["clockSeconds"])
        for side in TEAMS:
            baskets = [e for e in stamped if e.get("event_type") == "SHOT" and e["payload"].get("team") == side and e["payload"].get("made")]
            if baskets:
                gap = _int(baskets[-1]["payload"]["clockSeconds"]) - now
                if gap >= DROUGHT_NOTE_SECONDS:
                    notes.append(f"{team_name[side]} NO FIELD GOAL SINCE {_clock(baskets[-1]['payload']['clockSeconds'])}")
    return notes


def _foul_alert(state: Mapping[str, Any], events: list[Mapping[str, Any]], lines: Mapping[str, Mapping[str, int]], names: _Names) -> dict[str, Any] | None:
    # With alerts off the newest one is still reported, marked muted, so turning them
    # back on does not put an old foul on air.
    muted = ((state.get("hoops") or {}).get("display") or {}).get("alerts") is False
    counts: dict[str, int] = {}
    alert = None
    for event in events:
        payload = event.get("payload") or {}
        if event.get("event_type") != "FOUL" or not payload.get("playerId") or not payload.get("countsTowardPersonal"):
            continue
        pid = str(payload["playerId"])
        counts[pid] = counts.get(pid, 0) + 1
        if counts[pid] >= FOUL_TROUBLE_AT:
            alert = (event.get("event_id"), str(payload.get("team", "")), pid, counts[pid], _int(event.get("sequence")))
    if not alert:
        return None
    event_id, side, pid, count, sequence = alert
    who = names.who(side, pid)
    row = lines.get(pid, {})
    team = str(state.get(f"{side}_team", "") or "")
    out = pid in ((state.get("hoops") or {}).get("disqualified") or [])
    return {
        "id": event_id, "sequence": sequence, "muted": muted, "side": side, "number": who["number"], "name": who["name"] or who["last"],
        "line": f"{team} · {row.get('pts', 0)} points, {row.get('reb', 0)} rebounds",
        "tag": "FOULED OUT" if out else f"{count} FOULS", "tag2": "" if out else "FOUL TROUBLE",
    }


def _shot_chart(state: Mapping[str, Any], display: Mapping[str, Any], shots: list[Mapping[str, Any]], names: _Names) -> dict[str, Any]:
    side = display.get("team") if display.get("team") in TEAMS else "home"
    player = str(display.get("player", "") or "")
    pool = [s for s in shots if s.get("team") == side and (not player or str(s.get("shooterId")) == player)]
    zones = []
    for label, keys in CHART_ZONES:
        here = [s for s in pool if s.get("zone") in keys]
        made = sum(1 for s in here if s.get("made"))
        zones.append({"label": label, "pct": _pct(made, len(here)), "line": f"{made} of {len(here)}"})
    title = (names.short(side, player) if player else str(state.get(f"{side}_team", "") or side)).upper()
    return {"kind": "shot_chart", "title": f"{title} SHOT CHART", "sub": f"THROUGH {_period_name(state)}", "zones": zones,
            "shots": [{"x": float(s["spotX"]), "y": float(s["spotY"]), "made": bool(s.get("made"))} for s in pool if s.get("spotX") is not None]}


def _period_name(state: Mapping[str, Any]) -> str:
    period = str(state.get("period", "1"))
    return f"QUARTER {period}" if period.isdigit() else "OVERTIME"


def _comparison(state: Mapping[str, Any], events: list[Mapping[str, Any]], shots: list[Mapping[str, Any]], lines: Mapping[str, Mapping[str, int]], names: _Names, side_of: Mapping[str, str], longest: Mapping[str, str]) -> dict[str, Any]:
    teams = _team_rows(events, shots)
    left, right = "visitor", "home"
    rows = [
        ("Field goals", _pct(teams[left]["fgm"], teams[left]["fga"]), _pct(teams[right]["fgm"], teams[right]["fga"])),
        ("Three-pointers", f"{teams[left]['tpm']} of {teams[left]['tpa']}", f"{teams[right]['tpm']} of {teams[right]['tpa']}"),
        ("Points in paint", str(teams[left]["paint"]), str(teams[right]["paint"])),
        ("Second-chance", str(teams[left]["second"]), str(teams[right]["second"])),
        ("Off turnovers", str(teams[left]["off_turnovers"]), str(teams[right]["off_turnovers"])),
        ("Longest run", longest[left], longest[right]),
    ]
    leaders = {}
    for side in TEAMS:
        pool = [(pid, row) for pid, row in lines.items() if side_of.get(pid) == side and row["pts"] > 0]
        if pool:
            pid, row = max(pool, key=lambda item: item[1]["pts"])
            leaders[side] = {"who": names.short(side, pid), "pts": row["pts"]}
        else:
            leaders[side] = None
    return {"kind": "comparison", "left": str(state.get(f"{left}_team", "") or left).upper(), "right": str(state.get(f"{right}_team", "") or right).upper(),
            "sub": "HALFTIME" if str(state.get("period")) in ("2", "3") else _period_name(state), "rows": [{"label": a, "left": b, "right": c} for a, b, c in rows],
            "leaders": {"left": leaders[left], "right": leaders[right]}}


def build_broadcast(state: Mapping[str, Any], events: list[Mapping[str, Any]], names: Mapping[str, Mapping[str, Mapping[str, str]]]) -> dict[str, Any]:
    hoops = state.get("hoops") or {}
    resolver = _Names(names)
    shots = shots_with_notes([e for e in events])
    shots_by_id = {str(s["event_id"]): s for s in shots}
    lines = _player_lines(events)
    side_of = {str(pid): side for side in TEAMS for pid in (names.get(side) or {})}
    run, longest = _scoring_runs(events)
    on_floor = {}
    hot = {}
    for side in TEAMS:
        rows = []
        for pid in hoops.get(f"{side}_on_floor") or []:
            row = lines.get(str(pid), {})
            who = resolver.who(side, pid)
            rows.append({"number": who["number"], "last": who["last"], "pts": row.get("pts", 0), "fouls": _int((hoops.get("player_fouls") or {}).get(pid))})
        on_floor[side] = rows
        hot[side] = _hot_hand(side, lines, shots, resolver, {pid for pid, s in side_of.items() if s == side})
    display = hoops.get("display") or {}
    screen = None
    if display.get("screen") == "shot_chart":
        screen = _shot_chart(state, display, shots, resolver)
    elif display.get("screen") == "comparison":
        screen = _comparison(state, events, shots, lines, resolver, side_of, longest)
    return {
        "marker": _marker(state, events, resolver, shots_by_id),
        "run": run,
        "on_floor": on_floor,
        "hot_hand": {side: ({**hot[side], "shots": hot[side]["shots"]} if hot[side] else None) for side in TEAMS},
        "notes": _notes(state, events, lines, run, resolver, side_of),
        "alert": _foul_alert(state, events, lines, resolver),
        "screen": screen,
    }
