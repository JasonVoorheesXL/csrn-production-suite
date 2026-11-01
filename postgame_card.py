"""Postgame story graphic: a light, newspaper sports-page card (1080 x 1350).

Deliberately unlike the dark stadium pregame and final-score cards: cream
newsprint, black ink, a serif headline, grayscale team logos. Built from the
same facts as the written story (postgame_story.build_facts), so the card
and the post never disagree. The space under the headline is where the
black-and-white action illustration goes in the next round; until then it
holds the final score.
"""
from __future__ import annotations

import html
from typing import Any, Mapping

import postgame_story as story

WIDTH = 1080
HEIGHT = 1350


def _e(value: Any) -> str:
    return html.escape(str(value if value is not None else ""))


def _nobreak(text: str) -> str:
    """Keep '35-yd' on one line."""
    return _e(text).replace("-yd", "&#8209;yd")


def _team_block(team: Mapping[str, Any], logo_uri: str, *, winner: bool, align: str) -> str:
    logo = (f'<img src="{logo_uri}" alt="">' if logo_uri
            else f'<span class="logo-fallback">{_e(team["name"][:1])}</span>')
    return (
        f'<div class="team team-{align}{" winner" if winner else ""}">'
        f'<div class="team-logo">{logo}</div>'
        f'<div class="team-name">{_e(team["name"])}</div>'
        f'<div class="team-score">{_e(team["score"])}</div>'
        f'</div>'
    )


def _line_score_html(facts: Mapping[str, Any]) -> str:
    line = facts.get("line_score")
    if not line:
        return ""
    head = "".join(f"<th>{_e(label)}</th>" for label in line["labels"])
    rows = ""
    for key in ("visitor", "home"):
        team = facts["teams"][key]
        cells = "".join(f"<td>{_e(points)}</td>" for points in line[key])
        winner = " class=\"winner\"" if facts.get("winner") == key else ""
        rows += f'<tr{winner}><th class="ls-team">{_e(team["name"])}</th>{cells}<td class="ls-total">{_e(team["score"])}</td></tr>'
    return (f'<table class="line-score"><thead><tr><th class="ls-team"></th>{head}<th class="ls-total">T</th></tr></thead>'
            f'<tbody>{rows}</tbody></table>')


def _standouts_html(facts: Mapping[str, Any]) -> str:
    order = [facts["winner"], facts["loser"]] if facts.get("winner") else ["visitor", "home"]
    groups = []
    for key in order:
        rows = facts["standouts"].get(key) or []
        if not rows:
            continue
        items = "".join(
            f'<li><b>{_e(row["player"]["name"])}</b> <span>{_e(story.standout_line(row))}</span></li>'
            for row in rows
        )
        groups.append(f'<div class="group"><h4>{_e(facts["teams"][key]["name"])}</h4><ul>{items}</ul></div>')
    if not groups:
        return ""
    return f'<section class="standouts"><h3>Standouts</h3>{"".join(groups)}</section>'


def _key_plays_html(facts: Mapping[str, Any]) -> str:
    plays = facts.get("big_plays") or []
    if not plays:
        return ""
    items = "".join(
        f'<li><em>{_e(story.quarter_tag(play["quarter"]))}</em>'
        f'<span><b>{_e(facts["teams"][play["team"]]["name"])}</b> {_nobreak(story.big_play_line(play))}</span></li>'
        for play in plays
    )
    return f'<section class="key-plays"><h3>Key Plays</h3><ul>{items}</ul></section>'


