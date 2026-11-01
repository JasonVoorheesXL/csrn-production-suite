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


def players_of_the_game(facts: Mapping[str, Any], choices: Any) -> list[dict[str, Any]]:
    """Up to one Player of the Game per team, home first. `choices` is
    "home:2,visitor:1" (or a list of ids); a second pick for the same team is ignored."""
    ids = choices if isinstance(choices, (list, tuple)) else str(choices or "").split(",")
    picked: dict[str, dict[str, Any]] = {}
    for choice in ids:
        potg = player_of_the_game(facts, str(choice).strip())
        if potg and potg["team"] not in picked:
            picked[potg["team"]] = potg
    return [picked[team] for team in TEAMS if team in picked]


def player_of_the_game(facts: Mapping[str, Any], choice: str) -> dict[str, Any] | None:
    row = (facts.get("player_rows") or {}).get(str(choice or ""))
    pick = next((c for c in facts.get("players") or [] if c["id"] == choice), None)
    if not row or not pick:
        return None
    found = standouts([row], pick["team"], _NamesFromPick(pick))
    loose = found[0] if found else None
    if loose is None:
        loose = _any_line(row, pick)
    return {"team": pick["team"], "player": {"name": pick["name"], "last": pick["name"].split(" ")[-1],
                                             "number": pick["number"]}, "row": loose}


class _NamesFromPick:
    def __init__(self, pick: Mapping[str, Any]) -> None:
        self._pick = pick

    def person(self, team: str, number: Any = "", fallback: Any = "") -> dict[str, str]:
        name = self._pick["name"]
        return {"name": name, "last": name.split(" ")[-1], "number": self._pick["number"]}


def _any_line(p: Mapping[str, Any], pick: Mapping[str, Any]) -> dict[str, Any] | None:
    """A Player of the Game below the standout bar still gets their real numbers."""
    who = {"name": pick["name"], "last": pick["name"].split(" ")[-1], "number": pick["number"]}
    tds = _int(p.get("touchdowns"))
    if _int(p.get("rushing_attempts")):
        return {"player": who, "category": "rushing", "touchdowns": tds,
                "detail": {"attempts": _int(p.get("rushing_attempts")), "yards": _int(p.get("rushing_yards"))}}
    if _int(p.get("receptions")):
        return {"player": who, "category": "receiving", "touchdowns": tds,
                "detail": {"receptions": _int(p.get("receptions")), "yards": _int(p.get("receiving_yards"))}}
    if _int(p.get("pass_attempts")):
        return {"player": who, "category": "passing", "touchdowns": tds,
                "detail": {"completions": _int(p.get("completions")), "attempts": _int(p.get("pass_attempts")),
                           "yards": _int(p.get("passing_yards")), "touchdowns": _int(p.get("passing_touchdowns")),
                           "interceptions": _int(p.get("interceptions_thrown"))}}
    return None


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
    events = {str(e.get("id", "")): e for e in (state or {}).get("events") or [] if isinstance(e, Mapping)}
    raw_names = {team: str(broadcast.get(f"{team}_team") or "") for team in TEAMS}
    every_player = {}
    for p in players:
        every_player[(str(p.get("team", "")), str(p.get("number", "") or "").strip())] = p
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
        "timeline": timeline(register, scores, events, names, teams),
        "penalties": _penalties(register, teams, raw_names),
        "players": player_choices(players, names, teams),
        "player_rows": {f"{team}:{number}": row for (team, number), row in every_player.items() if number},
        "has_plays": bool(register or scores),
        # Numbers the story could only call "No. 33": missing from that team's roster.
        "unnamed": sorted(names.unnamed, key=lambda item: (item[0], _int(item[1]))),
    }


# -- drives and the game timeline -------------------------------------------------

_KICK_TYPES = {"kickoff", "punt", "kick"}
_SNAP_TYPES = {"run", "rush", "pass"}
LONG_PLAY_YARDS = 25
STOP_ZONE_YARDS = 30


