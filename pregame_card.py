"""Pregame story graphic (1080 x 1350) for Social Publishing, in the same themes
as the postgame graphic (postgame_card). Built from pregame_story.build_facts,
so it says only what the app has stored: results, averages and leaders cover the
games the station broadcast, and the card labels them that way.

Game Manager's pregame graphic is separate and does not use this module.
"""
from __future__ import annotations

from typing import Any, Mapping

import postgame_card as card
import postgame_story as story
import pregame_story

WIDTH = card.WIDTH
HEIGHT = card.HEIGHT
_e = card._e

_CSS = """
  .art { padding-top: 34px; padding-bottom: 34px; }
  .team { grid-template-columns: 150px minmax(0, 1fr); min-width: 0; }
  .team-name { overflow: hidden; white-space: nowrap; }
  .team-home { grid-template-columns: minmax(0, 1fr) 150px; }
  .team-logo { width: 150px; height: 150px; }
  .team-score { font-size: 96px; color: var(--win, var(--ink)); text-shadow: var(--win-glow, none); }
  .matchup-word { font-size: 44px; letter-spacing: .12em; }
  .kick { display: flex; flex-wrap: wrap; justify-content: center; align-items: center; gap: 8px 22px; padding: 12px 0 2px;
          font-size: 26px; font-weight: 700; letter-spacing: .14em; text-transform: uppercase; color: var(--accent, var(--ink)); }
  .kick span + span { border-left: 2px solid var(--rule); padding-left: 22px; }
  .tape { width: 100%; border-collapse: collapse; margin: 10px 0 4px; font-size: 31px; }
  .tape td { padding: 10px 8px; text-align: center; border-bottom: 1px solid var(--faint); width: 30%; font-family: var(--numbers);
             font-variant-numeric: lining-nums tabular-nums; font-weight: 700; }
  .tape th { padding: 10px 8px; border-bottom: 1px solid var(--faint); font-family: var(--label); font-size: 21px; letter-spacing: .14em;
             text-transform: uppercase; color: var(--soft); font-weight: 700; }
  .lower h3 { font-size: 24px; }
  .lower h4 { font-size: 21px; margin-top: 14px; }
  .lower li { font-size: 30px; line-height: 1.26; padding: 6px 0; }
  .lower li span { color: var(--soft); }
  .lower li em { font-style: normal; font-weight: 700; display: inline-block; min-width: 1.3em; }
  .lower section + section { margin-top: 12px; }
  .lower.single { grid-template-columns: 1fr; gap: 0; align-content: start; }
  .lower.single .group { margin-bottom: 6px; }
  .lower .note { margin: 8px 0 0; font-family: var(--label); font-size: 16px; letter-spacing: .06em; color: var(--soft); }
  .storylines li { padding: 6px 0; }
  .station small { font-size: 16px; letter-spacing: .14em; display: block; color: var(--soft); text-align: right; }
  .sparse .art { flex: 1 1 auto; }
  .sparse .team { grid-template-columns: 1fr; justify-items: center; text-align: center; row-gap: 14px; }
  .sparse .team-home .team-logo, .sparse .team-logo { grid-column: 1; grid-row: auto; width: 250px; height: 250px; }
  .sparse .team-home .team-name, .sparse .team-home .team-score { grid-column: 1; }
  .sparse .team-name { font-size: 38px; }
  .sparse .foot { margin-top: 14px; }
"""


def leader_line(pick: Mapping[str, Any]) -> str:
    """'1,240 pass yds, 12 TD' / '595 rush yds, 8 TD' / '22 rec, 410 yds, 3 TD'."""
    row = pick["row"]
    if pick["category"] == "passing":
        yards, tds = f"{row.get('passing_yards', 0):,} pass yds", row.get("passing_touchdowns", 0)
    elif pick["category"] == "rushing":
        yards, tds = f"{row.get('rushing_yards', 0):,} rush yds", row.get("rushing_touchdowns", 0)
    else:
        yards, tds = f"{row.get('receptions', 0)} rec, {row.get('receiving_yards', 0):,} yds", row.get("receiving_touchdowns", 0)
    return f"{yards}, {tds} TD" if tds else yards


def _result_line(result: Mapping[str, Any]) -> tuple[str, str]:
    ours, theirs = result["ours"], result["theirs"]
    mark = "W" if ours > theirs else "L" if ours < theirs else "T"
    return mark, f"{ours}-{theirs} {'vs.' if result['home'] else 'at'} {result['opponent']}"


