"""Basketball play reels: which plays can become a reel, and the script that draws one.

Everything comes from the console's event ledger: where the shot was taken, who
assisted, who was on the floor at that moment and the score after it. A miss is
never a reel of its own and the player on the wrong end of a block or a steal is
not named, so no reel is about somebody's bad moment.
"""
from __future__ import annotations

from typing import Any, Callable, Mapping

from hoops_shot_geometry import COURT_LENGTH, COURT_WIDTH, RIM_X, RIM_Y
from postgame_story import quarter_phrase, quarter_tag
from reel_story import DANCES, GRADE_NAMES, THEMES

TEAMS = ("home", "visitor")
KIND_LABELS = {"three": "Three-pointers", "dunk": "Dunks", "layup": "Layups", "jumper": "Jump shots", "block": "Blocks", "steal": "Steals"}
HALF_COURT = COURT_LENGTH / 2
DEFAULT_SPOTS = {"three": (60.0, 25.0), "dunk": (64.0, 21.0), "layup": (64.0, 21.0), "jumper": (66.0, 34.0), "block": (70.0, 30.0), "steal": (58.0, 25.0)}
WORDS = {"three": "THREE!", "dunk": "SLAM!", "layup": "BUCKET!", "jumper": "BUCKET!", "block": "BLOCKED!", "steal": "STOLEN!"}
Names = Mapping[str, Mapping[str, Mapping[str, str]]]


def _int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _clock(seconds: Any) -> str:
    total = _int(seconds)
    return f"{total // 60}:{total % 60:02d}"


def _person(names: Names, side: str, player_id: Any) -> dict[str, str] | None:
    pid = str(player_id or "")
    known = (names.get(side) or {}).get(pid) or {}
    name, number = str(known.get("name", "") or ""), str(known.get("number", "") or "")
    if not pid or not (name or number):
        return None
    return {"id": pid, "name": name or f"#{number}", "last": str(known.get("last", "") or name or f"#{number}"), "number": number}


def _shot_kind(payload: Mapping[str, Any]) -> str:
    if _int(payload.get("points")) == 3:
        return "three"
    if "dunk" in (payload.get("tags") or []):
        return "dunk"
    return "layup" if payload.get("zone") == "rim" else "jumper"


def _spot(payload: Mapping[str, Any], kind: str) -> dict[str, float]:
    """Inside the half of the floor the reel shows. Stored spots are from the attacker's view."""
    try:
        x, y = float(payload["spotX"]), float(payload["spotY"])
    except (KeyError, TypeError, ValueError):
        x, y = DEFAULT_SPOTS[kind]
    if x < HALF_COURT:
        x, y = COURT_LENGTH - x, COURT_WIDTH - y
    return {"x": x, "y": y}


def plays(state: Mapping[str, Any], names: Names, teams: Mapping[str, str]) -> list[dict[str, Any]]:
    """Every made basket, block and steal with a known player, oldest first."""
    events = ((state.get("hoops") or {}).get("hoops_events") or [])
    events = [e for e in events if isinstance(e, Mapping) and not e.get("voided")]
    notes: dict[str, dict[str, Any]] = {}
    for event in events:
        if event.get("event_type") == "PLAY_NOTE":
            payload = event.get("payload") or {}
            notes.setdefault(str(payload.get("targetEventId", "")), {}).update({k: v for k, v in payload.items() if k != "targetEventId"})
    floor: dict[str, list[str]] = {"home": [], "visitor": []}
    score = {"home": 0, "visitor": 0}
    found: list[dict[str, Any]] = []

    def add(event, payload, kind, side, hero, helper=None, other=None):
        period = str(payload.get("period", "") or "")
        tag = quarter_tag(period)
        what = {"three": "3-pointer", "dunk": "dunk", "layup": "layup", "jumper": "jumper", "block": "block", "steal": "steal"}[kind]
        help_note = f", assist {helper['last']}" if helper else ""
        found.append({
            "id": str(event.get("event_id", "")), "kind": kind, "team": side, "player": hero, "helper": helper,
            "other_number": (other or {}).get("number", ""), "other_id": (other or {}).get("id", ""), "spot": _spot(payload, kind), "points": _int(payload.get("points")),
            "period": period, "clock": _clock(payload.get("clockSeconds")),
            "floor": {team: list(floor[team]) for team in TEAMS}, "score": dict(score), "and_one": False,
            "label": " · ".join(part for part in (tag, teams.get(side, ""), f"{hero['name']} {what}{help_note}") if part),
        })

    for event in events:
        kind_of_event = event.get("event_type")
        payload = {**(event.get("payload") or {}), **notes.get(str(event.get("event_id")), {})}
        side = str(payload.get("team", ""))
        if kind_of_event == "LINEUP_SET" and side in TEAMS:
            floor[side] = [str(p) for p in payload.get("playerIds") or []]
        elif kind_of_event == "SUBSTITUTION" and side in TEAMS:
            floor[side] = [str(payload.get("inPlayerId", "")) if p == str(payload.get("outPlayerId", "")) else p for p in floor[side]]
        elif kind_of_event == "FREE_THROW" and side in TEAMS and payload.get("made"):
            score[side] += 1
        elif kind_of_event == "FOUL" and payload.get("andOne") and found and found[-1]["kind"] not in ("block", "steal"):
            if str(payload.get("drewFoulOn", "")) == found[-1]["player"]["id"]:
                found[-1]["and_one"] = True
                found[-1]["label"] += " (and one)"
        elif kind_of_event == "SHOT" and side in TEAMS:
            other = "visitor" if side == "home" else "home"
            if payload.get("made"):
                score[side] += _int(payload.get("points") or 2)
                hero = _person(names, side, payload.get("shooterId"))
                if hero:
                    add(event, payload, _shot_kind(payload), side, hero, _person(names, side, payload.get("assistId")))
            elif payload.get("blockPlayerId"):
                hero = _person(names, other, payload.get("blockPlayerId"))
                shooter = _person(names, side, payload.get("shooterId"))
                if hero:
                    add(event, payload, "block", other, hero, other=shooter)
        elif kind_of_event == "TURNOVER" and side in TEAMS and payload.get("stealPlayerId"):
            other = "visitor" if side == "home" else "home"
            hero = _person(names, other, payload.get("stealPlayerId"))
            robbed = _person(names, side, payload.get("turnoverPlayerId"))
            if hero:
                add(event, payload, "steal", other, hero, other=robbed)
    return found


