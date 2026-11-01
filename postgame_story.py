"""Postgame story (Social Publishing round 1, 2026-11-01).

Turns a finished football game into the facts a game story needs -- final
score, line score, scoring plays, big plays with the quarter they came in,
each team's standouts -- and writes a newspaper-style story from those facts
with the app's built-in writer. Nothing here invents detail: every sentence
is built from a recorded play or a box-score number.

Pure module (no Flask, no file access): the caller hands in the broadcast,
its game state, the statistics report and a roster lookup.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import re
from typing import Any, Callable, Mapping

TEAMS = ("home", "visitor")
BIG_GAIN_YARDS = 20
BIG_RETURN_YARDS = 30
MAX_BIG_PLAYS = 4
MAX_STANDOUTS = 3

_SUFFIXES = {"jr": "Jr.", "sr": "Sr.", "ii": "II", "iii": "III", "iv": "IV"}
_NUMBER_WORDS = ("zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine")
_QUARTER_NAMES = {1: "first quarter", 2: "second quarter", 3: "third quarter", 4: "fourth quarter"}
_MONTHS_AP = ("Jan.", "Feb.", "March", "April", "May", "June", "July", "Aug.", "Sept.", "Oct.", "Nov.", "Dec.")

RosterLookup = Callable[[str], list[Mapping[str, Any]]]


# -- small helpers ---------------------------------------------------------------

def _int(value: Any) -> int:
    try:
        return int(float(value or 0))
    except (TypeError, ValueError):
        return 0


def count_word(value: int) -> str:
    """AP style: spell out one through nine."""
    return _NUMBER_WORDS[value] if 0 <= value < 10 else str(value)


def plural(value: int, word: str, plural_word: str | None = None) -> str:
    return f"{count_word(value)} {word if value == 1 else (plural_word or word + 's')}"


def quarter_number(value: Any) -> int:
    text = str(value or "").strip().upper()
    if text.startswith("OT"):
        return 5
    return _int(text)


def quarter_phrase(value: Any) -> str:
    number = quarter_number(value)
    return _QUARTER_NAMES.get(number, "overtime" if number > 4 else "")


def quarter_tag(value: Any) -> str:
    number = quarter_number(value)
    if number > 4:
        return "OT"
    return f"Q{number}" if number else ""


def tidy_team_name(name: Any) -> str:
    """'ITAWAMBA AHS' -> 'Itawamba AHS': all-caps words longer than three letters
    are title-cased; short ones (AHS, MS) read as initials and stay."""
    text = re.sub(r"\s+", " ", str(name or "").strip())
    if not text or text != text.upper():
        return text
    return " ".join(w.capitalize() if len(w) > 3 else w for w in text.split(" "))


def tidy_person_name(name: Any) -> str:
    """Play text can carry whatever the statistician typed ('Michael lashun
    Williams'); capitalise any word that starts lower-case and leave the rest
    (McKellar, DeShawn) alone."""
    words = re.sub(r"\s+", " ", str(name or "").strip()).split(" ")
    out = []
    for word in words:
        if not word:
            continue
        suffix = _SUFFIXES.get(word.casefold().rstrip("."))
        out.append(suffix if suffix else (word[:1].upper() + word[1:] if word[:1].islower() else word))
    return " ".join(out)


def ap_date(value: Any) -> str:
    try:
        day = _dt.date.fromisoformat(str(value or "")[:10])
    except ValueError:
        return ""
    return f"{day.strftime('%A')}, {_MONTHS_AP[day.month - 1]} {day.day}, {day.year}"


def weekday(value: Any) -> str:
    try:
        return _dt.date.fromisoformat(str(value or "")[:10]).strftime("%A")
    except ValueError:
        return ""


def score_text(a: int, b: int) -> str:
    """Leader's score first, the way a story reads ('34-9')."""
    return f"{max(a, b)}-{min(a, b)}"


# -- player names --------------------------------------------------------------

class Names:
    """Roster-backed names. A play's number on that team's roster wins over
    whatever name the play text carried; without a roster match the play
    text's name is tidied; without either the player is 'No. 23'."""

    def __init__(self, roster_for_team: RosterLookup | None, team_names: list[str] | None = None) -> None:
        self._team_names = {re.sub(r"\s+", " ", n).strip().casefold() for n in (team_names or []) if n}
        self.unnamed: set[tuple[str, str]] = set()  # (team, number) with no name anywhere
        self._rosters: dict[str, list[Mapping[str, Any]]] = {}
        for team in TEAMS:
            try:
                players = list(roster_for_team(team) or []) if roster_for_team else []
            except Exception:
                players = []
            self._rosters[team] = [
                p for p in players
                if isinstance(p, Mapping)
                and str(p.get("status", "active") or "active").strip().casefold() != "inactive"
            ]

    @staticmethod
    def _roster_name(player: Mapping[str, Any]) -> tuple[str, str]:
        first = str(player.get("preferred_name") or player.get("first_name") or "").strip()
        last = str(player.get("last_name") or "").strip()
        if first and last and last.casefold() in first.casefold():
            return first, last  # preferred_name already holds the full name
        return (f"{first} {last}".strip(), last)

    def _by_number(self, team: str, number: Any) -> Mapping[str, Any] | None:
        number = str(number or "").strip()
        if not number:
            return None
        return next((p for p in self._rosters.get(team, []) if str(p.get("number", "")).strip() == number), None)

    def _by_name(self, team: str, name: str) -> Mapping[str, Any] | None:
        target = re.sub(r"\s+", " ", name).strip().casefold()
        if not target:
            return None
        for player in self._rosters.get(team, []):
            full, _ = self._roster_name(player)
            official = f"{player.get('first_name', '')} {player.get('last_name', '')}".strip()
            if target in {full.casefold(), re.sub(r"\s+", " ", official).casefold()}:
                return player
        return None

    def person(self, team: str, number: Any = "", fallback: Any = "") -> dict[str, str]:
        player = self._by_number(team, number) or self._by_name(team, str(fallback or ""))
        if player is not None:
            full, last = self._roster_name(player)
            full, last = tidy_person_name(full), tidy_person_name(last)
            if full:
                return {"name": full, "last": last or full.split(" ")[-1], "number": str(player.get("number", "") or number or "")}
        name = tidy_person_name(fallback)
        if (not name or re.fullmatch(r"(?i)player \d*", name) or name.startswith("#")
                or name.casefold() in self._team_names):
            number = str(number or "").strip()
            label = f"No. {number}" if number else ""
            if number:
                self.unnamed.add((team, number))
            return {"name": label, "last": label, "number": number, "unknown": not number, "team": team}
        return {"name": name, "last": name.split(" ")[-1], "number": str(number or "")}


# -- scoring plays -------------------------------------------------------------

_INTERCEPT_TD = re.compile(r"intercepted by #(\d+)\s+(.+?)\s+at .+?, returned (\d+) yards?", re.I)
_RETURN_TD = re.compile(r"(kickoff|punt).*?returned by #(\d+)\s+(.+?)\s+for (\d+) yards?", re.I)
_FUMBLE_TD = re.compile(r"recovered by #(\d+)\s+(.+?)(?:\s+at\b|,|$)", re.I)
_PASS = re.compile(r"#(\d+)\s+(.+?)\s+complete to #(\d+)\s+(.+?)\s+for (-?\d+) yards?", re.I)
_RUN = re.compile(r"#(\d+)\s+(.+?)\s+run for (-?\d+) yards?", re.I)
_YARD_TD = re.compile(r"(\d+)-yard .*?touchdown (run|pass)", re.I)
_XP = re.compile(r"extra point good by (.+)$", re.I)
_TWO = re.compile(r"(.+?)\s+two-point conversion\s*(run|pass)?", re.I)
_FG = re.compile(r"(?:(\d+)[- ]yard\s+)?(.*?)\s*field goal good", re.I)


def _touchdown(description: str, team: str, names: Names) -> dict[str, Any]:
    match = _INTERCEPT_TD.search(description)
    if match:
        return {"how": "interception_return", "yards": _int(match.group(3)),
                "player": names.person(team, match.group(1), match.group(2))}
    match = _RETURN_TD.search(description)
    if match:
        return {"how": f"{match.group(1).lower()}_return", "yards": _int(match.group(4)),
                "player": names.person(team, match.group(2), match.group(3))}
    if "fumble" in description.lower():
        match = _FUMBLE_TD.search(description)
        if match:
            return {"how": "fumble_return", "yards": 0, "player": names.person(team, match.group(1), match.group(2))}
    match = _PASS.search(description)
    if match:
        return {"how": "pass", "yards": _int(match.group(5)),
                "player": names.person(team, match.group(3), match.group(4)),
                "passer": names.person(team, match.group(1), match.group(2))}
    match = _RUN.search(description)
    if match:
        return {"how": "run", "yards": _int(match.group(3)), "player": names.person(team, match.group(1), match.group(2))}
    match = _YARD_TD.search(description)
    if match:
        return {"how": match.group(2).lower(), "yards": _int(match.group(1)), "player": None}
    return {"how": "other", "yards": 0, "player": None}


def scoring_plays(summary: list[Mapping[str, Any]], names: Names) -> list[dict[str, Any]]:
    """One entry per score, a touchdown carrying the try that followed it, in
    quarter order. The running score is recounted from the points, so a score
    entered out of order still reads right."""
    plays: list[dict[str, Any]] = []
    rows = sorted(
        (r for r in summary if isinstance(r, Mapping)),
        key=lambda r: (quarter_number(r.get("quarter")) or 99, _int(r.get("created_at"))),
    )
    running = {"home": 0, "visitor": 0}
    for row in rows:
        team = str(row.get("team", "") or "")
        if team not in TEAMS:
            continue
        points = _int(row.get("points"))
        description = str(row.get("description", "") or "")
        label = str(row.get("label", "") or "")
        running[team] += points
        entry = {
            "quarter": quarter_number(row.get("quarter")),
            "team": team,
            "points": points,
            "home_score": running["home"],
            "visitor_score": running["visitor"],
            "at": _int(row.get("created_at")),
        }
        previous = plays[-1] if plays else None
        is_try = points in (1, 2) and not re.search(r"safety", f"{label} {description}", re.I)
        if is_try and previous and previous["kind"] == "touchdown" and previous["team"] == team and not previous.get("try"):
            if points == 1:
                match = _XP.search(description)
                kicker = names.person(team, "", match.group(1)) if match else None
                previous["try"] = {"kind": "kick", "player": kicker if kicker and kicker["name"] else None}
            else:
                match = _TWO.search(description)
                who = names.person(team, "", match.group(1)) if match else None
                previous["try"] = {"kind": "two", "player": who if who and who["name"] else None,
                                   "how": (match.group(2) or "").lower() if match else ""}
            previous["home_score"], previous["visitor_score"] = entry["home_score"], entry["visitor_score"]
            continue
        if points == 6:
            entry.update(kind="touchdown", **_touchdown(description, team, names))
        elif points == 3:
            match = _FG.search(description)
            entry.update(kind="field_goal", yards=_int(match.group(1)) if match else 0,
                         player=names.person(team, "", match.group(2)) if match and match.group(2) else None)
        elif points == 2:
            entry.update(kind="safety", yards=0, player=None)
        else:
            entry.update(kind="other", yards=0, player=None)
        plays.append(entry)
    return plays


def scoring_line(play: Mapping[str, Any]) -> str:
    """Newspaper scoring-summary style: 'Kingston Branham 20 run (Eli McKellar kick)'."""
    player = (play.get("player") or {}).get("name", "")
    yards = play.get("yards") or 0
    how = play.get("how", "")
    if play["kind"] == "touchdown":
        if not player and how in ("run", "pass"):
            text = f"{yards}-yard TD {how}"
        elif how == "pass":
            passer = (play.get("passer") or {}).get("name", "")
            text = f"{player} {yards} pass from {passer}".strip()
        elif how == "run":
            text = f"{player} {yards} run"
        elif how == "interception_return":
            text = f"{player} {yards} interception return"
        elif how in ("kickoff_return", "punt_return"):
            text = f"{player} {yards} {how.split('_')[0]} return"
        elif how == "fumble_return":
            text = f"{player} fumble return"
        else:
            text = f"{yards}-yard touchdown" if yards else "Touchdown"
        attempt = play.get("try")
        if attempt:
            who = (attempt.get("player") or {}).get("name", "")
            if attempt["kind"] == "kick":
                text += f" ({who} kick)" if who else " (kick)"
            else:
                text += f" ({who} {attempt.get('how') or 'conversion'})" if who else " (two-point conversion)"
        return text.strip()
    if play["kind"] == "field_goal":
        return f"{player} {yards} field goal".replace("  ", " ").strip() if yards else f"{player} field goal".strip()
    if play["kind"] == "safety":
        return "Safety"
    return "Score"


# -- big plays -----------------------------------------------------------------

def _matches_score(scores: list[Mapping[str, Any]], team: str, quarter: int, yards: int) -> Mapping[str, Any] | None:
    return next(
        (s for s in scores if s["kind"] == "touchdown" and s["team"] == team and s["quarter"] == quarter and s.get("yards") == yards),
        None,
    )


def big_plays(register: list[Mapping[str, Any]], scores: list[Mapping[str, Any]], names: Names,
              winner: str | None = None) -> list[dict[str, Any]]:
    """Long scores, turnovers, gains of 20+ yards and returns of 30+, each with
    the quarter it came in, ranked by weight and handed back in game order."""
    found: list[dict[str, Any]] = []
    used_scores: set[int] = set()
    for row in register:
        if row.get("undone"):
            continue
        play_type = str(row.get("play_type", "") or "").lower()
        quarter = quarter_number(row.get("quarter"))
        offense = str(row.get("offense", "") or "")
        defense = str(row.get("defense", "") or "")
        yards = _int(row.get("yards"))
        order = _int(row.get("created_at")) or _int(row.get("play_number"))
        turnover_type = str(row.get("turnover_type", "") or "").lower()
        if row.get("turnover") and turnover_type in ("interception", "fumble_recovery") and defense in TEAMS:
            if turnover_type == "interception":
                who = names.person(defense, row.get("turnover_player_number"), row.get("turnover_player_name"))
            else:
                who = names.person(defense, row.get("recoverer_number"), row.get("recoverer_name"))
            returned = _int(row.get("return_yards"))
            score = next((s for s in scores if s["kind"] == "touchdown" and s["team"] == defense and s["quarter"] == quarter
                          and s.get("how") in ("interception_return", "fumble_return") and id(s) not in used_scores), None)
            if score is not None:
                used_scores.add(id(score))
            found.append({"kind": turnover_type, "team": defense, "quarter": quarter, "order": order, "player": who,
                          "yards": returned, "score": score, "weight": 90 + (40 if score else 0) + returned})
            continue
        if offense not in TEAMS:
            continue
        if play_type in ("run", "rush", "pass") and yards >= BIG_GAIN_YARDS:
            if play_type == "pass":
                who = names.person(offense, row.get("receiver_number"), row.get("receiver_name"))
                passer = names.person(offense, row.get("passer_number") or row.get("player_number"),
                                      row.get("passer_name") or row.get("player_name"))
            else:
                who = names.person(offense, row.get("player_number"), row.get("player_name"))
                passer = None
            score = _matches_score(scores, offense, quarter, yards)
            if score is not None and id(score) in used_scores:
                score = None
            if score is not None:
                used_scores.add(id(score))
            found.append({"kind": "pass" if play_type == "pass" else "run", "team": offense, "quarter": quarter,
                          "order": order, "player": who, "passer": passer, "yards": yards, "score": score,
                          "weight": yards + (100 if score else 0)})
            continue
        returned = _int(row.get("return_yards"))
        kicking = str(row.get("kicking_team", "") or "")
        # On a kick the returning side is whoever did not kick (the row's
        # offense/defense follow the ball, not the kicking unit).
        receiving = ("visitor" if kicking == "home" else "home") if kicking in TEAMS else defense
        if play_type in ("kickoff", "punt") and receiving in TEAMS and returned >= BIG_RETURN_YARDS:
            who = names.person(receiving, row.get("returner_number"), row.get("returner_name"))
            score = next((s for s in scores if s["kind"] == "touchdown" and s["team"] == receiving and s["quarter"] == quarter
                          and s.get("how") == f"{play_type}_return" and id(s) not in used_scores), None)
            if score is not None:
                used_scores.add(id(score))
            found.append({"kind": f"{play_type}_return", "team": receiving, "quarter": quarter, "order": order,
                          "player": who, "yards": returned, "score": score, "weight": returned + (100 if score else 0)})
    # A long scoring play the register missed (score recorded without a matching
    # play row) still counts.
    for score in scores:
        if score["kind"] == "touchdown" and id(score) not in used_scores and _int(score.get("yards")) >= BIG_GAIN_YARDS:
            how = score.get("how", "")
            kind = how if how in ("run", "pass", "interception", "kickoff_return", "punt_return") else ("interception" if how == "interception_return" else "run")
            found.append({"kind": kind, "team": score["team"], "quarter": score["quarter"], "order": score.get("at", 0),
                          "player": score.get("player"), "passer": score.get("passer"), "yards": score.get("yards", 0),
                          "score": score, "weight": score.get("yards", 0) + 100})
    found = [p for p in found if not (p.get("player") or {}).get("unknown") and (p.get("player") or {}).get("name")]
    for play in found:
        if play["team"] == winner:
            play["weight"] += 15
    chosen = sorted(found, key=lambda p: -p["weight"])[:MAX_BIG_PLAYS]
    return sorted(chosen, key=lambda p: (p["quarter"], p["order"]))


def big_play_line(play: Mapping[str, Any]) -> str:
    """Short form for the graphic: 'Jaylen Hall 63-yd TD run'."""
    who = (play.get("player") or {}).get("name", "")
    yards = play.get("yards") or 0
    td = " TD" if play.get("score") else ""
    kind = play["kind"]
    if kind == "run":
        return f"{who} {yards}-yd{td} run"
    if kind == "pass":
        passer = (play.get("passer") or {}).get("last", "")
        return f"{who} {yards}-yd{td} catch" + (f" from {passer}" if passer else "")
    if kind == "interception":
        return f"{who} interception" + (f", {yards}-yd TD return" if td else (f", {yards}-yd return" if yards else ""))
    if kind == "fumble_recovery":
        return f"{who} fumble recovery" + (" for a TD" if td else "")
    if kind.endswith("_return"):
        return f"{who} {yards}-yd {kind.split('_')[0]}{td} return"
    return who


# -- standouts -----------------------------------------------------------------

def standouts(players: list[Mapping[str, Any]], team: str, names: Names) -> list[dict[str, Any]]:
    """Up to three players per team who did something worth a line: real
    yardage or a score, never a -2-yard 'leader'."""
    rows: list[dict[str, Any]] = []
    for p in players:
        if p.get("team") != team:
            continue
        who = names.person(team, p.get("number"), p.get("name"))
        if not who["name"]:
            continue
        tds = _int(p.get("touchdowns"))
        options = []
        rush, rush_att = _int(p.get("rushing_yards")), _int(p.get("rushing_attempts"))
        if rush_att and (rush >= 40 or _int(p.get("rushing_touchdowns"))):
            options.append(("rushing", rush, {"attempts": rush_att, "yards": rush}))
        passing, comp, att = _int(p.get("passing_yards")), _int(p.get("completions")), _int(p.get("pass_attempts"))
        if att and (passing >= 50 or _int(p.get("passing_touchdowns"))):
            options.append(("passing", passing, {"completions": comp, "attempts": att, "yards": passing,
                                                 "touchdowns": _int(p.get("passing_touchdowns")),
                                                 "interceptions": _int(p.get("interceptions_thrown"))}))
        rec, catches = _int(p.get("receiving_yards")), _int(p.get("receptions"))
        if catches and (rec >= 40 or _int(p.get("receiving_touchdowns"))):
            options.append(("receiving", rec, {"receptions": catches, "yards": rec}))
        ints, sacks, recoveries = _int(p.get("interceptions")), _int(p.get("sacks")), _int(p.get("fumble_recoveries"))
        if ints or sacks or recoveries:
            options.append(("defense", 45 * ints + 30 * sacks + 35 * recoveries,
                             {"interceptions": ints, "sacks": sacks, "recoveries": recoveries}))
        if _int(p.get("field_goals")):
            options.append(("kicking", 25 * _int(p.get("field_goals")),
                            {"field_goals": _int(p.get("field_goals")), "attempts": _int(p.get("field_goal_attempts"))}))
        if not options:
            continue
        category, weight, detail = max(options, key=lambda o: o[1])
        rows.append({"player": who, "category": category, "detail": detail, "touchdowns": tds,
                     "weight": weight + 20 * tds})
    rows.sort(key=lambda r: -r["weight"])
    return rows[:MAX_STANDOUTS]


def standout_line(row: Mapping[str, Any]) -> str:
    """Graphic form: '18 car, 157 yds, 3 TD'."""
    d = row["detail"]
    tds = row.get("touchdowns") or 0
    td = f", {tds} TD" if tds else ""
    category = row["category"]
    if category == "rushing":
        return f"{d['attempts']} car, {d['yards']} yds{td}"
    if category == "passing":
        text = f"{d['completions']}-{d['attempts']}, {d['yards']} yds"
        if d["touchdowns"]:
            text += f", {d['touchdowns']} TD"
        if d["interceptions"]:
            text += f", {d['interceptions']} INT"
        return text
    if category == "receiving":
        return f"{d['receptions']} rec, {d['yards']} yds{td}"
    if category == "kicking":
        return f"{d['field_goals']}-{d['attempts']} FG"
    parts = []
    if d["interceptions"]:
        parts.append(f"{d['interceptions']} INT")
    if d["sacks"]:
        parts.append(f"{d['sacks']} sack" + ("s" if d["sacks"] != 1 else ""))
    if d["recoveries"]:
        parts.append(f"{d['recoveries']} FR")
    return ", ".join(parts) + td


# -- facts -----------------------------------------------------------------------

def _final_scores(broadcast: Mapping[str, Any], state: Mapping[str, Any]) -> tuple[int, int]:
    home = broadcast.get("final_home_score")
    visitor = broadcast.get("final_visitor_score")
    if home is None:
        home = (state or {}).get("home_score", broadcast.get("home_score", 0))
    if visitor is None:
        visitor = (state or {}).get("visitor_score", broadcast.get("visitor_score", 0))
    return _int(home), _int(visitor)


def score_points(score: Mapping[str, Any]) -> int:
    """A score's points including its try."""
    attempt = score.get("try")
    return score["points"] + ((1 if attempt["kind"] == "kick" else 2) if attempt else 0)


def line_score(scores: list[Mapping[str, Any]], home: int, visitor: int) -> dict[str, Any] | None:
    """Points per quarter. None when the scoring plays don't add up to the
    final (a hand-adjusted score), so nothing wrong goes in print."""
    last = max([4] + [s["quarter"] for s in scores if s["quarter"]])
    periods = list(range(1, last + 1))
    table = {team: [0] * len(periods) for team in TEAMS}
    for s in scores:
        if s["quarter"] in periods:
            table[s["team"]][s["quarter"] - 1] += score_points(s)
    if sum(table["home"]) != home or sum(table["visitor"]) != visitor:
        return None
    labels = [str(p) if p <= 4 else ("OT" if last == 5 else f"OT{p - 4}") for p in periods]
    return {"labels": labels, "home": table["home"], "visitor": table["visitor"]}


def build_facts(
    *,
    broadcast: Mapping[str, Any],
    state: Mapping[str, Any],
    statistics: Mapping[str, Any],
    roster_for_team: RosterLookup | None = None,
) -> dict[str, Any]:
    names = Names(roster_for_team, [str(broadcast.get("home_team") or ""), str(broadcast.get("visitor_team") or "")])
    home_score, visitor_score = _final_scores(broadcast, state)
    teams = {}
    for team in TEAMS:
        identity = broadcast.get(f"{team}_identity") if isinstance(broadcast.get(f"{team}_identity"), Mapping) else {}
        totals = ((statistics.get("teams") or {}).get(team) or {}) if statistics else {}
        teams[team] = {
            "key": team,
            "name": tidy_team_name(broadcast.get(f"{team}_team") or identity.get("broadcast_name") or team.title()),
            "mascot": str(identity.get("mascot") or "").strip(),
            "score": home_score if team == "home" else visitor_score,
            "totals": dict(totals),
        }
    scores = scoring_plays(list(statistics.get("scoring_summary") or []), names) if statistics else []
    register = list(statistics.get("play_register") or []) if statistics else []
    players = [p for p in (statistics.get("players") or []) if isinstance(p, Mapping)] if statistics else []
    if home_score == visitor_score:
        winner = loser = None
    else:
        winner = "home" if home_score > visitor_score else "visitor"
        loser = "visitor" if winner == "home" else "home"
    return {
        "broadcast_id": str(broadcast.get("broadcast_id", "") or ""),
        "sport": str(broadcast.get("sport", "") or ""),
        "date": str(broadcast.get("date", "") or ""),
        "venue": str(broadcast.get("venue", "") or "").strip(),
        "teams": teams,
        "winner": winner,
        "loser": loser,
        "scoring": scores,
        "line_score": line_score(scores, home_score, visitor_score),
        # The scoring plays add up to the final: mid-game scores can be quoted.
        "scores_reliable": line_score(scores, home_score, visitor_score) is not None,
        "big_plays": big_plays(register, scores, names, winner),
        "standouts": {team: standouts(players, team, names) for team in TEAMS},
        "has_plays": bool(register or scores),
        # Numbers the story could only call "No. 33": missing from that team's roster.
        "unnamed": sorted(names.unnamed, key=lambda item: (item[0], _int(item[1]))),
    }


# -- the built-in writer ---------------------------------------------------------

def _pick(options: list[str], variant: int, slot: str, seed: str) -> str:
    digest = int(hashlib.sha1(f"{seed}:{slot}".encode()).hexdigest()[:8], 16)
    return options[(digest + variant) % len(options)]


def _cumulative(line: Mapping[str, Any] | None, periods: int) -> tuple[int, int] | None:
    if not line:
        return None
    return sum(line["home"][:periods]), sum(line["visitor"][:periods])


class _Refs:
    """Full name the first time a player appears, last name after that --
    unless two players in the story share that last name."""

    def __init__(self, facts: Mapping[str, Any]) -> None:
        self.seen: set[str] = set()
        self.team_names = {key: team["name"] for key, team in facts["teams"].items()}
        people = [p.get(k) for p in facts["big_plays"] for k in ("player", "passer")]
        people += [r["player"] for rows in facts["standouts"].values() for r in rows]
        last_names: dict[str, set[str]] = {}
        for person in people:
            if person and person.get("name"):
                last_names.setdefault((person.get("last") or "").casefold(), set()).add(person["name"])
        self.shared = {last for last, full in last_names.items() if len(full) > 1}

    def __call__(self, person: Mapping[str, Any] | None) -> str:
        if not person or not person.get("name"):
            return ""
        name = person["name"]
        if name.startswith("No. ") and person.get("team") in self.team_names:
            return f"{self.team_names[person['team']]}'s {name}"
        if name in self.seen and (person.get("last") or "").casefold() not in self.shared:
            return person.get("last") or name
        self.seen.add(name)
        return name


def _a_or_count(value: int, word: str, plural_word: str | None = None) -> str:
    """'a touchdown', 'an interception', 'two touchdowns'."""
    if value == 1:
        return f"{'an' if word[:1] in 'aeiou' else 'a'} {word}"
    return plural(value, word, plural_word)


def _feat(row: Mapping[str, Any]) -> str:
    """'ran for 157 yards and three touchdowns on 18 carries'."""
    d = row["detail"]
    tds = row.get("touchdowns") or 0
    category = row["category"]
    if category == "rushing":
        text = f"ran for {d['yards']} yards"
        if tds:
            text += f" and {_a_or_count(tds, 'touchdown')}"
        return text + f" on {plural(d['attempts'], 'carry', 'carries')}"
    if category == "passing":
        text = f"completed {d['completions']} of {d['attempts']} passes for {d['yards']} yards"
        if d["touchdowns"]:
            text += f" and {_a_or_count(d['touchdowns'], 'touchdown')}"
        return text
    if category == "receiving":
        text = f"caught {plural(d['receptions'], 'pass', 'passes')} for {d['yards']} yards"
        if tds:
            text += f" and {_a_or_count(tds, 'touchdown')}"
        return text
    if category == "kicking":
        made, tried = d["field_goals"], d["attempts"]
        if made == tried:
            if made == 1:
                return "made a field goal"
            return "made both of his field goal tries" if made == 2 else f"made all {count_word(made)} of his field goal tries"
        return f"made {count_word(made)} of {count_word(tried)} field goal tries"
    bits = []
    if d["interceptions"]:
        bits.append("had " + _a_or_count(d["interceptions"], "interception"))
    if d["sacks"]:
        bits.append(("had " if not bits else "") + _a_or_count(d["sacks"], "sack"))
    if d["recoveries"]:
        if bits:
            bits.append(_a_or_count(d["recoveries"], "fumble recovery", "fumble recoveries"))
        else:
            bits.append("recovered " + _a_or_count(d["recoveries"], "fumble"))
    text = " and ".join(bits) if bits else "made plays on defense"
    if tds:
        text += f" and scored {_a_or_count(tds, 'touchdown')}"
    return text


def _big_play_sentence(play: Mapping[str, Any], facts: Mapping[str, Any], variant: int, ref: _Refs) -> str:
    yards = play.get("yards") or 0
    when = quarter_phrase(play["quarter"])
    when_text = (" in overtime" if when == "overtime" else f" in the {when}") if when else ""
    score = play.get("score")
    team = facts["teams"][play["team"]]["name"]
    after = ""
    if score and facts.get("scores_reliable"):
        own = score["home_score"] if play["team"] == "home" else score["visitor_score"]
        other = score["visitor_score"] if play["team"] == "home" else score["home_score"]
        if own > other:
            took_lead = own - score_points(score) <= other
            after = f", putting {team} ahead {score_text(own, other)}" if took_lead else f" to make it {score_text(own, other)}"
        elif own == other:
            after = f" to tie it at {own}"
        else:
            after = f" to cut the lead to {score_text(own, other)}"
    kind = play["kind"]
    seed = facts["broadcast_id"] + str(play.get("order"))
    if kind == "pass":
        passer = ref(play.get("passer"))
        who = ref(play.get("player"))
        if score:
            return _pick([f"{passer} found {who} for a {yards}-yard touchdown{when_text}{after}.",
                          f"{who} caught a {yards}-yard touchdown pass from {passer}{when_text}{after}."], variant, "pass", seed)
        return f"{passer} connected with {who} for {yards} yards{when_text}."
    who = ref(play.get("player"))
    if kind == "run":
        if score:
            return _pick([f"{who} broke a {yards}-yard touchdown run{when_text}{after}.",
                          f"{who} scored on a {yards}-yard run{when_text}{after}."], variant, "run", seed)
        return f"{who} had a {yards}-yard run{when_text}."
    if kind == "interception":
        if score:
            return f"{who} intercepted a pass and returned it {yards} yards for a touchdown{when_text}{after}."
        return f"{who} intercepted a pass{when_text}" + (f" and returned it {yards} yards." if yards >= 20 else ".")
    if kind == "fumble_recovery":
        if score:
            return f"{who} recovered a fumble and scored{when_text}{after}."
        return f"{who} recovered a fumble{when_text}."
    if kind.endswith("_return"):
        what = kind.split("_")[0]
        if score:
            return f"{who} returned a {what} {yards} yards for a touchdown{when_text}{after}."
        return f"{who} returned a {what} {yards} yards{when_text}."
    return ""


def scoring_summary_lines(facts: Mapping[str, Any]) -> list[str]:
    """'Q1 West Point: Kingston Branham 20 run (Eli McKellar kick), West Point 7-0'.
    The running score is left off when the plays don't add up to the final."""
    lines = []
    for play in facts["scoring"]:
        text = f"{quarter_tag(play['quarter'])} {facts['teams'][play['team']]['name']}: {scoring_line(play)}"
        if facts.get("scores_reliable"):
            home, visitor = play["home_score"], play["visitor_score"]
            if home == visitor:
                text += f", {home}-{visitor}"
            else:
                leader = facts["teams"]["home" if home > visitor else "visitor"]["name"]
                text += f", {leader} {score_text(home, visitor)}"
        lines.append(text)
    return lines


def _trailed_at_half(facts: Mapping[str, Any]) -> bool:
    half = _cumulative(facts["line_score"], 2)
    if not half or not facts["winner"]:
        return False
    own, other = (half[0], half[1]) if facts["winner"] == "home" else (half[1], half[0])
    return own < other


def headline(facts: Mapping[str, Any], variant: int = 0) -> str:
    teams = facts["teams"]
    seed = facts["broadcast_id"]
    if not facts["winner"]:
        return f"{teams['visitor']['name']} and {teams['home']['name']} tie, {teams['home']['score']}-{teams['visitor']['score']}"
    w, l = teams[facts["winner"]], teams[facts["loser"]]
    margin = w["score"] - l["score"]
    if _trailed_at_half(facts):
        options = ["{w} rallies past {l}", "{w} comes back to beat {l}"]
    elif margin >= 21:
        options = ["{w} rolls past {l}", "{w} routs {l}", "{w} runs away from {l}"]
    elif margin >= 10:
        options = ["{w} beats {l}", "{w} handles {l}", "{w} pulls away from {l}"]
    elif margin >= 4:
        options = ["{w} tops {l}", "{w} gets past {l}", "{w} beats {l}"]
    else:
        options = ["{w} edges {l}", "{w} holds off {l}", "{w} slips past {l}"]
    text = _pick(options, variant, "headline", seed).format(w=w["name"], l=l["name"])
    return f"{text}, {w['score']}-{l['score']}"


def _flow_paragraph(facts: Mapping[str, Any]) -> str:
    """How the score moved, from the line score: the first quarter, halftime,
    the third quarter and the second half."""
    line = facts["line_score"]
    if not line or not facts["winner"]:
        return ""
    w_key = facts["winner"]
    w, l = facts["teams"][w_key], facts["teams"][facts["loser"]]

    def at(periods: int) -> tuple[int, int]:
        home, visitor = _cumulative(line, periods)
        return (home, visitor) if w_key == "home" else (visitor, home)

    q1, half, q3 = at(1), at(2), at(3)
    second = (w["score"] - half[0], l["score"] - half[1])
    if half[0] < half[1]:
        return (f"{l['name']} led {half[1]}-{half[0]} at halftime, but {w['name']} outscored "
                f"{l['name']} {second[0]}-{second[1]} after the break.")
    if q1 == (0, 0):
        text = "Neither team scored in the first quarter"
    elif q1[0] == q1[1]:
        text = f"The teams were tied {q1[0]}-{q1[1]} after the first quarter"
    else:
        text = f"{w['name'] if q1[0] > q1[1] else l['name']} led {score_text(*q1)} after the first quarter"
    if half[0] > half[1]:
        if q1[0] > q1[1]:
            text += f" and built a {half[0]}-{half[1]} lead by halftime"
        else:
            text += f", and {w['name']} took a {half[0]}-{half[1]} lead into halftime"
    else:
        text += f", and the game was tied {half[0]}-{half[1]} at halftime"
    text += "."
    if second == (0, 0):
        text += " Neither team scored in the second half."
    elif q3[1] >= q3[0]:
        where = f"trailed {q3[1]}-{q3[0]}" if q3[1] > q3[0] else f"was tied {q3[0]}-{q3[1]}"
        text += f" {w['name']} {where} after three quarters before taking over in the fourth."
    elif q3[0] - q3[1] >= 15 > half[0] - half[1]:
        text += f" {w['name']} pulled away in the third quarter and led {q3[0]}-{q3[1]} going to the fourth."
    fourth = (w["score"] - q3[0], l["score"] - q3[1])
    if fourth[1] - fourth[0] >= 10 and w["score"] - l["score"] <= 8:
        text += f" {l['name']} scored {fourth[1]} points in the fourth quarter but came up short."
    return text


def write_story(
    facts: Mapping[str, Any],
    *,
    variant: int = 0,
    sponsor_name: str = "",
    station_name: str = "",
    watch_link: str = "",
    include_scoring: bool = True,
) -> dict[str, Any]:
    """The built-in writer: a headline and short newspaper paragraphs, built
    from the facts alone."""
    teams = facts["teams"]
    seed = facts["broadcast_id"]
    day = weekday(facts["date"])
    on_day = f" on {day}" if day else ""
    at_venue = f" at {facts['venue']}" if facts["venue"] else ""
    paragraphs: list[str] = []
    ref = _Refs(facts)
    described: set[str] = set()

    if facts["winner"]:
        w, l = teams[facts["winner"]], teams[facts["loser"]]
        has_mascot = w["mascot"] and w["mascot"].casefold() not in w["name"].casefold()
        w_full = f"the {w['name']} {w['mascot']}" if has_mascot else w["name"]
        verb = _pick(["beat", "defeated"], variant, "verb", seed)
        star = (facts["standouts"].get(facts["winner"]) or [None])[0]
        if star:
            described.add(star["player"]["name"])
            name = ref(star["player"])
            lede = _pick([
                f"{name} {_feat(star)} as {w_full} {verb} {l['name']} {w['score']}-{l['score']}{on_day}{at_venue}.",
                f"{w_full[:1].upper()}{w_full[1:]} {verb} {l['name']} {w['score']}-{l['score']}{on_day}{at_venue} behind {name}, who {_feat(star)}.",
            ], variant, "lede", seed)
        else:
            lede = f"{w_full[:1].upper()}{w_full[1:]} {verb} {l['name']} {w['score']}-{l['score']}{on_day}{at_venue}."
    else:
        h, v = teams["home"], teams["visitor"]
        lede = f"{v['name']} and {h['name']} played to a {h['score']}-{v['score']} tie{on_day}{at_venue}."
    paragraphs.append(lede)

    flow = _flow_paragraph(facts)
    if flow:
        paragraphs.append(flow)

    top = sorted(sorted(facts["big_plays"], key=lambda p: -p.get("weight", 0))[:3], key=lambda p: (p["quarter"], p.get("order", 0)))
    sentences = [s for s in (_big_play_sentence(p, facts, variant, ref) for p in top) if s]
    if sentences:
        paragraphs.append(" ".join(sentences))

    def team_paragraph(team_key: str, opener: str, limit: int) -> str:
        rows = [r for r in facts["standouts"].get(team_key) or [] if r["player"]["name"] not in described][:limit]
        if not rows:
            return ""
        parts = []
        for r in rows:
            described.add(r["player"]["name"])
            parts.append(f"{ref(r['player'])} {_feat(r)}")
        body = parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + f", and {parts[-1]}"
        return f"{opener}{body}."

    if facts["winner"]:
        w, l = teams[facts["winner"]], teams[facts["loser"]]
        extra = team_paragraph(facts["winner"], _pick([f"For {w['name']}, ", f"Also for {w['name']}, "], variant, "w-open", seed), 2)
        if extra:
            paragraphs.append(extra)
        other = team_paragraph(facts["loser"], f"For {l['name']}, ", 2)
        if other:
            paragraphs.append(other)
        w_yards = _int(w["totals"].get("total_yards"))
        l_yards = _int(l["totals"].get("total_yards"))
        if w_yards and l_yards and w_yards > l_yards:
            rushing = _int(w["totals"].get("rushing_yards"))
            tail = f", including {rushing} on the ground" if rushing >= 0.6 * w_yards and rushing >= 150 else ""
            paragraphs.append(f"{w['name']} outgained {l['name']} {w_yards}-{l_yards} in total offense{tail}.")
    else:
        for key in TEAMS:
            other = team_paragraph(key, f"For {teams[key]['name']}, ", 2)
            if other:
                paragraphs.append(other)

    closing = []
    if sponsor_name:
        closing.append(f"{station_name + ' coverage' if station_name else 'Coverage'} is brought to you by {sponsor_name.rstrip('.')}.")
    if watch_link:
        closing.append(f"Watch the full game: {watch_link}")
    hashtags = [f"#{tag}Football" for tag in (re.sub(r"[^A-Za-z0-9]", "", t["name"]) for t in teams.values()) if tag]
    hashtags.append("#HighSchoolFootball")
    title = headline(facts, variant)
    story = "\n\n".join(paragraphs)
    scoring = scoring_summary_lines(facts)
    blocks = [title, story]
    if include_scoring and scoring:
        blocks.append("SCORING\n" + "\n".join(scoring))
    if closing:
        blocks.append(" ".join(closing))
    post = "\n\n".join(blocks + [" ".join(hashtags)])
    return {"headline": title, "paragraphs": paragraphs, "story": story, "closing": closing, "scoring": scoring,
            "hashtags": hashtags, "post_text": post, "word_count": len(story.split()), "writer": "built-in",
            "variant": variant}
