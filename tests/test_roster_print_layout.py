"""Roster printouts (2026-10-31): Press Coverage-style pages with pronunciation,
shared by the Rosters page print and the Broadcaster Print Sheet."""
from __future__ import annotations

import re
from functools import wraps
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from flask import Flask

import roster_print_layout as layout
from broadcaster_print_service import BroadcasterPrintService
from routes.roster_routes import RosterRoutesDependencies, create_roster_blueprint

ROOT = Path(__file__).resolve().parents[1]


def _player(number: str, last: str, first: str = "Pat", **extra: Any) -> dict:
    return {"number": number, "last_name": last, "first_name": first, "position": "WR",
            "grade": "11", "pronunciation": f"{last.upper()}-ee", **extra}


def test_helpers() -> None:
    assert [layout.grade_label(g) for g in ("9", "10", "11", "12", "8", "Sophomore", "")] == [
        "Fr.", "So.", "Jr.", "Sr.", "8th", "So.", ""]
    assert layout.record_text({"wins": 7, "losses": 2}) == "7–2"
    assert layout.record_text({"wins": 3, "losses": 5, "ties": 1}) == "3–5–1"
    assert layout.record_text({}) == ""
    assert layout.game_when("2026-10-30", "7:00 PM") == "Friday, Oct. 30 · 7 p.m."
    assert layout.game_when("2026-09-04", "6:30 pm") == "Friday, Sept. 4 · 6:30 p.m."


def test_a_row_has_number_last_first_position_class_and_pronunciation() -> None:
    html = layout.roster_pages([_player("22", "Stubbendorff", "Finn", position="K", grade="10",
                                        pronunciation="STUB-ben-dorf", preferred_name="")],
                               title="Lafayette at Caledonia", subtitle="Friday, Oct. 30 · 7 p.m.",
                               team="Caledonia", team_tag="Home · 3–5")
    assert '<div class="pc-num">22</div>' in html
    assert "<b>STUBBENDORFF</b> Finn" in html
    assert "K So.<i>STUB-ben-dorf</i>" in html
    assert "<h1>LAFAYETTE AT CALEDONIA</h1>" in html and "<span>Home · 3–5</span>" in html


def test_numbers_in_order_four_columns_and_72_per_page() -> None:
    players = layout.active_players({"players": [_player(str(n), f"P{n}") for n in range(80, 0, -1)]
                                     + [_player("99", "Gone", status="inactive")]})
    assert [p["number"] for p in players][:3] == ["1", "2", "3"] and len(players) == 80
    html = layout.roster_pages(players, title="T", subtitle="", team="Team", team_tag="Home")
    pages = html.split('<section class="pc-page">')[1:]
    assert len(pages) == 2 and "continued" in pages[1]
    assert pages[0].count('class="pc-row"') == 72 and pages[0].count('class="pc-col"') == 4
    # Column-major: the first column runs 1..18.
    first_column = pages[0].split('<div class="pc-col">')[1]
    assert re.findall(r'pc-num">(\d+)<', first_column)[-1] == "18"


def test_print_sheet_uses_the_layout_with_home_away_and_records() -> None:
    broadcast = {"broadcast_id": "FB-1", "home_team": "Caledonia", "visitor_team": "Lafayette",
                 "date": "2026-10-30", "scheduled_start": "7:00 PM",
                 "home_pregame_record": {"wins": 3, "losses": 5}, "visitor_pregame_record": {"wins": 7, "losses": 2}}
    service = BroadcasterPrintService(load_broadcasts=lambda: [broadcast], load_rosters=lambda: [],
                                      load_packages=lambda: [], get_school_logo_file=lambda *a: Path("none.png"))
    document = service._render_document(broadcast, {"players": [_player("1", "Lang", "Caleb")]}, None)
    assert "<h1>LAFAYETTE AT CALEDONIA</h1>" in document
    assert "<span>Home · 3–5</span>" in document and "<span>Away · 7–2</span>" in document
    assert "<b>LANG</b> Caleb" in document
    assert "No matching roster was found for this team." in document
    assert "roster-table" not in document and "CSRN GAME-DAY" not in document


def test_rosters_page_print_endpoint() -> None:
    def require_auth(func):
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any):
            return func(*args, **kwargs)
        return wrapper

    roster = {"id": "r1", "school_name": "Caledonia", "season": "2026", "level": "Varsity", "sport": "Football",
              "players": [_player("12", "Watrous", "Brody")]}
    service = SimpleNamespace(read=lambda rid: SimpleNamespace(code="OK", data={"roster": roster}) if rid == "r1"
                              else SimpleNamespace(code="ROSTER_NOT_FOUND", data={}))
    app = Flask(__name__)
    app.register_blueprint(create_roster_blueprint(RosterRoutesDependencies(require_auth=require_auth,
                                                                            get_roster_service=lambda: service)))
    client = app.test_client()
    response = client.get("/api/rosters/r1/print")
    assert response.status_code == 200 and response.mimetype == "text/html"
    page = response.get_data(as_text=True)
    assert "<h1>CALEDONIA ROSTER</h1>" in page and "<b>WATROUS</b> Brody" in page and "@page pcroster" in page
    assert client.get("/api/rosters/nope/print").status_code == 404
    html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    assert "fetch(`/api/rosters/${encodeURIComponent(currentRoster.id)}/print`" in html
