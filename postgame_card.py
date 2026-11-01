"""Postgame story graphic (1080 x 1350), in the station's choice of look.

One layout, several themes that echo the app's broadcast looks: News (the
default: cream newsprint, black ink, grayscale logos), Collegiate Tech,
8-Bit Gameday, Friday Night Stadium, Heritage Press and Neon. Built from the
same facts as the written story (postgame_story.build_facts), so the card and
the post never disagree. The station logo can be shown round, on a glass
tile, or square; on the ink themes (News, Heritage) it follows the paper.
"""
from __future__ import annotations

import html
from typing import Any, Mapping

import postgame_story as story

WIDTH = 1080
HEIGHT = 1350

# id -> label and the static/ files the theme needs. The service turns each
# file into a data URI, since the card is rendered without a server.
THEMES: dict[str, dict[str, Any]] = {
    "news": {"label": "News", "assets": {}},
    "collegiate": {"label": "Collegiate Tech", "assets": {"font_display": "fonts/michroma-regular.woff2"}},
    "eightbit": {"label": "8-Bit Gameday", "assets": {"art": "8bit-gameday/environments/football-stadium.png"}},
    "stadium": {"label": "Friday Night Stadium", "assets": {
        "art": "friday-night-stadium/clash/football-field-background.png", "font_display": "fonts/bangers-regular.woff2"}},
    "heritage": {"label": "Heritage Press", "assets": {
        "art": "heritage/press-newsprint-texture.png", "font_display": "fonts/karantina-700.woff2"}},
    "neon": {"label": "Neon", "assets": {"font_display": "fonts/michroma-regular.woff2"}},
}
DEFAULT_THEME = "news"
LOGO_STYLES = {"round": "Round", "glass": "Glass", "square": "Square"}
DEFAULT_LOGO_STYLE = "round"
_DISPLAY_FONT = {"collegiate": "Michroma", "neon": "Michroma", "stadium": "Bangers", "heritage": "Karantina"}


