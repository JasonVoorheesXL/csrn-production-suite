"""Pregame story (Social Publishing, 2026-11-01): a game preview built from what
the app already stores -- both teams' records, the region and the kickoff,
each team's results and leaders in games the station has covered, past
meetings between the two schools, and the storylines from Pre-Game Setup.

Pure module, like postgame_story: the caller hands in the game, the other
stored games, and a way to load a covered game's statistics.
"""
from __future__ import annotations

import datetime as _dt
import re
from typing import Any, Callable, Mapping

import postgame_story as post
from postgame_story import TEAMS, _int, count_word, plural, tidy_team_name

StatisticsForGame = Callable[[Mapping[str, Any]], Mapping[str, Any] | None]
_MONTHS_AP = ("Jan.", "Feb.", "March", "April", "May", "June", "July", "Aug.", "Sept.", "Oct.", "Nov.", "Dec.")


def record_text(record: Any) -> str:
    """{'wins': 7, 'losses': 2, 'ties': 0} -> '7-2'; nothing when unknown."""
    if isinstance(record, Mapping):
        wins, losses, ties = _int(record.get("wins")), _int(record.get("losses")), _int(record.get("ties"))
        if wins or losses or ties:
            return f"{wins}-{losses}" + (f"-{ties}" if ties else "")
        return ""
    text = str(record or "").strip()
    return text if re.fullmatch(r"\d+-\d+(-\d+)?", text) else ""


def kickoff_text(value: Any) -> str:
    """'7:00 PM' -> '7 p.m.', '6:30 pm' -> '6:30 p.m.'."""
    match = re.match(r"\s*(\d{1,2})(?::(\d{2}))?\s*([AaPp])\.?\s*[Mm]?\.?", str(value or ""))
    if not match:
        return ""
    hour, minutes, half = match.group(1), match.group(2), match.group(3).lower()
    return f"{int(hour)}{':' + minutes if minutes and minutes != '00' else ''} {half}.m."


def _date(value: Any) -> _dt.date | None:
    try:
        return _dt.date.fromisoformat(str(value or "")[:10])
    except ValueError:
        return None


def short_date(value: Any) -> str:
    day = _date(value)
    return f"{_MONTHS_AP[day.month - 1]} {day.day}" if day else ""


def _final(game: Mapping[str, Any]) -> tuple[int, int] | None:
    home, visitor = game.get("final_home_score"), game.get("final_visitor_score")
    if home is None or visitor is None:
        return None
    return _int(home), _int(visitor)


def _results_for(school_id: str, games: list[Mapping[str, Any]], before: _dt.date | None) -> list[dict[str, Any]]:
    """This school's finished games the station covered, oldest first."""
    rows = []
    for game in games:
        if game.get("archived") or str(game.get("status", "")).lower() != "completed":
            continue
        day = _date(game.get("date"))
        if before and (not day or day >= before):
            continue
        final = _final(game)
        if not final:
            continue
        for side in TEAMS:
            if str(game.get(f"{side}_school_id", "") or "") == school_id:
                other = "visitor" if side == "home" else "home"
                ours, theirs = (final[0], final[1]) if side == "home" else (final[1], final[0])
                rows.append({"date": game.get("date"), "home": side == "home", "ours": ours, "theirs": theirs,
                             "opponent": tidy_team_name(game.get(f"{other}_team") or ""),
                             "opponent_id": str(game.get(f"{other}_school_id", "") or ""), "game": game, "side": side})
    return sorted(rows, key=lambda r: str(r["date"] or ""))


def _streak(results: list[Mapping[str, Any]]) -> tuple[str, int]:
    if not results:
        return "", 0
    last = results[-1]
    kind = "W" if last["ours"] > last["theirs"] else "L" if last["ours"] < last["theirs"] else "T"
    count = 0
    for r in reversed(results):
        if ("W" if r["ours"] > r["theirs"] else "L" if r["ours"] < r["theirs"] else "T") != kind:
            break
        count += 1
    return kind, count


