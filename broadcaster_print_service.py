from __future__ import annotations

import base64
import html
import mimetypes
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from playwright.sync_api import sync_playwright

from runtime_diagnostics_service import get_runtime_diagnostics


Record = dict[str, Any]
ObjectLoader = Callable[[], list[Record]]


@dataclass(frozen=True)
class BroadcasterPrintResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.code == "OK"


class BroadcasterPrintService:
    """Build game-specific broadcaster reference PDFs."""

    def __init__(
        self,
        *,
        load_broadcasts: ObjectLoader,
        load_rosters: ObjectLoader,
        load_packages: ObjectLoader,
        get_school_logo_file: Callable[[str, str], Path],
    ) -> None:
        self._load_broadcasts = load_broadcasts
        self._load_rosters = load_rosters
        self._load_packages = load_packages
        self._get_school_logo_file = get_school_logo_file

    def generate(self, broadcast_id: str) -> BroadcasterPrintResult:
        broadcast = self._find_broadcast(broadcast_id)
        if broadcast is None:
            return BroadcasterPrintResult("BROADCAST_NOT_FOUND")

        home_roster, visitor_roster = self._resolve_rosters(broadcast)

        document = self._render_document(
            broadcast,
            home_roster,
            visitor_roster,
        )

        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                try:
                    page = browser.new_page()
                    page.set_content(document, wait_until="load")
                    pdf_bytes = page.pdf(
                        format="Letter",
                        print_background=True,
                        prefer_css_page_size=True,
                    )
                finally:
                    browser.close()
        except Exception as exc:
            return BroadcasterPrintResult(
                "PDF_GENERATION_FAILED",
                {"message": str(exc)},
            )

        filename = self._filename(broadcast)

        return BroadcasterPrintResult(
            "OK",
            {
                "pdf": pdf_bytes,
                "filename": filename,
                "home_roster_found": home_roster is not None,
                "visitor_roster_found": visitor_roster is not None,
            },
        )

    def _find_broadcast(self, broadcast_id: str) -> Record | None:
        target = str(broadcast_id or "").strip()
        return next(
            (
                item
                for item in self._load_broadcasts()
                if str(item.get("broadcast_id", "")) == target
                and not item.get("archived")
            ),
            None,
        )

    def _resolve_rosters(
        self,
        broadcast: Mapping[str, Any],
    ) -> tuple[Record | None, Record | None]:
        rosters = list(self._load_rosters())
        package_ids: list[str] = []

        package = next(
            (
                item
                for item in self._load_packages()
                if str(item.get("broadcast_id", ""))
                == str(broadcast.get("broadcast_id", ""))
            ),
            None,
        )

        if package:
            package_ids = [
                str(value)
                for value in (package.get("roster_ids") or [])
                if str(value).strip()
            ]

        linked = [
            roster
            for roster in rosters
            if str(roster.get("id", "")) in package_ids
        ]

        home_school_id = str(broadcast.get("home_school_id", ""))
        visitor_school_id = str(broadcast.get("visitor_school_id", ""))

        home = next(
            (
                roster
                for roster in linked
                if str(roster.get("school_id", "")) == home_school_id
            ),
            None,
        )
        visitor = next(
            (
                roster
                for roster in linked
                if str(roster.get("school_id", "")) == visitor_school_id
            ),
            None,
        )

        if home is None:
            home = self._fallback_roster(
                rosters,
                broadcast,
                home_school_id,
                "home",
            )

        if visitor is None:
            visitor = self._fallback_roster(
                rosters,
                broadcast,
                visitor_school_id,
                "visitor",
            )

        return home, visitor

    # Match tiers tried in order: exact (sport, season, level, division),
    # then relax division (most likely to differ by formatting -- "Boys" vs
    # "boys", "AAA" vs "AAA "), then relax level too. sport and season are
    # never relaxed -- a roster for the wrong sport or the wrong season is
    # never an acceptable fallback.
    _MATCH_TIERS: tuple[tuple[str, ...], ...] = (
        ("sport", "season", "level", "division"),
        ("sport", "season", "level"),
        ("sport", "season"),
    )

    @staticmethod
    def _roster_match_field(roster: Mapping[str, Any], field: str) -> str:
        value = str(roster.get(field, "") or "")
        return value if field == "season" else value.casefold()

    @classmethod
    def _wanted_match_fields(cls, broadcast: Mapping[str, Any]) -> dict[str, str]:
        return {
            field: cls._roster_match_field(broadcast, field)
            for field in ("sport", "season", "level", "division")
        }

    @classmethod
    def _fallback_roster(
        cls,
        rosters: list[Record],
        broadcast: Mapping[str, Any],
        school_id: str,
        side: str,
    ) -> Record | None:
        if not school_id:
            return None

        wanted = cls._wanted_match_fields(broadcast)
        candidates = [
            roster
            for roster in rosters
            if str(roster.get("school_id", "")) == school_id
        ]

        log_fields = {
            "side": side,
            "school_id": school_id,
            "broadcast_id": str(broadcast.get("broadcast_id", "") or ""),
            "broadcast_sport": wanted["sport"],
            "broadcast_season": wanted["season"],
            "broadcast_level": wanted["level"],
            "broadcast_division": wanted["division"],
        }

        if not candidates:
            get_runtime_diagnostics().record(
                "BROADCASTER_PRINT_ROSTER_FALLBACK",
                result="NO_ROSTER_FOR_SCHOOL",
                **log_fields,
            )
            return None

        for tier_index, tier_fields in enumerate(cls._MATCH_TIERS):
            match = next(
                (
                    roster
                    for roster in candidates
                    if all(
                        cls._roster_match_field(roster, field) == wanted[field]
                        for field in tier_fields
                    )
                ),
                None,
            )
            if match is None:
                continue
            if tier_index > 0:
                relaxed = [
                    field
                    for field in ("level", "division")
                    if field not in tier_fields
                ]
                get_runtime_diagnostics().record(
                    "BROADCASTER_PRINT_ROSTER_FALLBACK",
                    result="RELAXED_MATCH",
                    matched_fields=list(tier_fields),
                    relaxed_fields=relaxed,
                    roster_id=str(match.get("id", "")),
                    roster_level=str(match.get("level", "") or ""),
                    roster_division=str(match.get("division", "") or ""),
                    **log_fields,
                )
            return match

        # No tier matched. Report the field-by-field diagnosis against the
        # closest candidate (one matching sport+season if any exist, else
        # just the first candidate for this school) instead of failing
        # silently.
        closest = next(
            (
                roster
                for roster in candidates
                if cls._roster_match_field(roster, "sport") == wanted["sport"]
                and cls._roster_match_field(roster, "season") == wanted["season"]
            ),
            candidates[0],
        )
        get_runtime_diagnostics().record(
            "BROADCASTER_PRINT_ROSTER_FALLBACK",
            result="NO_MATCH",
            candidate_count=len(candidates),
            closest_roster_id=str(closest.get("id", "")),
            sport_matched=cls._roster_match_field(closest, "sport") == wanted["sport"],
            season_matched=cls._roster_match_field(closest, "season") == wanted["season"],
            level_matched=cls._roster_match_field(closest, "level") == wanted["level"],
            division_matched=cls._roster_match_field(closest, "division") == wanted["division"],
            closest_roster_sport=cls._roster_match_field(closest, "sport"),
            closest_roster_season=cls._roster_match_field(closest, "season"),
            closest_roster_level=cls._roster_match_field(closest, "level"),
            closest_roster_division=cls._roster_match_field(closest, "division"),
            **log_fields,
        )
        return None

    def _render_document(
        self,
        broadcast: Mapping[str, Any],
        home_roster: Mapping[str, Any] | None,
        visitor_roster: Mapping[str, Any] | None,
    ) -> str:
        home_name = self._text(broadcast.get("home_team", "Home"))
        visitor_name = self._text(broadcast.get("visitor_team", "Visitor"))
        date = self._text(broadcast.get("date", "Date TBD"))
        start = self._text(broadcast.get("scheduled_start", "Time TBD"))
        venue = self._text(broadcast.get("venue", "Venue TBD"))
        sport = self._text(broadcast.get("sport", ""))
        level = self._text(broadcast.get("level", ""))
        broadcast_id = self._text(broadcast.get("broadcast_id", ""))

        home_logo = self._logo_data_uri(
            broadcast.get("home_identity"),
            broadcast.get("home_school_id"),
        )
        visitor_logo = self._logo_data_uri(
            broadcast.get("visitor_identity"),
            broadcast.get("visitor_school_id"),
        )

        tracking = broadcast.get("record_tracking", {})
        primary_side = (
            str(tracking.get("primary_side", "")).strip().lower()
            if isinstance(tracking, Mapping)
            else ""
        )
        broadcast_logo = (
            home_logo
            if primary_side == "home"
            else visitor_logo
            if primary_side == "visitor"
            else visitor_logo or home_logo
        )

        visitor_pages = self._roster_pages(
            visitor_roster,
            visitor_name,
            visitor_logo,
        )
        home_pages = self._roster_pages(
            home_roster,
            home_name,
            home_logo,
        )

        # The configured primary team's roster prints first (broadcaster
        # convenience). Round 13 Task C: key off the broadcast's recorded
        # primary side -- already resolved above from record_tracking -- rather
        # than a hard-coded "caledonia" team-name match. No primary recorded
        # (fresh install / legacy broadcast) -> the natural home-first order.
        if primary_side == "visitor":
            first_roster_pages = visitor_pages
            second_roster_pages = home_pages
        else:
            first_roster_pages = home_pages
            second_roster_pages = visitor_pages
        logo_html = (
            f'<img class="cover-logo" src="{broadcast_logo}" alt="">'
            if broadcast_logo
            else ""
        )

        return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Broadcaster Print Sheet</title>