def _averages(team: Mapping[str, Any]) -> tuple[str, str]:
    """Points scored and allowed per game, once there are at least two covered games."""
    results = team["results"]
    if len(results) < 2:
        return "", ""
    return (f"{sum(r['ours'] for r in results) / len(results):.1f}",
            f"{sum(r['theirs'] for r in results) / len(results):.1f}")


def _level(team: Mapping[str, Any]) -> str:
    parts = [team["classification"], f"Region {team['region']}" if team["region"] else ""]
    return " · ".join(part for part in parts if part)


def _tape_html(facts: Mapping[str, Any]) -> tuple[str, bool]:
    """The side-by-side comparison, and whether it used covered-game numbers."""
    v, h = facts["teams"]["visitor"], facts["teams"]["home"]
    v_for, v_against = _averages(v)
    h_for, h_against = _averages(h)
    rows = [("Region record", v["region_record"], h["region_record"]), ("Classification", _level(v), _level(h)),
            ("Points per game", v_for, h_for), ("Points allowed", v_against, h_against)]
    cells = "".join(f"<tr><td>{_e(left or '–')}</td><th>{_e(label)}</th><td>{_e(right or '–')}</td></tr>"
                    for label, left, right in rows if left or right)
    return (f'<table class="tape"><tbody>{cells}</tbody></table>' if cells else ""), bool(v_for or h_for)


def _players_html(facts: Mapping[str, Any]) -> str:
    groups = []
    for key in ("visitor", "home"):
        team = facts["teams"][key]
        if not team["leaders"]:
            continue
        items = "".join(f'<li><b>{_e(pick["player"]["name"])}</b> <span>{card._nobreak(leader_line(pick))}</span></li>'
                        for pick in team["leaders"])
        groups.append(f'<div class="group"><h4>{_e(team["name"])}</h4><ul>{items}</ul></div>')
    return f'<section class="players"><h3>Players to Watch</h3>{"".join(groups)}</section>' if groups else ""


def _results_html(facts: Mapping[str, Any]) -> str:
    groups = []
    for key in ("visitor", "home"):
        team = facts["teams"][key]
        if not team["results"]:
            continue
        items = "".join("<li><em>{}</em> <span>{}</span></li>".format(*map(_e, _result_line(r))) for r in team["results"][-4:])
        groups.append(f'<div class="group"><h4>{_e(team["name"])}</h4><ul>{items}</ul></div>')
    return f'<section class="results"><h3>Recent Results</h3>{"".join(groups)}</section>' if groups else ""


def _extras_html(facts: Mapping[str, Any]) -> str:
    """Their last meeting and the station's storylines, whichever exist."""
    parts = []
    h, v = facts["teams"]["home"], facts["teams"]["visitor"]
    if facts["meetings"]:
        last = facts["meetings"][-1]
        winner = h["name"] if last["ours"] > last["theirs"] else v["name"] if last["ours"] < last["theirs"] else ""
        score = f"{max(last['ours'], last['theirs'])}-{min(last['ours'], last['theirs'])}"
        when = pregame_story.short_date(last["date"])
        line = f"{winner} won {score}" if winner else f"Tied {score}"
        parts.append(f'<section class="meeting"><h3>Last Meeting</h3><ul><li>{_e(line)}{" <span>" + _e(when) + "</span>" if when else ""}</li></ul></section>')
    if facts["storylines"]:
        items = "".join(f"<li>{_e(line)}</li>" for line in facts["storylines"][:2])
        parts.append(f'<section class="storylines"><h3>Storylines</h3><ul>{items}</ul></section>')
    return "".join(parts)


def _kick_html(facts: Mapping[str, Any], level_game: bool) -> str:
    bits = [f"Kickoff {facts['kickoff']}" if facts["kickoff"] else ""]
    if level_game:
        bits.append(f"Region {facts['teams']['home']['region']} game")
    bits += [d.title() for d in facts["designations"]]
    spans = "".join(f"<span>{_e(bit)}</span>" for bit in bits if bit)
    return f'<div class="kick cond">{spans}</div>' if spans else ""