def _headline(play: Mapping[str, Any]) -> str:
    line = {"three": "Three-pointer", "dunk": "Dunk", "layup": "Layup", "jumper": "Jump shot", "block": "Blocked shot", "steal": "Steal"}[play["kind"]]
    if play.get("and_one"):
        line += " and the foul"
    if play.get("helper"):
        line += f", assist from {play['helper']['last']}"
    return line


def _captions(play: Mapping[str, Any], team_name: str) -> list[dict[str, str]]:
    last, helper, kind = play["player"]["last"], play.get("helper"), play["kind"]
    if kind == "block":
        setup, action = f"{team_name} on defense", f"{last} goes up!"
    elif kind == "steal":
        setup, action = f"{team_name} on defense", f"{last} jumps the play!"
    else:
        setup = f"{helper['last']} finds {last}" if helper else f"{last} has the ball"
        action = {"three": f"{last} from deep!", "dunk": f"{last} takes off!", "layup": f"{last} to the rim!", "jumper": f"{last} rises up!"}[kind]
    word = "AND ONE!" if play.get("and_one") else WORDS[kind]
    return [{"phase": "setup", "text": setup}, {"phase": "action", "text": action}, {"phase": "finish", "text": word}]


def _floor_numbers(play: Mapping[str, Any], side: str, names: Names, skip: set[str], heads: Callable[[str, str], str] | None) -> list[dict[str, str]]:
    rows = []
    for pid in play["floor"].get(side) or []:
        if pid in skip:
            continue
        who = _person(names, side, pid)
        if who:
            rows.append({"number": who["number"], "head": heads(side, pid) if heads else ""})
    return rows


def script(play: Mapping[str, Any], *, teams: Mapping[str, str], names: Names, station_name: str = "", station_logo: str = "",
           logo_style: str = "round", sponsor_name: str = "", sponsor_logo: str = "", dance: str = "fistpump", theme: str = "paper",
           colors: Mapping[str, Mapping[str, str]] | None = None, grade: str = "",
           featured_head: Callable[[str, str], str] | None = None, team_head: Callable[[str, str], str] | None = None) -> dict[str, Any]:
    """Everything the court animation needs for one play."""
    side = play["team"]
    other = "visitor" if side == "home" else "home"
    colors = colors or {}
    hero, helper = play["player"], play.get("helper")
    grade_name = GRADE_NAMES.get(str(grade or "").strip(), str(grade or "").strip())
    tag = " · ".join(part for part in (f"#{hero['number']}" if hero["number"] else "", grade_name) if part)
    skip = {hero["id"], (helper or {}).get("id", "")}
    return {
        "sport": "basketball",
        "kind": play["kind"],
        "td": True,      # confetti and the big word, as on a football score
        "spot": play["spot"],
        "rim": {"x": RIM_X, "y": RIM_Y},
        "title": {
            "kicker": f"{teams['visitor']} at {teams['home']}".upper(),
            "name": hero["name"],
            "tag": tag,
            "line": _headline(play),
            "when": quarter_phrase(play["period"]).capitalize() if play.get("period") else "",
        },
        "hero": {"name": hero["name"], "number": hero["number"], "head": featured_head(side, hero["id"]) if featured_head else ""},
        "helper": {"name": helper["name"], "number": helper["number"], "head": featured_head(side, helper["id"]) if featured_head else ""} if helper else None,
        "other_number": play.get("other_number", ""),
        "teammates": _floor_numbers(play, side, names, skip, team_head),
        "opponents": _floor_numbers(play, other, names, {play.get("other_id", "")}, None),
        "offense": {"name": teams[side], "side": side, **(colors.get(side) or {})},
        "defense": {"name": teams[other], "side": other, **(colors.get(other) or {})},
        "word": "AND ONE!" if play.get("and_one") else WORDS[play["kind"]],
        "captions": _captions(play, teams[side]),
        "score_after": f"{teams['visitor']} {play['score']['visitor']}, {teams['home']} {play['score']['home']}",
        "station": station_name,
        "station_logo": station_logo,
        "logo_style": logo_style,
        "sponsor": sponsor_name,
        "sponsor_logo": sponsor_logo,
        "dance": dance if dance in DANCES else "fistpump",
        "theme": theme if theme in THEMES else "paper",
        "label": "Animated recreation from the official stats",
    }