<style>
@page quick {{
    size: Letter portrait;
    margin: .38in .42in .42in;
}}
@page roster {{
    size: Letter landscape;
    margin: .27in .32in .30in;
}}
* {{
    box-sizing: border-box;
}}
html, body {{
    margin: 0;
    color: #111;
    background: #fff;
    font-family: Arial, Helvetica, sans-serif;
}}
.quick-reference {{
    page: quick;
    min-height: 9.9in;
    break-before: page;
}}
.cover-header {{
    position: relative;
    min-height: 1.05in;
    border-bottom: 4px solid #b5121b;
    padding: 0 1.38in 10px 0;
    margin-bottom: 12px;
}}
.brand {{
    font-size: 9pt;
    font-weight: 800;
    letter-spacing: .12em;
    color: #b5121b;
}}
.cover-header h1 {{
    margin: 4px 0 3px;
    font-size: 20pt;
    line-height: 1.05;
}}
.cover-logo {{
    position: absolute;
    right: 0;
    top: 0;
    width: 1.08in;
    height: 1.08in;
    object-fit: contain;
}}
.matchup {{
    font-size: 14pt;
    font-weight: 800;
}}
.meta {{
    margin-top: 5px;
    color: #444;
    font-size: 9pt;
    line-height: 1.35;
}}
.quick-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 9px;
}}
.quick-card {{
    border: 1px solid #aaa;
    border-radius: 5px;
    padding: 8px 9px;
    break-inside: avoid;
    font-size: 9pt;
}}
.quick-card h3 {{
    margin: 0 0 5px;
    color: #b5121b;
    font-size: 10.5pt;
}}
.quick-card ol,
.quick-card ul {{
    margin: 3px 0 0 17px;
    padding: 0;
}}
.quick-card li {{
    margin: 0 0 4px;
}}
.warning {{
    margin-top: 9px;
    border: 2px solid #b5121b;
    padding: 8px;
    font-size: 8.7pt;
    font-weight: 700;
}}
.notes {{
    margin-top: 10px;
}}
.notes h2 {{
    margin: 0 0 4px;
    padding: 5px 7px;
    background: #111;
    color: #fff;
    font-size: 11pt;
}}
.note-line {{
    height: 24px;
    border-bottom: 1px solid #aaa;
}}
.footer {{
    margin-top: 7px;
    color: #777;
    font-size: 7.5pt;
    text-align: right;
}}

