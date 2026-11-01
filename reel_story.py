"""Play reels (Social Publishing, 2026-11-01): which plays of a game are worth a
reel, and the "script" a paper-cutout animation follows for one of them.

Built only from what the statistician recorded -- where the play started and
ended, which way the team was going, the play type and who had the ball. The
data has no routes, blockers or defender positions, so the animation is a
stylized recreation and says so on screen.

Every position in a script is in "field yards" for the team with the ball on
the play's key run (the ball carrier, receiver after the catch, interceptor or
returner): 0 is that team's own goal line, 100 the goal it is attacking, so
the hero always runs left to right.
"""
from __future__ import annotations

from typing import Any, Mapping

import postgame_story as post
from postgame_story import TEAMS, _int, quarter_phrase, quarter_tag, yards_to_goal

REEL_KINDS = ("run", "pass", "interception", "kickoff_return", "punt_return", "field_goal")
DANCES = {"shimmy": "Shimmy", "robot": "Robot", "disco": "Disco Point", "moonwalk": "Moonwalk",
          "fistpump": "Fist Pump", "kneeknock": "Knee Knocker", "twirl": "Paper Twirl"}
THEMES = {"paper": "Paper Cutout", "neon": "Neon", "chalk": "Chalkboard", "comic": "Comic Book"}
GRADE_NAMES = {"9": "Freshman", "10": "Sophomore", "11": "Junior", "12": "Senior"}


def _heading(row: Mapping[str, Any] | None, team: str, events: Mapping[str, Any]) -> Any:
    if not row:
        return None
    event = events.get(str(row.get("event_id", "") or "")) or {}
    return (event.get("before") or {}).get(f"{team}_direction")


def _field(spot: Any, team: str, row: Mapping[str, Any] | None, events: Mapping[str, Any]) -> float | None:
    """A recorded spot as field yards for `team` (0 own goal, 100 their goal)."""
    ytg = yards_to_goal(spot, _heading(row, team, events))
    return None if ytg is None else 100.0 - ytg


def _clamp(value: float) -> float:
    return max(0.0, min(100.0, value))


def _geometry(kind: str, team: str, yards: int, row: Mapping[str, Any] | None, events: Mapping[str, Any], td: bool) -> dict[str, Any]:
    """Start, catch and end of the play in the hero's field yards. Missing spots
    fall back to what the yardage implies, ending in the end zone on a score."""
    other = "visitor" if team == "home" else "home"
    yards = max(0, yards)
    if kind in ("run", "pass"):
        start = _field((row or {}).get("ball_spot"), team, row, events)
        # The yardage is what the story says, so it wins when a spot disagrees.
        if td:
            start = 100.0 - yards
        elif start is None or start + yards > 99:
            start = (50.0 - yards / 2) if start is None else 99.0 - yards
        end = 100.0 if td else _clamp(start + yards)
        geometry = {"los": start, "start": start, "end": end}
        if kind == "pass":
            air = yards * (0.65 if yards >= 15 else 0.85)
            geometry["catch"] = _clamp(start + air)
        return geometry
    if kind == "interception":
        offense_los = _field((row or {}).get("ball_spot"), other, row, events)
        catch = _field((row or {}).get("turnover_spot"), team, row, events)
        if catch is None:
            catch = 100.0 - offense_los if offense_los is not None else 40.0
        end = 100.0 if td else _clamp(catch + yards)
        los = 100.0 - offense_los if offense_los is not None else _clamp(catch - 12)
        return {"los": los, "start": catch, "catch": catch, "end": end}
    if kind in ("kickoff_return", "punt_return"):
        catch = _field((row or {}).get("landing_spot"), team, row, events)
        kick_from = _field((row or {}).get("ball_spot"), other, row, events)
        if catch is None:
            catch = 5.0 if kind == "kickoff_return" else 20.0
        end = 100.0 if td else _clamp(catch + yards)
        kick_spot = 100.0 - kick_from if kick_from is not None else _clamp(catch + 55)
        return {"los": kick_spot, "start": catch, "catch": catch, "end": end}
    # Field goal: the hold is 7 yards behind the line, the kick is the line + 17.
    los = _field((row or {}).get("ball_spot"), team, row, events)
    if los is None:
        los = 100.0 - max(yards - 17, 3) if yards else 80.0
    return {"los": los, "start": los - 7, "end": 110.0}


def plays(facts: Mapping[str, Any]) -> list[dict[str, Any]]:
    """The reel-worthy plays, in game order: every touchdown and field goal,
    long runs and catches, interceptions and long returns."""
    found = []
    for index, item in enumerate(facts.get("timeline") or []):
        kind, td, yards = item["type"], False, _int(item.get("yards"))
        player, passer, score = item.get("player"), item.get("passer"), None
        if kind == "score":
            score = item["score"]
            how = score.get("how", "")
            if score["kind"] == "field_goal":
                kind, player, yards = "field_goal", score.get("player"), _int(score.get("yards"))
            elif score["kind"] == "touchdown" and how in ("run", "pass", "interception_return", "kickoff_return", "punt_return"):
                kind = {"interception_return": "interception"}.get(how, how)
                td, player, passer, yards = True, score.get("player"), score.get("passer"), _int(score.get("yards"))
            else:
                continue
        if kind not in REEL_KINDS or not (player or {}).get("name") or (player or {}).get("unknown"):
            continue
        found.append({"id": f"p{index}", "index": index, "kind": kind, "team": item["team"], "td": td,
                      "yards": yards, "quarter": item["quarter"], "player": player, "passer": passer, "score": score,
                      "row": item.get("row"), "label": _label(facts, item["team"], kind, td, yards, player, passer, item["quarter"])})
    return found