def render_card_html(
    facts: Mapping[str, Any],
    *,
    headline: str,
    station_name: str,
    station_logo_uri: str = "",
    logos: Mapping[str, str] | None = None,
    sponsor_name: str = "",
    sponsor_logo_uri: str = "",
    theme: str = card.DEFAULT_THEME,
    station_logo_style: str = card.DEFAULT_LOGO_STYLE,
    assets: Mapping[str, str] | None = None,
) -> str:
    theme = card.theme_id(theme)
    station_logo_style = card.logo_style(station_logo_style)
    assets = dict(assets or {})
    logos = logos or {}
    teams = facts["teams"]
    dateline = " · ".join(part for part in (story.ap_date(facts.get("date")), facts.get("venue") or "") if part)
    sport = (facts.get("sport") or "Football").strip().title() or "Football"
    visitor = card._team_block({"name": teams["visitor"]["name"], "score": teams["visitor"]["record"]}, logos.get("visitor", ""), winner=False, align="visitor")
    home = card._team_block({"name": teams["home"]["name"], "score": teams["home"]["record"]}, logos.get("home", ""), winner=False, align="home")
    sponsor = ""
    if sponsor_name or sponsor_logo_uri:
        mark = (f'<span class="sponsor-chip"><img src="{sponsor_logo_uri}" alt=""></span>' if sponsor_logo_uri
                else f"<strong>{_e(sponsor_name)}</strong>")
        sponsor = f'<div class="sponsor"><span>Brought to you by</span>{mark}</div>'
    station_mark = f'<span class="station-logo"><img src="{station_logo_uri}" alt=""></span>' if station_logo_uri else ""
    tape, averaged = _tape_html(facts)
    left = _players_html(facts) or _results_html(facts)
    right = (_results_html(facts) if _players_html(facts) else "") + _extras_html(facts)
    covered = bool(averaged or facts["teams"]["home"]["leaders"] or facts["teams"]["visitor"]["leaders"]
                   or facts["teams"]["home"]["results"] or facts["teams"]["visitor"]["results"])
    note = f'<p class="note">Averages, leaders and results are from games on {_e(station_name)}.</p>' if covered and station_name else ""
    sparse = not (left or right)
    if left and not right:
        right, left = left, ""
        lower = f'<div class="lower single">{right}{note}</div>'
    elif sparse:
        lower = ""
    else:
        lower = f'<div class="lower"><div>{left}{note}</div><div>{right}</div></div>'
    level_game = bool(facts.get("region_game") and teams["home"]["region"])
    css = card._BASE_CSS.replace("__W__", str(WIDTH)).replace("__H__", str(HEIGHT))
    theme_css = card._THEME_CSS[theme].replace("__ART__", assets.get("art", ""))
    return f"""<!doctype html>
<html><head><meta charset="utf-8">
<style>
{card._font_face(assets, theme)}{css}{theme_css}{_CSS}
</style></head>
<body class="theme-{theme} logo-{station_logo_style}{' sparse' if sparse else ''}">
  <div class="mast cond"><div class="mast-title">{_e(station_name)} Sports</div><div class="mast-tag">{_e(sport)} · Pregame</div></div>
  <div class="dateline cond">{_e(dateline)}</div>
  <h1 id="headline">{_e(headline)}</h1>
  <div class="art">
    {visitor}
    <div class="final matchup-word cond">AT</div>
    {home}
  </div>
  {_kick_html(facts, level_game)}
  {tape}
  {lower}
  <div class="foot cond">{sponsor}<div class="station">{station_mark}<span><small>Live on</small>{_e(station_name)}</span></div></div>
  <script>
  function fitCard() {{
    var head = document.getElementById('headline');
    var size = parseFloat(getComputedStyle(head).fontSize);
    while (head.scrollHeight > 160 && size > 36) {{ size -= 2; head.style.fontSize = size + 'px'; }}
    document.querySelectorAll('.team-name').forEach(function(el) {{
      var s = parseFloat(getComputedStyle(el).fontSize);
      while (el.scrollWidth > el.clientWidth && s > 16) {{ s -= 1; el.style.fontSize = s + 'px'; }}
    }});
    var lower = document.querySelector('.lower');
    if (lower) {{
      var items = document.querySelectorAll('.lower li'), s = 30;
      while (lower.scrollHeight > lower.clientHeight + 1 && s > 15) {{
        s -= 1;
        items.forEach(function(li) {{ li.style.fontSize = s + 'px'; }});
      }}
    }}
    window.__cardFitted = true;
  }}
  // Fit after the theme's display font has loaded, or the measurements are wrong.
  (document.fonts && document.fonts.ready ? document.fonts.ready : Promise.resolve()).then(fitCard);
  </script>
</body></html>"""