.roster-page {{
    page: roster;
    position: relative;
    break-before: page;
    overflow: hidden;
}}
.roster-page:first-of-type {{
    break-before: auto;
}}
.roster-watermark {{
    position: absolute;
    left: 50%;
    top: 53%;
    width: 4.8in;
    height: 4.8in;
    transform: translate(-50%, -50%);
    object-fit: contain;
    opacity: .055;
    z-index: 0;
}}
.roster-content {{
    position: relative;
    z-index: 1;
}}
.roster-heading {{
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 12px;
    border-bottom: 3px solid #111;
    padding-bottom: 5px;
    margin-bottom: 6px;
}}
.roster-heading h1 {{
    margin: 0;
    font-size: 18pt;
    line-height: 1;
}}
.continued {{
    font-size: 9pt;
    font-weight: 800;
    letter-spacing: .08em;
    color: #666;
}}
.roster-table {{
    width: 100%;
    border-collapse: collapse;
    table-layout: fixed;
    font-size: 9.5pt;
    line-height: 1.05;
}}
.roster-table th {{
    background: rgba(232,232,232,.96);
    border-top: 1px solid #888;
    border-bottom: 2px solid #666;
    padding: 3px 5px;
    text-align: left;
    font-size: 8.7pt;
}}
.roster-table td {{
    border-bottom: 1px solid rgba(190,190,190,.88);
    padding: 2.2px 5px;
    vertical-align: middle;
    height: 15px;
}}
.roster-table th.number,
.roster-table td.number {{
    width: 7%;
    text-align: center;
    font-weight: 800;
}}
.roster-table th.name,
.roster-table td.name {{
    width: 33%;
}}
.roster-table th.pronunciation,
.roster-table td.pronunciation {{
    width: 43%;
}}
.roster-table th.position,
.roster-table td.position {{
    width: 17%;
}}
.pronunciation-text {{
    font-weight: 700;
}}
.roster-columns {{
    display: flex;
    gap: .3in;
}}
.roster-columns .roster-table {{
    flex: 1 1 0;
    min-width: 0;
}}
.empty {{
    padding: 18px;
    border: 1px dashed #aaa;
    color: #666;
}}
</style>
</head>
<body>

