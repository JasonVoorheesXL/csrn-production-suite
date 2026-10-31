"""Roster printout pages (2026-10-31), shared by the Rosters page print and the
Broadcaster Print Sheet.

Modelled on Press Coverage MS's game rosters: landscape Letter, one team per
page, a matchup header, a black team bar, and four columns of players read top
to bottom: a big condensed jersey number, LAST name in caps with the first
name, and a small line with position and class. Ours adds each player's
pronunciation to that line, since that is what the person on the microphone
needs.
"""
from __future__ import annotations

import html
import math
from datetime import date as _date
from typing import Any, Iterable, Mapping

ROWS_PER_COLUMN = 18
COLUMNS = 4
PLAYERS_PER_PAGE = ROWS_PER_COLUMN * COLUMNS

_GRADE_LABELS = {
    "7": "7th", "8": "8th", "9": "Fr.", "10": "So.", "11": "Jr.", "12": "Sr.",
    "fr": "Fr.", "freshman": "Fr.", "so": "So.", "soph": "So.", "sophomore": "So.",
    "jr": "Jr.", "junior": "Jr.", "sr": "Sr.", "senior": "Sr.",
}


_AP_MONTHS = {1: "Jan.", 2: "Feb.", 3: "March", 4: "April", 5: "May", 6: "June", 7: "July",
              8: "Aug.", 9: "Sept.", 10: "Oct.", 11: "Nov.", 12: "Dec."}


def _text(value: Any) -> str:
    return html.escape(str(value or "").strip())


def grade_label(grade: Any) -> str:
    """9/10/11/12 or the words, as a roster prints them: Fr. So. Jr. Sr."""
    raw = str(grade or "").strip()
    return _GRADE_LABELS.get(raw.lower().rstrip("."), raw)


def _number_key(player: Mapping[str, Any]) -> tuple[int, str]:
    number = str(player.get("number", "") or "").strip()
    return (int(number) if number.isdigit() else 999, number)