def yards_to_goal(spot: Any, direction: Any) -> int | None:
    """'RIGHT 20' for a team moving right is 20 yards from the goal; for a team
    moving left it is 80."""
    text = re.sub(r"\s+", " ", str(spot or "").strip().upper())
    heading = str(direction or "").strip().upper()
    if text in ("50", "MIDFIELD"):
        return 50
    match = re.fullmatch(r"(LEFT|RIGHT) (GOAL|\d+)", text)
    if not match or heading not in ("LEFT", "RIGHT"):
        return None
    yards = 0 if match.group(2) == "GOAL" else int(match.group(2))
    return yards if match.group(1) == heading else 100 - yards


def _other(team: str) -> str:
    return "visitor" if team == "home" else "home"


def spot_phrase(ytg: int | None, offense: str, teams: Mapping[str, Any]) -> str:
    """'the Caledonia 35' / 'midfield', from the offense's yards to goal."""
    if ytg is None or not 0 < ytg < 100:
        return ""
    if ytg == 50:
        return "midfield"
    if ytg > 50:
        return f"the {teams[offense]['name']} {100 - ytg}"
    return f"the {teams[_other(offense)]['name']} {ytg}"


def _heading(row: Mapping[str, Any], team: str, events: Mapping[str, Any]) -> Any:
    event = events.get(str(row.get("event_id", "") or "")) or {}
    return (event.get("before") or {}).get(f"{team}_direction")


def drive_for(index: int, register: list[Mapping[str, Any]], events: Mapping[str, Any]) -> dict[str, Any] | None:
    """The possession that ended with register[index]: how many snaps, how far
    from the goal it started, and what gave the team the ball."""
    row = register[index]
    team = str(row.get("offense", "") or "")
    if team not in TEAMS:
        return None
    first = index
    while first > 0:
        prev = register[first - 1]
        if prev.get("undone"):
            first -= 1
            continue
        if str(prev.get("offense", "") or "") != team or str(prev.get("play_type", "")).lower() in _KICK_TYPES or prev.get("turnover"):
            break
        first -= 1
    rows = [r for r in register[first:index + 1] if not r.get("undone")]
    snaps = sum(1 for r in rows if str(r.get("play_type", "")).lower() in _SNAP_TYPES)
    start = rows[0]
    began = ""
    if first > 0:
        prev = register[first - 1]
        kind = str(prev.get("play_type", "")).lower()
        turnover = str(prev.get("turnover_type", "") or "").lower() if prev.get("turnover") else ""
        began = {"interception": "interception", "fumble_recovery": "fumble recovery", "downs": "fourth-down stop"}.get(
            turnover, "punt" if kind == "punt" else "kickoff" if kind == "kickoff" else "")
    return {"plays": snaps, "yards": yards_to_goal(start.get("ball_spot"), _heading(start, team, events)), "began": began}


def _penalties(register: list[Mapping[str, Any]], teams: Mapping[str, Any], raw_names: Mapping[str, str]) -> dict[str, dict[str, int]]:
    counts = {team: {"count": 0, "yards": 0} for team in TEAMS}
    lookup = {}
    for team in TEAMS:
        for name in (teams[team]["name"], raw_names.get(team, "")):
            if name:
                lookup[name.casefold()] = team
    for row in register:
        if str(row.get("play_type", "")).lower() != "penalty" or row.get("undone"):
            continue
        match = re.match(r"Penalty, (.+?), (\d+) yards?", str(row.get("result", "") or ""))
        team = lookup.get(match.group(1).strip().casefold()) if match else None
        if team:
            counts[team]["count"] += 1
            counts[team]["yards"] += int(match.group(2))
    return counts