{first_roster_pages}
{second_roster_pages}

<section class="quick-reference">
<div class="cover-header">
    <div class="brand">CSRN GAME-DAY QUICK REFERENCE</div>
    <h1>{visitor_name} at {home_name}</h1>
    <div class="matchup">{sport} &middot; {level}</div>
    <div class="meta">
        {date} | {start}<br>
        {venue}<br>
        Broadcast ID: {broadcast_id}
    </div>
    {logo_html}
</div>

<div class="quick-grid">

<div class="quick-card">
<h3>1. Load This Game</h3>
<ol>
<li>Open <strong>Game Manager</strong>.</li>
<li>Find <strong>{visitor_name} at {home_name}</strong>.</li>
<li>Select <strong>Open in Command Center</strong>.</li>
<li>Confirm matchup, venue, date and scheduled start.</li>
</ol>
</div>

<div class="quick-card">
<h3>2. Confirm Broadcast Data</h3>
<ul>
<li>Verify both team rosters are loaded.</li>
<li>Confirm broadcaster crew assignments.</li>
<li>Review pronunciations and pregame notes.</li>
<li>Verify the game remains in its pregame state.</li>
</ul>
</div>

<div class="quick-card">
<h3>3. Audio Check</h3>
<ul>
<li>Confirm each broadcaster microphone registers separately.</li>
<li>Verify normal speech reaches the expected OBS level.</li>
<li>Confirm noise suppression / gate filters are active.</li>
<li>Monitor the outgoing program feed before going live.</li>
</ul>
</div>