def render_card_html(
    facts: Mapping[str, Any],
    *,
    headline: str,
    deck: str = "",
    station_name: str,
    station_logo_uri: str = "",
    logos: Mapping[str, str] | None = None,
    sponsor_name: str = "",
    sponsor_logo_uri: str = "",
) -> str:
    logos = logos or {}
    teams = facts["teams"]
    dateline = " · ".join(part for part in (story.ap_date(facts.get("date")), facts.get("venue") or "") if part)
    sport = (facts.get("sport") or "Football").strip() or "Football"
    visitor = _team_block(teams["visitor"], logos.get("visitor", ""), winner=facts.get("winner") == "visitor", align="visitor")
    home = _team_block(teams["home"], logos.get("home", ""), winner=facts.get("winner") == "home", align="home")
    sponsor = ""
    if sponsor_name or sponsor_logo_uri:
        mark = f'<img src="{sponsor_logo_uri}" alt="">' if sponsor_logo_uri else f"<strong>{_e(sponsor_name)}</strong>"
        sponsor = f'<div class="sponsor"><span>Brought to you by</span>{mark}</div>'
    station_mark = f'<img src="{station_logo_uri}" alt="">' if station_logo_uri else ""
    lower = _standouts_html(facts) + _key_plays_html(facts)
    return f"""<!doctype html>
<html><head><meta charset="utf-8">
<style>
  :root {{ --paper: #f3efe5; --ink: #171512; --soft: #5f594f; --rule: #2a2622; --faint: #cfc6b4; }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin: 0; padding: 0; }}
  body {{
    width: {WIDTH}px; height: {HEIGHT}px; overflow: hidden; color: var(--ink);
    background:
      radial-gradient(circle at 18% 12%, rgba(255,255,255,.55), transparent 42%),
      radial-gradient(circle at 85% 90%, rgba(160,140,100,.12), transparent 50%),
      var(--paper);
    font-family: Georgia, "Times New Roman", serif;
    display: flex; flex-direction: column; padding: 46px 58px 40px;
  }}
  .cond {{ font-family: Bahnschrift, "Arial Narrow", "Segoe UI", sans-serif; font-stretch: condensed; }}
  .mast {{ border-top: 7px solid var(--rule); border-bottom: 3px double var(--rule); padding: 10px 0 9px;
           display: flex; align-items: baseline; justify-content: space-between; gap: 20px; }}
  .mast-title {{ font-size: 34px; font-weight: 700; letter-spacing: .26em; text-transform: uppercase; white-space: nowrap; }}
  .mast-tag {{ font-size: 20px; font-weight: 700; letter-spacing: .22em; text-transform: uppercase; color: var(--soft); }}
  .dateline {{ font-size: 19px; letter-spacing: .08em; text-transform: uppercase; color: var(--soft); padding: 9px 0 0; }}
  h1 {{ font-size: 68px; line-height: 1.02; font-weight: 700; letter-spacing: -.01em; margin: 14px 0 12px; }}
  .deck {{ font-family: Cambria, Georgia, serif; font-size: 25px; line-height: 1.32; margin: 0 0 18px; color: #2c2823; }}
  .num {{ font-family: Bahnschrift, "Arial Narrow", "Segoe UI", sans-serif; font-variant-numeric: lining-nums tabular-nums; }}
  .art {{ flex: 0 0 auto; border-top: 2px solid var(--rule); border-bottom: 2px solid var(--rule);
          display: grid; grid-template-columns: 1fr 120px 1fr; align-items: center; padding: 26px 0; }}
  .team {{ display: grid; grid-template-columns: 128px 1fr; grid-template-rows: auto auto; column-gap: 20px; align-items: center; }}
  .team-home {{ grid-template-columns: 1fr 128px; text-align: right; }}
  .team-home .team-logo {{ grid-column: 2; grid-row: 1 / span 2; }}
  .team-home .team-name, .team-home .team-score {{ grid-column: 1; }}
  .team-logo {{ grid-row: 1 / span 2; width: 128px; height: 128px; display: grid; place-items: center; }}
  .team-logo img {{ max-width: 100%; max-height: 100%; object-fit: contain; filter: grayscale(1) contrast(1.15); }}
  .logo-fallback {{ font-size: 80px; font-weight: 700; }}
  .team-name {{ font-size: 30px; font-weight: 700; line-height: 1.05; text-transform: uppercase; letter-spacing: .04em; }}
  .team-score {{ font-family: Bahnschrift, "Arial Narrow", sans-serif; font-size: 118px; font-weight: 700; line-height: .95; color: var(--soft); font-variant-numeric: tabular-nums; }}
  .team.winner .team-score {{ color: var(--ink); }}
  .final {{ text-align: center; font-size: 22px; font-weight: 700; letter-spacing: .3em; text-transform: uppercase; }}
  .line-score {{ width: 100%; border-collapse: collapse; margin: 16px 0 6px; font-size: 25px; }}
  .line-score td, .line-score thead th:not(.ls-team) {{ font-family: Bahnschrift, "Arial Narrow", sans-serif; font-variant-numeric: lining-nums tabular-nums; }}
  .line-score th, .line-score td {{ padding: 5px 8px; text-align: center; border-bottom: 1px solid var(--faint); }}
  .line-score thead th {{ font-size: 18px; letter-spacing: .14em; color: var(--soft); border-bottom: 2px solid var(--rule); }}
  .line-score .ls-team {{ text-align: left; width: 46%; font-weight: 700; text-transform: uppercase; letter-spacing: .03em; }}
  .line-score .ls-total {{ font-weight: 700; border-left: 2px solid var(--rule); }}
  .line-score tr.winner td, .line-score tr.winner th {{ font-weight: 700; }}
  .lower {{ flex: 1 1 auto; min-height: 0; display: grid; grid-template-columns: 1fr 1fr; gap: 34px; padding-top: 14px; overflow: hidden; }}
  .lower h3 {{ margin: 0 0 8px; font-size: 21px; letter-spacing: .24em; text-transform: uppercase; border-bottom: 2px solid var(--rule); padding-bottom: 5px; }}
  .lower h4 {{ margin: 10px 0 4px; font-size: 18px; letter-spacing: .14em; text-transform: uppercase; color: var(--soft); }}
  .lower ul {{ list-style: none; margin: 0; padding: 0; font-family: Cambria, Georgia, serif; }}
  .standouts li {{ font-size: 26px; line-height: 1.24; padding: 4px 0; }}
  .standouts li span {{ color: var(--soft); white-space: nowrap; }}
  .key-plays li {{ display: grid; grid-template-columns: 48px 1fr; gap: 8px; font-size: 26px; line-height: 1.24; padding: 8px 0; border-bottom: 1px solid var(--faint); }}
  .key-plays em {{ font-style: normal; font-weight: 700; color: var(--soft); }}
  .foot {{ flex: 0 0 auto; border-top: 3px double var(--rule); margin-top: 14px; padding-top: 14px;
           display: flex; align-items: center; justify-content: space-between; gap: 24px; min-height: 96px; }}
  .sponsor {{ display: flex; align-items: center; gap: 16px; font-size: 18px; letter-spacing: .14em; text-transform: uppercase; color: var(--soft); }}
  .sponsor img {{ max-height: 80px; max-width: 300px; object-fit: contain; }}
  .sponsor strong {{ font-size: 26px; color: var(--ink); letter-spacing: .04em; }}
  .station {{ display: flex; align-items: center; gap: 14px; font-size: 22px; font-weight: 700; letter-spacing: .18em; text-transform: uppercase; margin-left: auto; }}
  .station img {{ max-height: 70px; max-width: 120px; object-fit: contain; }}
</style></head>
<body>
  <div class="mast cond"><div class="mast-title">{_e(station_name)} Sports</div><div class="mast-tag">{_e(sport)} · Postgame</div></div>
  <div class="dateline cond">{_e(dateline)}</div>
  <h1 id="headline">{_e(headline)}</h1>
  {f'<p class="deck" id="deck">{_e(deck)}</p>' if deck else ''}
  <div class="art">
    {visitor}
    <div class="final cond">Final</div>
    {home}
  </div>
  {_line_score_html(facts)}
  <div class="lower">{lower}</div>
  <div class="foot cond">{sponsor}<div class="station">{station_mark}<span>{_e(station_name)}</span></div></div>
  <script>
  (function() {{
    function shrink(el, min, maxHeight) {{
      var size = parseFloat(getComputedStyle(el).fontSize);
      while (el.scrollHeight > maxHeight && size > min) {{ size -= 2; el.style.fontSize = size + 'px'; }}
    }}
    shrink(document.getElementById('headline'), 44, 150);
    var deck = document.getElementById('deck');
    if (deck) shrink(deck, 19, 140);
    document.querySelectorAll('.team-name').forEach(function(el) {{
      var size = parseFloat(getComputedStyle(el).fontSize);
      while (el.scrollWidth > el.clientWidth && size > 18) {{ size -= 1; el.style.fontSize = size + 'px'; }}
    }});
    var lower = document.querySelector('.lower');
    var items = document.querySelectorAll('.lower li');
    var size = 26;
    while (lower.scrollHeight > lower.clientHeight + 1 && size > 16) {{
      size -= 1;
      items.forEach(function(li) {{ li.style.fontSize = size + 'px'; }});
    }}
  }})();
  </script>
</body></html>"""