def _leaders(results: list[Mapping[str, Any]], statistics_for: StatisticsForGame | None, names: post.Names, team: str) -> list[dict[str, Any]]:
    """Season-to-date leaders over the covered games: top passer, rusher and receiver."""
    if not statistics_for:
        return []
    totals: dict[str, dict[str, Any]] = {}
    for r in results:
        try:
            stats = statistics_for(r["game"]) or {}
        except Exception:
            continue
        for p in stats.get("players") or []:
            if not isinstance(p, Mapping) or p.get("team") != r["side"]:
                continue
            number = str(p.get("number", "") or "").strip()
            if not number:
                continue
            row = totals.setdefault(number, {"number": number, "name": p.get("name", ""), "games": set()})
            row["games"].add(id(r["game"]))
            for key in ("rushing_yards", "rushing_attempts", "rushing_touchdowns", "passing_yards", "pass_attempts",
                        "completions", "passing_touchdowns", "receiving_yards", "receptions", "receiving_touchdowns", "touchdowns"):
                row[key] = row.get(key, 0) + _int(p.get(key))
    picks = []
    for category, yards_key, floor in (("passing", "passing_yards", 150), ("rushing", "rushing_yards", 150), ("receiving", "receiving_yards", 120)):
        candidates = [row for row in totals.values() if row.get(yards_key, 0) >= floor]
        if not candidates:
            continue
        best = max(candidates, key=lambda row: row.get(yards_key, 0))
        who = names.person(team, best["number"], best["name"])
        if who["name"] and not who.get("unknown") and not who["name"].startswith("No. "):
            picks.append({"category": category, "player": who, "row": best, "games": len(best["games"])})
    return picks


def build_facts(
    *,
    broadcast: Mapping[str, Any],
    games: list[Mapping[str, Any]],
    storylines: list[str] | None = None,
    statistics_for: StatisticsForGame | None = None,
    roster_for_team: post.RosterLookup | None = None,
) -> dict[str, Any]:
    names = post.Names(roster_for_team, [str(broadcast.get("home_team") or ""), str(broadcast.get("visitor_team") or "")])
    day = _date(broadcast.get("date"))
    teams = {}
    for team in TEAMS:
        identity = broadcast.get(f"{team}_identity") if isinstance(broadcast.get(f"{team}_identity"), Mapping) else {}
        school_id = str(broadcast.get(f"{team}_school_id", "") or "")
        results = _results_for(school_id, games, day) if school_id else []
        teams[team] = {
            "key": team,
            "school_id": school_id,
            "name": tidy_team_name(broadcast.get(f"{team}_team") or identity.get("broadcast_name") or team.title()),
            "mascot": str(identity.get("mascot") or "").strip(),
            "record": record_text(broadcast.get(f"{team}_pregame_record")),
            "region_record": record_text(broadcast.get(f"{team}_pregame_region_record")),
            "classification": str(broadcast.get(f"{team}_classification") or broadcast.get("classification") or "").strip(),
            "region": str(broadcast.get(f"{team}_region") or "").strip(),
            "results": results,
            "streak": _streak(results),
            "leaders": _leaders(results, statistics_for, names, team),
        }
    home_id, visitor_id = teams["home"]["school_id"], teams["visitor"]["school_id"]
    meetings = [r for r in teams["home"]["results"] if visitor_id and r["opponent_id"] == visitor_id]
    designations = [str(d).replace("_", " ") for d in broadcast.get("special_designations") or [] if str(d).strip()]
    return {
        "broadcast_id": str(broadcast.get("broadcast_id", "") or ""),
        "sport": str(broadcast.get("sport", "") or ""),
        "date": str(broadcast.get("date", "") or ""),
        "weekday": post.weekday(broadcast.get("date")),
        "kickoff": kickoff_text(broadcast.get("scheduled_start")),
        "venue": str(broadcast.get("venue", "") or "").strip(),
        "region_game": bool(broadcast.get("region_game")),
        "designations": designations,
        "teams": teams,
        "meetings": meetings,
        "storylines": [str(line).strip() for line in storylines or [] if str(line).strip()],
        "home_id": home_id,
    }


def _result_phrase(r: Mapping[str, Any]) -> str:
    """'a 41-16 loss at West Point' / 'a 27-8 win over Columbus'."""
    won = r["ours"] > r["theirs"]
    tie = r["ours"] == r["theirs"]
    score = f"{max(r['ours'], r['theirs'])}-{min(r['ours'], r['theirs'])}"
    if tie:
        return f"a {score} tie with {r['opponent']}"
    where = ("over" if r["home"] else "at") if won else ("to" if r["home"] else "at")
    return f"{'an' if score.startswith(('8', '11', '18')) else 'a'} {score} {'win' if won else 'loss'} {where} {r['opponent']}"