<div class="quick-card">
<h3>4. OBS Readiness</h3>
<ul>
<li>Run the Command Center OBS readiness check.</li>
<li>Confirm OBS is reachable and authenticated.</li>
<li>Confirm the required scene and browser source are available.</li>
<li>Correct failed readiness items before starting.</li>
</ul>
</div>

<div class="quick-card">
<h3>5. Stream Platform</h3>
<ul>
<li>Prepare the correct Facebook / YouTube live event.</li>
<li>Verify title, audience and destination.</li>
<li>Confirm OBS is using the intended stream configuration.</li>
<li>Use a test broadcast when appropriate.</li>
</ul>
</div>

<div class="quick-card">
<h3>6. Start Broadcast</h3>
<ol>
<li>Complete readiness checks.</li>
<li>Begin the streaming-platform session as required.</li>
<li>Select <strong>Start Broadcast</strong> in CSRN.</li>
<li>Confirm the game changes to <strong>LIVE</strong>.</li>
<li>Confirm program graphics appear correctly.</li>
</ol>
</div>

</div>

<div class="warning">
IMPORTANT: Start Broadcast changes the CSRN game to LIVE and enables the scorebug. Complete the readiness checks above before pressing Start Broadcast.
</div>

<div class="quick-card" style="margin-top:9px">
<h3>If the Broadcast Is Interrupted</h3>
Use <strong>Resume Broadcast</strong> only when recovering an already-started broadcast. Do not use Resume as the normal game-start workflow.
</div>

<div class="notes">
<h2>Broadcast Notes</h2>
<div class="note-line"></div>
<div class="note-line"></div>
<div class="note-line"></div>
<div class="note-line"></div>
</div>