def _label(facts, team, kind, td, yards, player, passer, quarter) -> str:
    who = player["name"]
    what = {
        "run": f"{yards}-yd {'TD ' if td else ''}run",
        "pass": f"{yards}-yd {'TD ' if td else ''}catch" + (f" from {passer['last']}" if passer and passer.get('last') else ""),
        "interception": "interception" + (f", {yards}-yd TD return" if td else ""),
        "kickoff_return": f"{yards}-yd kickoff {'TD ' if td else ''}return",
        "punt_return": f"{yards}-yd punt {'TD ' if td else ''}return",
        "field_goal": f"{yards}-yd field goal" if yards else "field goal",
    }[kind]
    return f"{quarter_tag(quarter)} · {facts['teams'][team]['name']} · {who} {what}"


def _headline_line(kind: str, td: bool, yards: int) -> str:
    if kind == "field_goal":
        return f"{yards}-yard field goal" if yards else "Field goal"
    noun = {"run": "run", "pass": "catch", "interception": "interception return",
            "kickoff_return": "kickoff return", "punt_return": "punt return"}[kind]
    if kind == "interception" and not td:
        return "Interception"
    return f"{yards}-yard {'touchdown ' if td else ''}{noun}"


def _captions(kind: str, td: bool, yards: int, hero: str, passer: str, team: str, other: str) -> list[dict[str, Any]]:
    """What the caption scrap says during each phase (phase names match the animation)."""
    last = hero.split(" ")[-1]
    first = {
        "run": f"{last} takes the handoff",
        "pass": f"{passer.split(' ')[-1] if passer else team} drops back to pass",
        "interception": f"{other} throws it…",
        "kickoff_return": f"{other} kicks it deep to {last}",
        "punt_return": f"{other} punts it to {last}",
        "field_goal": f"{last} lines up the kick",
    }[kind]
    middle = {
        "run": f"{last} breaks free!",
        "pass": f"Caught by {last}!",
        "interception": f"Picked off by {last}!",
        "kickoff_return": f"{last} finds a crease!",
        "punt_return": f"{last} finds a crease!",
        "field_goal": "It's up…",
    }[kind]
    if kind == "field_goal":
        finish = "It's GOOD!"
    elif td:
        finish = "TOUCHDOWN!"
    else:
        finish = f"{yards} yards!" if yards else "What a play!"
    return [{"phase": "setup", "text": first}, {"phase": "action", "text": middle}, {"phase": "finish", "text": finish}]


def script(facts: Mapping[str, Any], play: Mapping[str, Any], *, broadcast: Mapping[str, Any],
           station_name: str = "", station_logo: str = "", logo_style: str = "round",
           sponsor_name: str = "", sponsor_logo: str = "", dance: str = "shimmy", theme: str = "paper",
           colors: Mapping[str, Mapping[str, str]] | None = None) -> dict[str, Any]:
    """Everything the paper-cutout animation needs for one play."""
    teams = facts["teams"]
    team, other = play["team"], ("visitor" if play["team"] == "home" else "home")
    events = facts.get("events") or {}
    geometry = _geometry(play["kind"], team, play["yards"], play.get("row"), events, play["td"])
    hero = play["player"]
    names = facts.get("names")
    roster = names.roster_player(team, hero.get("number")) if names and hero.get("number") else None
    grade = GRADE_NAMES.get(str((roster or {}).get("grade", "") or "").strip(), "")
    tag = " · ".join(part for part in (f"#{hero['number']}" if hero.get("number") else "", grade) if part)
    matchup = f"{teams['visitor']['name']} at {teams['home']['name']}"
    score = play.get("score")
    after = ""
    if score and facts.get("scores_reliable"):
        after = f"{teams['visitor']['name']} {score['visitor_score']}, {teams['home']['name']} {score['home_score']}"
    colors = colors or {}
    passer = (play.get("passer") or {}).get("name", "")
    return {
        "kind": play["kind"],
        "td": play["td"],
        "yards": play["yards"],
        "geometry": geometry,
        "kicker": play["kind"] == "field_goal",
        "title": {
            "kicker": matchup.upper(),
            "name": hero["name"],
            "tag": tag,
            "line": _headline_line(play["kind"], play["td"], play["yards"]),
            "when": quarter_phrase(play["quarter"]).capitalize() if play.get("quarter") else "",
        },
        "hero": {"name": hero["name"], "number": str(hero.get("number", "") or "")},
        "passer": {"name": passer, "number": str((play.get("passer") or {}).get("number", "") or "")},
        "offense": {"name": teams[team]["name"], "side": team, **(colors.get(team) or {})},
        "defense": {"name": teams[other]["name"], "side": other, **(colors.get(other) or {})},
        "captions": _captions(play["kind"], play["td"], play["yards"], hero["name"], passer,
                              teams[team]["name"], teams[other]["name"]),
        "score_after": after,
        "station": station_name,
        "station_logo": station_logo,
        "logo_style": logo_style,
        "sponsor": sponsor_name,
        "sponsor_logo": sponsor_logo,
        "dance": dance if dance in DANCES else "shimmy",
        "theme": theme if theme in THEMES else "paper",
        "label": "Animated recreation from the official stats",
    }