def timeline(
    register: list[Mapping[str, Any]],
    scores: list[dict[str, Any]],
    events: Mapping[str, Any],
    names: Names,
    teams: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Everything the story walks through, in game order: each score (with its
    drive), turnovers, fourth-down stops near the goal, and long plays."""
    by_time = {_int(row.get("created_at")): i for i, row in enumerate(register) if _int(row.get("created_at"))}
    items: list[dict[str, Any]] = []
    scoring_rows: set[int] = set()
    for score in scores:
        index = by_time.get(score.get("at", 0))
        drive = None
        if index is not None:
            scoring_rows.add(index)
            if score["kind"] == "field_goal" or (score["kind"] == "touchdown" and score.get("how") in ("run", "pass")):
                drive = drive_for(index, register, events)
                if drive and drive["plays"] < 2:
                    drive = None
                if drive and score["kind"] == "touchdown" and (drive["yards"] is None or drive["yards"] < (score.get("yards") or 0)):
                    drive["yards"] = None
        items.append({"type": "score", "quarter": score["quarter"], "order": score.get("at", 0), "team": score["team"],
                      "score": score, "drive": drive})
    for index, row in enumerate(register):
        if row.get("undone") or index in scoring_rows:
            continue
        quarter = quarter_number(row.get("quarter"))
        order = _int(row.get("created_at"))
        offense = str(row.get("offense", "") or "")
        defense = str(row.get("defense", "") or "")
        play_type = str(row.get("play_type", "")).lower()
        turnover = str(row.get("turnover_type", "") or "").lower() if row.get("turnover") else ""
        if turnover in ("interception", "fumble_recovery") and defense in TEAMS:
            if turnover == "interception":
                who = names.person(defense, row.get("turnover_player_number"), row.get("turnover_player_name"))
                victim = names.person(offense, row.get("passer_number") or row.get("player_number"),
                                      row.get("passer_name") or row.get("player_name")) if offense in TEAMS else None
            else:
                who = names.person(defense, row.get("recoverer_number"), row.get("recoverer_name"))
                victim = names.person(offense, row.get("player_number"), row.get("player_name")) if offense in TEAMS else None
            if any(s["kind"] == "touchdown" and s["team"] == defense and s["quarter"] == quarter
                   and s.get("how") in ("interception_return", "fumble_return") for s in scores):
                continue  # told as the score
            items.append({"type": turnover, "quarter": quarter, "order": order, "team": defense, "player": who,
                          "victim": victim if victim and victim.get("name") and not victim.get("unknown") else None,
                          "yards": _int(row.get("return_yards"))})
        elif turnover == "downs" and offense in TEAMS:
            ytg = yards_to_goal(row.get("ball_spot"), _heading(row, offense, events))
            if ytg is not None and ytg <= STOP_ZONE_YARDS:
                items.append({"type": "downs", "quarter": quarter, "order": order, "team": defense,
                              "spot": spot_phrase(ytg, offense, teams), "offense": offense})
        elif play_type in _SNAP_TYPES and offense in TEAMS and _int(row.get("yards")) >= LONG_PLAY_YARDS:
            if play_type == "pass":
                who = names.person(offense, row.get("receiver_number"), row.get("receiver_name"))
                passer = names.person(offense, row.get("passer_number") or row.get("player_number"),
                                      row.get("passer_name") or row.get("player_name"))
            else:
                who, passer = names.person(offense, row.get("player_number"), row.get("player_name")), None
            items.append({"type": "pass" if play_type == "pass" else "run", "quarter": quarter, "order": order,
                          "team": offense, "player": who, "passer": passer, "yards": _int(row.get("yards"))})
        elif play_type in ("kickoff", "punt") and _int(row.get("return_yards")) >= BIG_RETURN_YARDS:
            kicking = str(row.get("kicking_team", "") or "")
            receiving = _other(kicking) if kicking in TEAMS else defense
            if receiving in TEAMS:
                items.append({"type": f"{play_type}_return", "quarter": quarter, "order": order, "team": receiving,
                              "player": names.person(receiving, row.get("returner_number"), row.get("returner_name")),
                              "yards": _int(row.get("return_yards"))})
    told = {(s["team"], s["quarter"], s.get("yards"), (s.get("player") or {}).get("name")) for s in scores if s["kind"] == "touchdown"}
    items = [i for i in items if not (i["type"] in ("run", "pass")
                                      and (i["team"], i["quarter"], i["yards"], (i.get("player") or {}).get("name")) in told)]
    items = [i for i in items if i["type"] == "score" or i["type"] == "downs"
             or ((i.get("player") or {}).get("name") and not (i.get("player") or {}).get("unknown"))]
    return sorted(items, key=lambda i: (i["quarter"] or 99, i["order"]))


def player_choices(players: list[Mapping[str, Any]], names: Names, teams: Mapping[str, Any]) -> list[dict[str, str]]:
    """Everyone with a recorded stat, for the Player of the Game picker."""
    choices = []
    for p in players:
        team = str(p.get("team", "") or "")
        number = str(p.get("number", "") or "").strip()
        if team not in TEAMS or not number:
            continue
        who = names.person(team, number, p.get("name"))
        if not who["name"]:
            continue
        impact = (_int(p.get("rushing_yards")) + _int(p.get("passing_yards")) + _int(p.get("receiving_yards"))
                  + _int(p.get("kickoff_return_yards")) + _int(p.get("punt_return_yards")) + 20 * _int(p.get("touchdowns"))
                  + 40 * _int(p.get("interceptions")) + 30 * _int(p.get("sacks")) + 30 * _int(p.get("fumble_recoveries"))
                  + 10 * _int(p.get("field_goals")))
        choices.append({"id": f"{team}:{number}", "team": team, "number": number, "name": who["name"], "impact": impact,
                        "label": f"{teams[team]['name']} · #{number} "
                                 + ("(not on the roster)" if who["name"].startswith("No. ") else who["name"])})
    # Best performers first, so the likely pick is near the top of the list.
    return sorted(choices, key=lambda c: (c["team"] != "home", -c["impact"], _int(c["number"])))


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
        people += [i.get(k) for i in facts.get("timeline") or [] for k in ("player", "passer", "victim")]
        people += [i["score"].get(k) for i in facts.get("timeline") or [] if i["type"] == "score" for k in ("player", "passer")]
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
            return _pick([f"{passer} found {who} for {_a(yards)} {yards}-yard touchdown{when_text}{after}.",
                          f"{who} caught {_a(yards)} {yards}-yard touchdown pass from {passer}{when_text}{after}."], variant, "pass", seed)
        return f"{passer} connected with {who} for {yards} yards{when_text}."
    who = ref(play.get("player"))
    if kind == "run":
        if score:
            return _pick([f"{who} broke {_a(yards)} {yards}-yard touchdown run{when_text}{after}.",
                          f"{who} scored on {_a(yards)} {yards}-yard run{when_text}{after}."], variant, "run", seed)
        return f"{who} had {_a(yards)} {yards}-yard run{when_text}."
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


def _after(score: Mapping[str, Any], team: str, facts: Mapping[str, Any]) -> str:
    """', putting West Point ahead 7-0' / ' to make it 21-3' / ' to tie it at 14'."""
    if not facts.get("scores_reliable"):
        return ""
    name = facts["teams"][team]["name"]
    own = score["home_score"] if team == "home" else score["visitor_score"]
    other = score["visitor_score"] if team == "home" else score["home_score"]
    if own > other:
        return f", putting {name} ahead {score_text(own, other)}" if own - score_points(score) <= other else f", making it {score_text(own, other)}"
    if own == other:
        return f", tying it at {own}"
    return f", cutting the lead to {score_text(own, other)}"


def _a(number: int) -> str:
    """'an 11-play', 'an 8-play', 'a 7-play'."""
    spoken = str(number)
    return "an" if spoken.startswith("8") or spoken in ("11", "18") else "a"


def _yards_out(yards: int) -> str:
    return "1 yard out" if yards == 1 else f"{yards} yards out"


def _drive_text(drive: Mapping[str, Any] | None) -> str:
    """'a 7-play, 65-yard drive' (yards only when the start spot is known)."""
    if not drive:
        return ""
    yards = f", {drive['yards']}-yard" if drive.get("yards") else ""
    return f"{_a(drive['plays'])} {drive['plays']}-play{yards} drive"


def _score_sentence(item: Mapping[str, Any], facts: Mapping[str, Any], variant: int, ref: _Refs) -> str:
    score, drive = item["score"], item.get("drive")
    team = facts["teams"][item["team"]]["name"]
    after = _after(score, item["team"], facts)
    seed = facts["broadcast_id"] + str(item["order"])
    yards = score.get("yards") or 0
    drive_text = _drive_text(drive)
    followed = f" that followed {_a(8) if drive['began'][:1] in 'aeiou' else 'a'} {drive['began']}" if drive and drive.get("began") in ("interception", "fumble recovery", "fourth-down stop") else ""
    how = score.get("how", "")
    if score["kind"] == "touchdown" and how == "run" and score.get("player"):
        who = ref(score["player"])
        if drive_text:
            return _pick([f"{who} capped {drive_text}{followed} with {_a(yards)} {yards}-yard touchdown run{after}.",
                          f"{who} finished {drive_text}{followed} by scoring from {_yards_out(yards)}{after}."], variant, "drive-run", seed)
        if yards < 20:
            return f"{who} scored from {_yards_out(yards)}{after}."
        return _pick([f"{who} scored on {_a(yards)} {yards}-yard run{after}.",
                      f"{who} broke {_a(yards)} {yards}-yard touchdown run{after}."], variant, "run", seed)
    if score["kind"] == "touchdown" and how == "pass" and score.get("player"):
        passer, who = ref(score.get("passer")), ref(score["player"])
        lead = f"{passer} hit {who} for {_a(yards)} {yards}-yard touchdown" if passer else f"{who} caught {_a(yards)} {yards}-yard touchdown pass"
        if drive_text:
            return f"{lead}, capping {drive_text}{followed}{after}."
        return f"{lead}{after}."
    if score["kind"] == "touchdown" and how == "interception_return" and score.get("player"):
        return f"{ref(score['player'])} intercepted a pass and returned it {yards} yards for a touchdown{after}."
    if score["kind"] == "touchdown" and how in ("kickoff_return", "punt_return") and score.get("player"):
        return f"{ref(score['player'])} returned a {how.split('_')[0]} {yards} yards for a touchdown{after}."
    if score["kind"] == "touchdown" and how == "fumble_return" and score.get("player"):
        return f"{ref(score['player'])} picked up a fumble and scored{after}."
    team_after = after.replace(f", putting {team} ahead", " to go ahead")
    if score["kind"] == "touchdown":
        return f"{team} scored on {_a(yards)} {yards}-yard touchdown{team_after}." if yards else f"{team} scored a touchdown{team_after}."
    if score["kind"] == "field_goal":
        kicker = ref(score.get("player")) or team
        if kicker == team:
            after = team_after
        length = f"{_a(score['yards'])} {score['yards']}-yard field goal" if score.get("yards") else "a field goal"
        if drive_text:
            return f"{kicker} kicked {length} at the end of {drive_text}{after}."
        return f"{kicker} kicked {length}{after}."
    if score["kind"] == "safety":
        return f"{team} scored a safety{team_after}."
    return ""


def _item_sentence(item: Mapping[str, Any], facts: Mapping[str, Any], variant: int, ref: _Refs) -> str:
    kind = item["type"]
    if kind == "score":
        return _score_sentence(item, facts, variant, ref)
    yards = item.get("yards") or 0
    team = facts["teams"][item["team"]]["name"]

    def whose(person: Mapping[str, Any] | None) -> str:
        """'Lafayette's Hugh Trost': on a change of possession the reader (and
        the AI writer) can't tell whose player it was from the name alone."""
        name = ref(person)
        return name if name.startswith(f"{team}'s ") else f"{team}'s {name}"

    if kind == "interception":
        victim = f" off {ref(item['victim'])}" if item.get("victim") else ""
        back = f" and returned it {yards} yards" if yards >= 15 else ""
        return f"{whose(item['player'])} intercepted a pass{victim}{back}."
    if kind == "fumble_recovery":
        return f"{whose(item['player'])} recovered a fumble."
    if kind == "downs":
        where = f" at {item['spot']}" if item.get("spot") else ""
        return f"{facts['teams'][item['team']]['name']}'s defense stopped {facts['teams'][item['offense']]['name']} on downs{where}."
    if kind == "run":
        return f"{ref(item['player'])} broke {_a(yards)} {yards}-yard run."
    if kind == "pass":
        passer = ref(item.get("passer"))
        return f"{passer} connected with {ref(item['player'])} for {yards} yards." if passer else f"{ref(item['player'])} caught {_a(yards)} {yards}-yard pass."
    if kind.endswith("_return"):
        return f"{whose(item['player'])} returned a {kind.split('_')[0]} {yards} yards."
    return ""