def theme_id(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text if text in THEMES else DEFAULT_THEME


def logo_style(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text if text in LOGO_STYLES else DEFAULT_LOGO_STYLE


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
        f'<div class="team-score num">{_e(team["score"])}</div>'
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


def _potg_html(facts: Mapping[str, Any], picks: Any, station_name: str = "") -> str:
    """One strip per Player of the Game: 'Player of the Game' for a single
    pick, '<Team> Player of the Game' when each team has one."""
    picks = [picks] if isinstance(picks, Mapping) else list(picks or [])
    rows = []
    for potg in picks:
        line = story.standout_line(potg["row"]) if potg.get("row") else ""
        team = facts["teams"][potg["team"]]["name"]
        tag = f"{team} Player of the Game" if len(picks) > 1 else f"{station_name} Player of the Game".strip()
        line_html = f'<span class="potg-line">{_nobreak(line)}</span>' if line else ""
        team_html = "" if len(picks) > 1 else f'<span class="potg-team">{_e(team)}</span>'
        rows.append(f'<div class="potg"><span class="potg-tag">{_e(tag)}</span>'
                    f'<b>{_e(potg["player"]["name"])}</b>{team_html}{line_html}</div>')
    return "".join(rows)


def _standouts_html(facts: Mapping[str, Any]) -> str:
    order = [facts["winner"], facts["loser"]] if facts.get("winner") else ["visitor", "home"]
    groups = []
    for key in order:
        rows = facts["standouts"].get(key) or []
        if not rows:
            continue
        items = "".join(
            f'<li><b>{_e(row["player"]["name"])}</b> <span>{_nobreak(story.standout_line(row))}</span></li>'
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


_BASE_CSS = """
  * { box-sizing: border-box; }
  html, body { margin: 0; padding: 0; }
  body { width: __W__px; height: __H__px; overflow: hidden; color: var(--ink); background: var(--bg);
         font-family: var(--body); display: flex; flex-direction: column; padding: 46px 58px 40px; position: relative; }
  .cond { font-family: var(--label); font-stretch: condensed; }
  .num { font-family: var(--numbers); font-variant-numeric: lining-nums tabular-nums; }
  .mast { border-top: 7px solid var(--rule); border-bottom: 3px double var(--rule); padding: 10px 0 9px;
          display: flex; align-items: baseline; justify-content: space-between; gap: 20px; }
  .mast-title { font-size: 34px; font-weight: 700; letter-spacing: .26em; text-transform: uppercase; white-space: nowrap; }
  .mast-tag { font-size: 20px; font-weight: 700; letter-spacing: .22em; text-transform: uppercase; color: var(--soft); }
  .dateline { font-size: 19px; letter-spacing: .08em; text-transform: uppercase; color: var(--soft); padding: 9px 0 0; }
  h1 { font-family: var(--head); font-size: 68px; line-height: 1.02; font-weight: 700; letter-spacing: var(--head-tracking, -.01em);
       text-transform: var(--head-case, none); margin: 14px 0 12px; color: var(--head-ink, var(--ink)); text-shadow: var(--head-glow, none); }
  .deck { font-family: var(--deck); font-size: 25px; line-height: 1.32; margin: 0 0 18px; color: var(--deck-ink, var(--ink)); }
  .art { flex: 0 0 auto; border-top: 2px solid var(--rule); border-bottom: 2px solid var(--rule); background: var(--art-bg, none);
         border-radius: var(--art-radius, 0); box-shadow: var(--art-shadow, none);
         display: grid; grid-template-columns: 1fr 120px 1fr; align-items: center; padding: 26px var(--art-pad, 0); }
  .team { display: grid; grid-template-columns: 128px 1fr; grid-template-rows: auto auto; column-gap: 20px; align-items: center; }
  .team-home { grid-template-columns: 1fr 128px; text-align: right; }
  .team-home .team-logo { grid-column: 2; grid-row: 1 / span 2; }
  .team-home .team-name, .team-home .team-score { grid-column: 1; }
  .team-logo { grid-row: 1 / span 2; width: 128px; height: 128px; display: grid; place-items: center; }
  .team-logo img { max-width: 100%; max-height: 100%; object-fit: contain; filter: var(--logo-filter, none); }
  .logo-fallback { font-size: 80px; font-weight: 700; }
  .team-name { font-family: var(--head); font-size: 30px; font-weight: 700; line-height: 1.05; text-transform: uppercase; letter-spacing: .04em; }
  .team-score { font-size: 118px; font-weight: 700; line-height: .95; color: var(--soft); }
  .team.winner .team-score { color: var(--win, var(--ink)); text-shadow: var(--win-glow, none); }
  .final { text-align: center; font-size: 22px; font-weight: 700; letter-spacing: .3em; text-transform: uppercase; color: var(--accent, var(--ink)); }
  .line-score { width: 100%; border-collapse: collapse; margin: 16px 0 6px; font-size: 25px; }
  .line-score td, .line-score thead th:not(.ls-team) { font-family: var(--numbers); font-variant-numeric: lining-nums tabular-nums; }
  .line-score th, .line-score td { padding: 5px 8px; text-align: center; border-bottom: 1px solid var(--faint); }
  .line-score thead th { font-size: 18px; letter-spacing: .14em; color: var(--soft); border-bottom: 2px solid var(--rule); }
  .line-score .ls-team { text-align: left; width: 46%; font-family: var(--head); font-weight: 700; text-transform: uppercase; letter-spacing: .03em; font-size: 24px; }
  .line-score .ls-total { font-weight: 700; border-left: 2px solid var(--rule); }
  .line-score tr.winner td, .line-score tr.winner th { font-weight: 700; color: var(--win, var(--ink)); }
  .potg { display: flex; align-items: baseline; flex-wrap: wrap; gap: 6px 14px; margin: 10px 0 0; padding: 8px 16px;
          border: 2px solid var(--rule); background: var(--potg-bg, none); border-radius: var(--art-radius, 0); }
  .potg-tag { font-family: var(--label); font-size: 18px; font-weight: 700; letter-spacing: .2em; text-transform: uppercase; color: var(--accent, var(--soft)); }
  .potg b { font-family: var(--head); font-size: 28px; }
  .potg-team { font-family: var(--label); font-size: 20px; letter-spacing: .1em; text-transform: uppercase; color: var(--soft); }
  .potg-line { font-size: 22px; color: var(--soft); }
  .lower { flex: 1 1 auto; min-height: 0; display: grid; grid-template-columns: 1fr 1fr; gap: 34px; padding-top: 14px; overflow: hidden; }
  .lower h3 { margin: 0 0 8px; font-family: var(--head); font-size: 21px; letter-spacing: .24em; text-transform: uppercase;
              border-bottom: 2px solid var(--rule); padding-bottom: 5px; color: var(--accent, var(--ink)); }
  .lower h4 { margin: 10px 0 4px; font-family: var(--label); font-size: 18px; letter-spacing: .14em; text-transform: uppercase; color: var(--soft); }
  .lower ul { list-style: none; margin: 0; padding: 0; font-family: var(--list); }
  .standouts li { font-size: 26px; line-height: 1.24; padding: 4px 0; }
  .standouts li span { color: var(--soft); white-space: nowrap; }
  .key-plays li { display: grid; grid-template-columns: 48px 1fr; gap: 8px; font-size: 26px; line-height: 1.24; padding: 8px 0; border-bottom: 1px solid var(--faint); }
  .key-plays em { font-style: normal; font-weight: 700; color: var(--soft); }
  .foot { flex: 0 0 auto; border-top: 3px double var(--rule); margin-top: 14px; padding-top: 14px;
          display: flex; align-items: center; justify-content: space-between; gap: 24px; min-height: 96px; }
  .sponsor { display: flex; align-items: center; gap: 16px; font-size: 18px; letter-spacing: .14em; text-transform: uppercase; color: var(--soft); }
  .sponsor img { max-height: 80px; max-width: 300px; object-fit: contain; }
  .sponsor-chip { background: var(--chip-bg, none); border-radius: 10px; padding: var(--chip-pad, 0); display: flex; }
  .sponsor strong { font-size: 26px; color: var(--ink); letter-spacing: .04em; }
  .station { display: flex; align-items: center; gap: 14px; font-size: 22px; font-weight: 700; letter-spacing: .18em; text-transform: uppercase; margin-left: auto; }
  .station-logo { width: 78px; height: 78px; display: grid; place-items: center; overflow: hidden; }
  .station-logo img { width: 100%; height: 100%; object-fit: contain; filter: var(--station-filter, none); }
  .logo-round .station-logo { border-radius: 50%; }
  .logo-round .station-logo img { object-fit: cover; }
  .logo-glass .station-logo { border-radius: 16px; padding: 8px; background: linear-gradient(160deg, rgba(255,255,255,.55), rgba(255,255,255,.08));
                              border: 1px solid rgba(255,255,255,.6); box-shadow: 0 8px 18px rgba(0,0,0,.28), inset 0 1px 0 rgba(255,255,255,.7); }
  .logo-square .station-logo { border-radius: 0; }
"""

_THEME_CSS = {
    "news": """
  :root { --ink: #171512; --soft: #5f594f; --rule: #2a2622; --faint: #cfc6b4;
          --bg: radial-gradient(circle at 18% 12%, rgba(255,255,255,.55), transparent 42%), radial-gradient(circle at 85% 90%, rgba(160,140,100,.12), transparent 50%), #f3efe5;
          --body: Georgia, "Times New Roman", serif; --head: Georgia, "Times New Roman", serif; --deck: Cambria, Georgia, serif;
          --list: Cambria, Georgia, serif; --label: Bahnschrift, "Arial Narrow", "Segoe UI", sans-serif;
          --numbers: Bahnschrift, "Arial Narrow", sans-serif; --deck-ink: #2c2823;
          --logo-filter: grayscale(1) contrast(1.15); --station-filter: grayscale(1) contrast(1.1); }
""",
    "heritage": """
  :root { --ink: #3a2a19; --soft: #6e5a42; --rule: #4a3520; --faint: #c9b48e;
          --bg: linear-gradient(rgba(236,221,190,.82), rgba(226,206,168,.86)), url('__ART__') center/cover, #e8d7b4;
          --body: Georgia, "Times New Roman", serif; --head: "Karantina", Georgia, serif; --deck: Georgia, serif;
          --list: Georgia, serif; --label: "Karantina", Bahnschrift, sans-serif; --numbers: "Karantina", Bahnschrift, sans-serif;
          --head-tracking: .01em; --logo-filter: sepia(1) grayscale(.35) contrast(1.1); --station-filter: sepia(1) grayscale(.35) contrast(1.05); }
  h1 { font-size: 92px; line-height: .95; }
  .team-score { font-size: 140px; }
""",
    "collegiate": """
  :root { --ink: #f8fbff; --soft: #b9c7d8; --rule: #c9203b; --faint: rgba(191,201,212,.22); --accent: #ff4a63; --win: #ffffff;
          --bg: radial-gradient(circle at 80% 0%, rgba(201,32,59,.35), transparent 45%), linear-gradient(160deg, #07101a 0%, #122033 100%);
          --body: "Segoe UI", Arial, sans-serif; --head: "Michroma", "Segoe UI", sans-serif; --deck: "Segoe UI", Arial, sans-serif;
          --list: "Segoe UI", Arial, sans-serif; --label: Bahnschrift, "Segoe UI", sans-serif; --numbers: Bahnschrift, "Segoe UI", sans-serif;
          --head-case: uppercase; --head-tracking: .02em; --art-bg: rgba(255,255,255,.06); --art-radius: 16px; --art-pad: 22px;
          --art-shadow: 0 18px 38px rgba(0,0,0,.45), inset 0 1px 0 rgba(255,255,255,.12); --potg-bg: rgba(255,255,255,.06);
          --chip-bg: rgba(255,255,255,.9); --chip-pad: 8px 12px; }
  h1 { font-size: 52px; line-height: 1.12; }
""",
    "neon": """
  :root { --ink: #eafcff; --soft: #8fb3c9; --rule: #19e3ff; --faint: rgba(25,227,255,.25); --accent: #ff3df2; --win: #19e3ff;
          --bg: radial-gradient(circle at 15% 10%, rgba(255,61,242,.22), transparent 40%), radial-gradient(circle at 90% 85%, rgba(25,227,255,.2), transparent 45%), #02030a;
          --body: "Segoe UI", Arial, sans-serif; --head: "Michroma", "Segoe UI", sans-serif; --deck: "Segoe UI", Arial, sans-serif;
          --list: "Segoe UI", Arial, sans-serif; --label: Bahnschrift, "Segoe UI", sans-serif; --numbers: Bahnschrift, "Segoe UI", sans-serif;
          --head-case: uppercase; --head-glow: 0 0 18px rgba(25,227,255,.55); --win-glow: 0 0 24px rgba(25,227,255,.7);
          --art-bg: rgba(25,227,255,.05); --art-radius: 14px; --art-pad: 22px; --art-shadow: 0 0 0 1px rgba(255,61,242,.45), 0 0 30px rgba(255,61,242,.25);
          --potg-bg: rgba(255,61,242,.08); --chip-bg: rgba(255,255,255,.9); --chip-pad: 8px 12px; }
  h1 { font-size: 52px; line-height: 1.12; }
""",
    "eightbit": """
  :root { --ink: #f2f5f7; --soft: #9fb0bd; --rule: #16ff83; --faint: rgba(22,255,131,.25); --accent: #ffc928; --win: #ffc928;
          --bg: linear-gradient(rgba(4,8,12,.84), rgba(4,8,12,.92)), url('__ART__') center/cover, #05080c;
          --body: "Courier New", Consolas, monospace; --head: "Courier New", Consolas, monospace; --deck: "Courier New", Consolas, monospace;
          --list: "Courier New", Consolas, monospace; --label: "Courier New", Consolas, monospace; --numbers: "Courier New", Consolas, monospace;
          --head-case: uppercase; --head-tracking: 0; --head-glow: 4px 4px 0 #0b5d33; --win-glow: 4px 4px 0 #6b4f00;
          --art-bg: rgba(0,0,0,.55); --art-pad: 22px; --art-shadow: 0 0 0 4px #16ff83; --potg-bg: rgba(0,0,0,.55);
          --chip-bg: #f2f5f7; --chip-pad: 6px 10px; }
  body, img { image-rendering: pixelated; }
  h1 { font-size: 50px; line-height: 1.12; font-weight: 900; }
  .team-score { font-weight: 900; }
""",
    "stadium": """
  :root { --ink: #ffffff; --soft: #d3dbe4; --rule: #ffc928; --faint: rgba(255,255,255,.22); --accent: #ffc928; --win: #ffc928;
          --bg: linear-gradient(180deg, rgba(5,10,20,.55) 0%, rgba(5,10,20,.88) 38%, rgba(5,10,20,.95) 100%), url('__ART__') center top/cover, #0b1220;
          --body: "Segoe UI", Arial, sans-serif; --head: "Bangers", Impact, sans-serif; --deck: "Segoe UI", Arial, sans-serif;
          --list: "Segoe UI", Arial, sans-serif; --label: Bahnschrift, "Segoe UI", sans-serif; --numbers: Bahnschrift, Impact, sans-serif;
          --head-tracking: .03em; --head-glow: 0 4px 0 rgba(0,0,0,.6); --art-bg: rgba(0,0,0,.35); --art-radius: 14px; --art-pad: 22px;
          --potg-bg: rgba(0,0,0,.35); --chip-bg: rgba(255,255,255,.92); --chip-pad: 8px 12px; }
  h1 { font-size: 80px; line-height: 1; }
""",
}


def _font_face(assets: Mapping[str, str], theme: str) -> str:
    font, family = assets.get("font_display"), _DISPLAY_FONT.get(theme)
    if not font or not family:
        return ""
    return f"@font-face {{ font-family: '{family}'; src: url('{font}') format('woff2'); font-weight: 100 900; }}\n"


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
    theme: str = DEFAULT_THEME,
    station_logo_style: str = DEFAULT_LOGO_STYLE,
    assets: Mapping[str, str] | None = None,
    player_of_game: Any = None,
) -> str:
    theme = theme_id(theme)
    station_logo_style = logo_style(station_logo_style)
    assets = dict(assets or {})
    logos = logos or {}
    teams = facts["teams"]
    dateline = " · ".join(part for part in (story.ap_date(facts.get("date")), facts.get("venue") or "") if part)
    sport = (facts.get("sport") or "Football").strip() or "Football"
    visitor = _team_block(teams["visitor"], logos.get("visitor", ""), winner=facts.get("winner") == "visitor", align="visitor")
    home = _team_block(teams["home"], logos.get("home", ""), winner=facts.get("winner") == "home", align="home")
    sponsor = ""
    if sponsor_name or sponsor_logo_uri:
        mark = (f'<span class="sponsor-chip"><img src="{sponsor_logo_uri}" alt=""></span>' if sponsor_logo_uri
                else f"<strong>{_e(sponsor_name)}</strong>")
        sponsor = f'<div class="sponsor"><span>Brought to you by</span>{mark}</div>'
    station_mark = f'<span class="station-logo"><img src="{station_logo_uri}" alt=""></span>' if station_logo_uri else ""
    lower = _standouts_html(facts) + _key_plays_html(facts)
    css = _BASE_CSS.replace("__W__", str(WIDTH)).replace("__H__", str(HEIGHT))
    theme_css = _THEME_CSS[theme].replace("__ART__", assets.get("art", ""))
    return f"""<!doctype html>
<html><head><meta charset="utf-8">
<style>
{_font_face(assets, theme)}{css}{theme_css}
</style></head>
<body class="theme-{theme} logo-{station_logo_style}">
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
  {_potg_html(facts, player_of_game, station_name)}
  <div class="lower">{lower}</div>
  <div class="foot cond">{sponsor}<div class="station">{station_mark}<span>{_e(station_name)}</span></div></div>
  <script>
  function fitCard() {{
    function shrink(el, min, maxHeight) {{
      var size = parseFloat(getComputedStyle(el).fontSize);
      while (el.scrollHeight > maxHeight && size > min) {{ size -= 2; el.style.fontSize = size + 'px'; }}
    }}
    shrink(document.getElementById('headline'), 36, 160);
    var deck = document.getElementById('deck');
    if (deck) shrink(deck, 19, 140);
    document.querySelectorAll('.team-name').forEach(function(el) {{
      var size = parseFloat(getComputedStyle(el).fontSize);
      while (el.scrollWidth > el.clientWidth && size > 16) {{ size -= 1; el.style.fontSize = size + 'px'; }}
    }});
    var lower = document.querySelector('.lower');
    var items = document.querySelectorAll('.lower li');
    var size = 26;
    while (lower.scrollHeight > lower.clientHeight + 1 && size > 15) {{
      size -= 1;
      items.forEach(function(li) {{ li.style.fontSize = size + 'px'; }});
    }}
    window.__cardFitted = true;
  }}
  // Fit after the theme's display font has loaded, or the measurements are wrong.
  (document.fonts && document.fonts.ready ? document.fonts.ready : Promise.resolve()).then(fitCard);
  </script>
</body></html>"""