def _leader_clause(pick: Mapping[str, Any]) -> str:
    """'Tyler Long has run for 595 yards and eight touchdowns'."""
    row, who = pick["row"], pick["player"]["name"]
    if pick["category"] == "passing":
        tds = row.get("passing_touchdowns", 0)
        return f"{who} has thrown for {row['passing_yards']} yards" + (f" and {plural(tds, 'touchdown')}" if tds else "")
    if pick["category"] == "rushing":
        tds = row.get("rushing_touchdowns", 0)
        return f"{who} has run for {row['rushing_yards']} yards" + (f" and {plural(tds, 'touchdown')}" if tds else "")
    tds = row.get("receiving_touchdowns", 0)
    return (f"{who} has caught {plural(row['receptions'], 'pass', 'passes')} for {row['receiving_yards']} yards"
            + (f" and {plural(tds, 'touchdown')}" if tds else ""))


def headline(facts: Mapping[str, Any], variant: int = 0) -> str:
    h, v = facts["teams"]["home"], facts["teams"]["visitor"]
    seed = facts["broadcast_id"]
    if "homecoming" in [d.lower() for d in facts["designations"]]:
        options = [f"{h['name']} hosts {v['name']} on homecoming night", f"{v['name']} visits {h['name']} for homecoming"]
    elif facts["region_game"] and h["region"]:
        options = [f"{h['name']} hosts {v['name']} in Region {h['region']} matchup", f"{v['name']} at {h['name']}: Region {h['region']} on the line"]
    else:
        options = [f"{h['name']} hosts {v['name']} {facts['weekday']}".strip(), f"Preview: {v['name']} at {h['name']}"]
    return post._pick(options, variant, "pregame-headline", seed)


def write_story(facts: Mapping[str, Any], *, variant: int = 0, sponsor_name: str = "", station_name: str = "") -> dict[str, Any]:
    """The built-in pregame writer: who, when, where, records, recent form,
    past meetings, players to watch, storylines."""
    h, v = facts["teams"]["home"], facts["teams"]["visitor"]

    def label(team: Mapping[str, Any]) -> str:
        bits = [team["record"]]
        if team["region_record"]:
            bits.append(f"{team['region_record']} Region {team['region']}" if team["region"] else f"{team['region_record']} region")
        bits = [b for b in bits if b]
        return f"{team['name']} ({', '.join(bits)})" if bits else team["name"]

    paragraphs = []
    when = " ".join(part for part in (facts["kickoff"], facts["weekday"]) if part)
    where = f" at {facts['venue']}" if facts["venue"] else ""
    level = ""
    if facts["region_game"] and h["region"]:
        level = f" in a Class {h['classification']}, Region {h['region']} game" if h["classification"] else f" in a Region {h['region']} game"
    paragraphs.append(f"{label(h)} hosts {label(v)}{' at ' + when if when else ''}{where}{level}.".replace("  ", " "))

    special = [d for d in facts["designations"] if d.lower() != "homecoming"]
    if "homecoming" in [d.lower() for d in facts["designations"]]:
        paragraphs[-1] += f" It is homecoming at {h['name']}."
    if special:
        paragraphs[-1] += f" The game is also {', '.join(special)}."

    for team in (h, v):
        results = team["results"]
        if not results:
            continue
        sentence = f"{team['name']} is coming off {_result_phrase(results[-1])} on {short_date(results[-1]['date'])}."
        kind, count = team["streak"]
        if count >= 2 and kind in ("W", "L"):
            sentence += f" {team['name']} has {'won' if kind == 'W' else 'lost'} {count_word(count)} straight."
        wins = [r for r in results if r["ours"] > r["theirs"]]
        if len(results) >= 3:
            biggest = max(results, key=lambda r: r["ours"] - r["theirs"])
            if biggest in wins:
                sentence += f" Its biggest win so far was {biggest['ours']}-{biggest['theirs']} over {biggest['opponent']}."
        paragraphs.append(sentence)

    if facts["meetings"]:
        last = facts["meetings"][-1]
        winner = h["name"] if last["ours"] > last["theirs"] else v["name"] if last["ours"] < last["theirs"] else ""
        score = f"{max(last['ours'], last['theirs'])}-{min(last['ours'], last['theirs'])}"
        day = _date(last["date"])
        when_met = f"{_MONTHS_AP[day.month - 1]} {day.day}, {day.year}" if day else "earlier"
        paragraphs.append(f"The teams met {when_met}, when {winner + ' won ' + score if winner else 'they tied ' + score}.")

    for team in (h, v):
        clauses = [_leader_clause(pick) for pick in team["leaders"]]
        if clauses:
            games = len(team["results"])
            covered = f"In the {count_word(games)} {team['name']} {'game' if games == 1 else 'games'} {station_name + ' has' if station_name else 'we have'} covered this season, "
            body = clauses[0] if len(clauses) == 1 else ", ".join(clauses[:-1]) + f", and {clauses[-1]}"
            paragraphs.append(covered + body + ".")

    if facts["storylines"]:
        paragraphs.append(" ".join(line if line.endswith((".", "!", "?")) else line + "." for line in facts["storylines"]))

    closing = []
    if sponsor_name:
        closing.append(f"{station_name + ' coverage' if station_name else 'Coverage'} is brought to you by {sponsor_name.rstrip('.')}.")
    hashtags = [f"#{tag}Football" for tag in (re.sub(r"[^A-Za-z0-9]", "", t["name"]) for t in (h, v)) if tag]
    hashtags.append("#HighSchoolFootball")
    title = headline(facts, variant)
    story = "\n\n".join(paragraphs)
    post_text = "\n\n".join([title, story] + ([" ".join(closing)] if closing else []) + [" ".join(hashtags)])
    return {"headline": title, "paragraphs": paragraphs, "story": story, "closing": closing, "scoring": [],
            "hashtags": hashtags, "post_text": post_text, "word_count": len(story.split()), "writer": "built-in",
            "variant": variant}