def _quarter_paragraphs(facts: Mapping[str, Any], variant: int, ref: _Refs) -> list[str]:
    """One paragraph per quarter, every score and turning point in order."""
    items = facts.get("timeline") or []
    if not items:
        return []
    last = max([4] + [i["quarter"] for i in items if i["quarter"]])
    paragraphs = []
    for quarter in range(1, last + 1):
        sentences = [s for s in (_item_sentence(i, facts, variant, ref) for i in items if i["quarter"] == quarter) if s]
        scored = any(i["type"] == "score" for i in items if i["quarter"] == quarter)
        when = "overtime" if quarter > 4 else f"the {_QUARTER_NAMES[quarter]}"
        if not scored:
            sentences.append("Neither team scored." if sentences else f"Neither team scored in {when}.")
        sentences = [s for s in sentences if s]
        if not sentences:
            continue
        first = sentences[0]
        if not first.startswith("Neither"):
            sentences[0] = f"In {when}, {first}"
        paragraphs.append(" ".join(sentences))
    return paragraphs


def _team_stats_paragraph(facts: Mapping[str, Any]) -> str:
    teams = facts["teams"]
    order = [facts["winner"], facts["loser"]] if facts["winner"] else ["visitor", "home"]
    parts = []
    for key in order:
        t = teams[key]["totals"]
        rushing, passing = _int(t.get("rushing_yards")), _int(t.get("passing_yards"))
        if rushing > 0 and passing > 0:
            parts.append(f"{teams[key]['name']} ran for {rushing} yards and threw for {passing}")
        elif rushing > 0 or passing > 0:
            parts.append(f"{teams[key]['name']} {'ran' if rushing > 0 else 'threw'} for {max(rushing, passing)} yards")
    text = ("; ".join(parts) + ".") if parts else ""
    turnovers = [(key, _int(teams[key]["totals"].get("turnovers_gained"))) for key in order]
    forced = [f"{teams[k]['name']} forced {plural(n, 'turnover')}" for k, n in turnovers if n]
    if len(forced) == 2 and turnovers[0][1] == turnovers[1][1]:
        forced = [f"Each team forced {plural(turnovers[0][1], 'turnover')}"]
    if forced:
        text += " " + " and ".join(forced) + "."
    flags = facts.get("penalties") or {}
    flagged = [(teams[k]["name"], flags[k]["count"], flags[k]["yards"]) for k in order if flags.get(k, {}).get("count")]
    if flagged:
        first = f"{flagged[0][0]} was penalized {plural(flagged[0][1], 'time')} for {flagged[0][2]} yards"
        if len(flagged) > 1:
            first += f" and {flagged[1][0]} {plural(flagged[1][1], 'time')} for {flagged[1][2]}"
        text += f" {first}."
    return text.strip()


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
    player_of_game: str = "",
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

    paragraphs.extend(_quarter_paragraphs(facts, variant, ref))

    picks = players_of_the_game(facts, player_of_game)
    for potg in picks:
        if potg["player"]["name"] in described:
            potg = {**potg, "row": None}  # the lede already gave his numbers
        described.add(potg["player"]["name"])
        who = potg["player"]["name"]
        team_name = facts["teams"][potg["team"]]["name"]
        feat = f", who {_feat(potg['row'])}" if potg["row"] else ""
        if len(picks) > 1:
            paragraphs.append(f"{team_name}'s Player of the Game: {who}{feat}.")
        else:
            label = f"The {station_name} Player of the Game" if station_name else "The Player of the Game"
            paragraphs.append(f"{label}: {who} of {team_name}{feat}.")

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
        extra = team_paragraph(facts["winner"], _pick([f"For {w['name']}, ", f"Also for {w['name']}, "], variant, "w-open", seed), 3)
        if extra:
            paragraphs.append(extra)
        other = team_paragraph(facts["loser"], f"For {l['name']}, ", 3)
        if other:
            paragraphs.append(other)
        w_yards = _int(w["totals"].get("total_yards"))
        l_yards = _int(l["totals"].get("total_yards"))
        stats = _team_stats_paragraph(facts)
        if w_yards and l_yards and w_yards > l_yards:
            stats = f"{w['name']} outgained {l['name']} {w_yards}-{l_yards} in total offense. " + stats
        if stats.strip():
            paragraphs.append(stats.strip())
    else:
        for key in TEAMS:
            other = team_paragraph(key, f"For {teams[key]['name']}, ", 3)
            if other:
                paragraphs.append(other)
        stats = _team_stats_paragraph(facts)
        if stats:
            paragraphs.append(stats)

    closing = []
    if sponsor_name:
        closing.append(f"{station_name + ' coverage' if station_name else 'Coverage'} is brought to you by {sponsor_name.rstrip('.')}.")
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