def active_players(roster: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    """Active players in jersey-number order."""
    players = roster.get("players", []) if isinstance(roster, Mapping) else []
    if not isinstance(players, list):
        return []
    active = [
        player for player in players
        if isinstance(player, Mapping) and str(player.get("status", "active")).casefold() != "inactive"
    ]
    return sorted(active, key=_number_key)


def record_text(record: Any) -> str:
    """"7–2" (or "7–2–1"), or "" before any game is played."""
    if not isinstance(record, Mapping):
        return ""
    wins, losses, ties = (int(record.get(key, 0) or 0) for key in ("wins", "losses", "ties"))
    if not (wins or losses or ties):
        return ""
    return f"{wins}–{losses}" + (f"–{ties}" if ties else "")


def game_when(date_value: Any, start_value: Any) -> str:
    """"Friday, Oct. 30 · 7 p.m." from 2026-10-30 and 7:00 PM; raw text otherwise."""
    parts: list[str] = []
    raw_date = str(date_value or "").strip()
    try:
        day = _date.fromisoformat(raw_date)
        parts.append(f"{day.strftime('%A')}, {_AP_MONTHS[day.month]} {day.day}")
    except ValueError:
        if raw_date:
            parts.append(raw_date)
    raw_start = str(start_value or "").strip()
    if raw_start:
        clock = raw_start.upper().replace(" ", "")
        for suffix, label in (("PM", "p.m."), ("AM", "a.m.")):
            if clock.endswith(suffix):
                clock = clock[: -len(suffix)]
                if clock.endswith(":00"):
                    clock = clock[:-3]
                raw_start = f"{clock} {label}"
                break
        parts.append(raw_start)
    return " · ".join(parts)


def _row(player: Mapping[str, Any]) -> str:
    first = str(player.get("first_name", "") or "").strip()
    preferred = str(player.get("preferred_name", "") or "").strip()
    if preferred and preferred.casefold() != first.casefold():
        first = f'{first} "{preferred}"' if first else preferred
    last = str(player.get("last_name", "") or "").strip()
    positions = [str(player.get(key, "") or "").strip() for key in ("position", "secondary_position")]
    meta = " ".join(x for x in ("/".join(p for p in positions if p), grade_label(player.get("grade"))) if x)
    pronunciation = str(player.get("pronunciation", "") or "").strip()
    say = f'<i>{_text(pronunciation)}</i>' if pronunciation else ""
    return (
        '<div class="pc-row">'
        f'<div class="pc-num">{_text(player.get("number"))}</div>'
        '<div class="pc-who">'
        f'<div class="pc-name"><b>{_text(last.upper())}</b> {_text(first)}</div>'
        f'<div class="pc-meta">{_text(meta)}{say}</div>'
        "</div></div>"
    )


def roster_pages(
    players: Iterable[Mapping[str, Any]],
    *,
    title: str,
    subtitle: str,
    team: str,
    team_tag: str,
    brand: str = "",
    empty_message: str = "No active players on this roster.",
) -> str:
    """One <section> per printed page for one team."""
    players = list(players)
    chunks = [players[i:i + PLAYERS_PER_PAGE] for i in range(0, len(players), PLAYERS_PER_PAGE)] or [[]]
    pages: list[str] = []
    for index, chunk in enumerate(chunks):
        # Read top to bottom, then the next column. Each column stands alone, so
        # one long name that wraps only lengthens its own column.
        per_column = max(1, math.ceil(len(chunk) / COLUMNS))
        columns = [chunk[i:i + per_column] for i in range(0, len(chunk), per_column)]
        body = (
            '<div class="pc-cols">'
            + "".join('<div class="pc-col">' + "".join(_row(p) for p in column) + "</div>" for column in columns)
            + "</div>"
            if chunk else f'<div class="pc-empty">{_text(empty_message)}</div>'
        )
        tag = _text(team_tag) + (" · continued" if index else "")
        pages.append(
            '<section class="pc-page">'
            '<header class="pc-head">'
            f'<h1>{_text(title.upper())}</h1><span class="pc-when">{_text(subtitle)}</span>'
            f'<span class="pc-brand">{_text(brand.upper())}</span>'
            "</header>"
            f'<div class="pc-bar"><h2>{_text(team.upper())}</h2><span>{tag}</span></div>'
            f"{body}"
            '<footer class="pc-foot"><span>Pronunciation in <i>italics</i>, from the roster. '
            "Check new names with the team before saying them on air.</span>"
            f"<span>{len(players)} active players</span></footer>"
            "</section>"
        )
    return "".join(pages)


# Bahnschrift's condensed bold ships with Windows 10 and 11 (what the app runs
# on), so nothing has to be embedded; Arial Narrow is the fallback.
_CONDENSED = '700 {size}/{height} Bahnschrift, "Arial Narrow", sans-serif; font-stretch: condensed'

ROSTER_CSS = """
@page pcroster { size: Letter landscape; margin: .34in .4in .3in; }
.pc-page { page: pcroster; break-before: page; display: flex; flex-direction: column;
  height: 7.84in; color: #111; font-family: Arial, Helvetica, sans-serif; }
.pc-head { display: flex; align-items: baseline; gap: 14px; border-bottom: 3px solid #111; padding-bottom: 3px; }
.pc-head h1 { margin: 0; font: H1; }
.pc-when { font-weight: 700; font-size: 12pt; }
.pc-brand { margin-left: auto; font-weight: 800; font-size: 9pt; letter-spacing: .22em; }
.pc-bar { display: flex; align-items: center; justify-content: space-between; margin-top: 5px;
  background: #111; color: #fff; padding: 2px 10px; }
.pc-bar h2 { margin: 0; font: BAR; letter-spacing: .01em; }
.pc-bar span { font-weight: 800; font-size: 10pt; }
.pc-cols { display: grid; grid-template-columns: repeat(4, 1fr); column-gap: .2in; align-items: start; margin-top: 3px; }
.pc-col { display: flex; flex-direction: column; min-width: 0; }
.pc-row { display: grid; grid-template-columns: .44in 1fr; align-items: center; column-gap: 5px;
  border-bottom: 1px solid #bdbdbd; padding: 2px 0 1px; break-inside: avoid; }
.pc-num { text-align: right; font: NUM; }
.pc-name { font: NAME; }
.pc-name b { font-size: 13.5pt; text-transform: uppercase; }
.pc-meta { font-size: 7pt; font-weight: 800; line-height: 1.15; margin-top: 1px; }
.pc-meta i { font-weight: 600; color: #8a1220; margin-left: 5px; }
.pc-empty { margin-top: 18px; font-size: 12pt; font-weight: 700; }
.pc-foot { margin-top: auto; display: flex; justify-content: space-between; border-top: 1px solid #111;
  padding-top: 3px; font-size: 7.5pt; color: #333; }
""".replace("H1", _CONDENSED.format(size="28pt", height="1")).replace(
    "BAR", _CONDENSED.format(size="21pt", height="1.1")).replace(
    "NUM", _CONDENSED.format(size="21pt", height="1")).replace(
    "NAME", _CONDENSED.replace("700", "600").format(size="12.5pt", height="1.05"))



def roster_document(sections: str, *, title: str) -> str:
    """A complete printable page (the Rosters page print)."""
    return (
        '<!doctype html><html><head><meta charset="utf-8">'
        f"<title>{_text(title)}</title>"
        f"<style>{ROSTER_CSS}html,body{{margin:0;background:#fff}}</style>"
        f"</head><body>{sections}</body></html>"
    )