def fact_sheet(facts: Mapping[str, Any]) -> str:
    """What the AI writer gets for a preview: the app's stored facts. Results
    and leaders cover only the games the station broadcast."""
    h, v = facts["teams"]["home"], facts["teams"]["visitor"]
    lines = [f"GAME: {v['name']} at {h['name']}",
             f"WHEN: {facts['weekday']} {short_date(facts['date'])}, kickoff {facts['kickoff'] or 'not set'}".strip(),
             f"VENUE: {facts['venue']}" if facts["venue"] else "",
             f"REGION GAME: {'yes' if facts['region_game'] else 'no'}"
             + (f" (Class {h['classification']}, Region {h['region']})" if facts["region_game"] and h["region"] else ""),
             f"SPECIAL: {', '.join(facts['designations'])}" if facts["designations"] else ""]
    for team in (h, v):
        bits = [f"overall {team['record']}" if team["record"] else "", f"region {team['region_record']}" if team["region_record"] else ""]
        lines.append(f"{team['name'].upper()} ({team['mascot'] or 'mascot unknown'}): record before this game as entered by the station: "
                     + (", ".join(b for b in bits if b) or "not entered"))
        if team["results"]:
            lines.append(f"  Games the station covered: " + "; ".join(
                f"{short_date(r['date'])} {'vs' if r['home'] else 'at'} {r['opponent']} "
                f"{'W' if r['ours'] > r['theirs'] else 'L' if r['ours'] < r['theirs'] else 'T'} {r['ours']}-{r['theirs']}"
                for r in team["results"]))
        else:
            lines.append("  The station has not covered this team this season; research its results.")
        for pick in team["leaders"]:
            lines.append(f"  Leader in covered games: {_leader_clause(pick)}")
    if facts["meetings"]:
        lines.append("PAST MEETINGS THE STATION COVERED: " + "; ".join(
            f"{r['date']}: {h['name']} {r['ours']}, {v['name']} {r['theirs']}" for r in facts["meetings"]))
    if facts["storylines"]:
        lines.append("STORYLINES FROM THE STATION: " + " | ".join(facts["storylines"]))
    return "\n".join(line for line in lines if line)