<div class="footer">
Generated by CSRN Production Suite | {broadcast_id}
</div>
</section>
</body>
</html>"""

    # Rows that fit on one physical landscape page in a single-column
    # roster table (empirically verified against the current font-size/
    # row-height CSS). A team's roster is always condensed to exactly 2
    # physical pages -- if the two halves would each still exceed this
    # (a roster over ~76 active players), each half's page switches to a
    # 2-column layout instead of spilling onto extra physical pages.
    ROWS_PER_COLUMN = 38

    def _roster_pages(
        self,
        roster: Mapping[str, Any] | None,
        team_name: str,
        logo_data_uri: str,
    ) -> str:
        players = self._active_players(roster)

        if roster is None:
            chunks: list[list[Mapping[str, Any]]] = [[]]
            empty_message = "No matching roster was found for this team."
        elif not players:
            chunks = [[]]
            empty_message = "This roster currently contains no active players."
        else:
            empty_message = ""
            if len(players) <= self.ROWS_PER_COLUMN:
                chunks = [players]
            else:
                midpoint = (len(players) + 1) // 2
                chunks = [players[:midpoint], players[midpoint:]]

        pages: list[str] = []
        total = len(chunks)

        for index, chunk in enumerate(chunks, start=1):
            continued = (
                '<div class="continued">CONTINUED</div>'
                if index > 1
                else ""
            )
            watermark = (
                f'<img class="roster-watermark" src="{logo_data_uri}" alt="">'
                if logo_data_uri
                else ""
            )

            if not chunk:
                body = f'<div class="empty">{self._text(empty_message)}</div>'
            elif len(chunk) > self.ROWS_PER_COLUMN:
                # Chunk is still too tall for one column on this physical
                # page (a >76-player roster) -- lay it out as 2 side-by-
                # side columns on the same page rather than letting the
                # table overflow onto a 3rd/4th physical page.
                column_midpoint = (len(chunk) + 1) // 2
                body = (
                    '<div class="roster-columns">'
                    f"{self._roster_table(chunk[:column_midpoint])}"
                    f"{self._roster_table(chunk[column_midpoint:])}"
                    "</div>"
                )
            else:
                body = self._roster_table(chunk)

            pages.append(
                '<section class="roster-page">'
                f"{watermark}"
                '<div class="roster-content">'
                '<div class="roster-heading">'
                f"<h1>{team_name}</h1>"
                f"{continued}"
                "</div>"
                f"{body}"
                "</div>"
                "</section>"
            )

        return "".join(pages)

    def _active_players(
        self,
        roster: Mapping[str, Any] | None,
    ) -> list[Mapping[str, Any]]:
        if roster is None:
            return []

        players = roster.get("players", [])
        if not isinstance(players, list):
            return []

        active = [
            player
            for player in players
            if isinstance(player, Mapping)
            and str(player.get("status", "active")).casefold() != "inactive"
        ]
        active.sort(key=self._player_sort_key)
        return active

    def _roster_table(
        self,
        players: list[Mapping[str, Any]],
    ) -> str:
        rows: list[str] = []

        for player in players:
            number = self._text(player.get("number", ""))
            preferred = str(player.get("preferred_name", "") or "").strip()
            first = str(player.get("first_name", "") or "").strip()
            last = str(player.get("last_name", "") or "").strip()
            first_display = preferred or first
            name = self._text(
                " ".join(x for x in (first_display, last) if x)
            )
            pronunciation = self._text(player.get("pronunciation", ""))
            position = self._text(
                player.get("position")
                or player.get("secondary_position")
                or ""
            )

            rows.append(
                "<tr>"
                f'<td class="number">{number}</td>'
                f'<td class="name"><strong>{name}</strong></td>'
                f'<td class="pronunciation"><span class="pronunciation-text">{pronunciation}</span></td>'
                f'<td class="position">{position}</td>'
                "</tr>"
            )

        return (
            '<table class="roster-table">'
            "<thead><tr>"
            '<th class="number">#</th>'
            '<th class="name">Player</th>'
            '<th class="pronunciation">Pronunciation</th>'
            '<th class="position">Pos</th>'
            "</tr></thead>"
            "<tbody>"
            + "".join(rows)
            + "</tbody></table>"
        )

    def _logo_data_uri(
        self,
        identity: Any,
        fallback_school_id: Any,
    ) -> str:
        if not isinstance(identity, Mapping):
            identity = {}

        school_id = str(
            identity.get("school_id")
            or fallback_school_id
            or ""
        ).strip()
        logo_route = str(identity.get("logo", "") or "").strip()

        if not school_id or not logo_route:
            return ""

        filename = Path(logo_route).name
        if not filename:
            return ""

        try:
            path = self._get_school_logo_file(school_id, filename)
            if not path.exists() or not path.is_file():
                return ""

            mime = mimetypes.guess_type(path.name)[0] or "image/png"
            payload = base64.b64encode(path.read_bytes()).decode("ascii")
            return f"data:{mime};base64,{payload}"
        except (OSError, ValueError):
            return ""

    @staticmethod
    def _player_sort_key(player: Mapping[str, Any]) -> tuple[int, str]:
        raw = str(player.get("number", "") or "").strip()
        match = re.search(r"\d+", raw)
        numeric = int(match.group()) if match else 9999
        return numeric, raw.casefold()

    @staticmethod
    def _text(value: Any) -> str:
        return html.escape(str(value or "").strip())

    @staticmethod
    def _filename(broadcast: Mapping[str, Any]) -> str:
        visitor = str(broadcast.get("visitor_team", "Visitor"))
        home = str(broadcast.get("home_team", "Home"))
        date = str(broadcast.get("date", "") or "")
        base = f"{date}_{visitor}_at_{home}_Broadcaster_Print_Sheet"
        cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("_")
        return f"{cleaned or 'Broadcaster_Print_Sheet'}.pdf"