def fact_sheet(facts: Mapping[str, Any], written: Mapping[str, Any]) -> str:
    """What the AI writer gets: the final, the scoring, the app's own game log
    (drives, turnovers, stops), standouts and team numbers -- nothing more."""
    teams = facts["teams"]
    h, v = teams["home"], teams["visitor"]
    lines = [f"GAME: {v['name']} at {h['name']}" + (f" ({h['mascot']})" if h["mascot"] else ""),
             f"DATE: {ap_date(facts['date'])}" if facts["date"] else "",
             f"VENUE: {facts['venue']}" if facts["venue"] else "",
             f"FINAL: {h['name']} {h['score']}, {v['name']} {v['score']}",
             f"MASCOTS: {h['name']} {h['mascot'] or '-'}; {v['name']} {v['mascot'] or '-'}"]
    line = facts.get("line_score")
    if line:
        lines.append("LINE SCORE (by quarter): " + "; ".join(
            f"{teams[key]['name']} {' '.join(str(n) for n in line[key])} = {teams[key]['score']}" for key in ("visitor", "home")))
    else:
        lines.append("NOTE: the recorded scoring plays do not add up to the final score, so do not quote running scores.")
    if written.get("scoring"):
        lines.append("SCORING SUMMARY (in order):\n" + "\n".join(f"- {s}" for s in written["scoring"]))
    lines.append("GAME LOG FROM THE STATION'S STATISTICIAN (accurate; rewrite it, keep every number):\n" + "\n".join(
        written["paragraphs"]))
    for key in TEAMS:
        rows = facts["standouts"].get(key) or []
        if rows:
            lines.append(f"STANDOUTS, {teams[key]['name']}: " + "; ".join(
                f"{r['player']['name']} ({standout_line(r)})" for r in rows))
    for key in TEAMS:
        t = teams[key]["totals"]
        flags = (facts.get("penalties") or {}).get(key) or {}
        lines.append(f"TEAM STATS, {teams[key]['name']}: total {_int(t.get('total_yards'))} yds, rushing {_int(t.get('rushing_yards'))}, "
                     f"passing {_int(t.get('passing_yards'))}, turnovers forced {_int(t.get('turnovers_gained'))}, "
                     f"penalties {flags.get('count', 0)} for {flags.get('yards', 0)} yds")
    if facts.get("unnamed"):
        lines.append("NOTE: some players are known only by number (not on the roster); refer to them as the app's game log does.")
    lines.append("NO GAME CLOCK was recorded: say which quarter, never a time.")
    return "\n".join(line for line in lines if line)
