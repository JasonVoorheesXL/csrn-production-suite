"""Broadcaster Print Sheet: the coaching/staff directory page went away with
Personnel (2026-10-31). The roster pages are covered in
test_roster_print_layout.py. Exercises the HTML assembly directly, without
generate()'s real Playwright PDF render.
"""
from __future__ import annotations

import inspect

from broadcaster_print_service import BroadcasterPrintService


def make_service() -> BroadcasterPrintService:
    return BroadcasterPrintService(
        load_broadcasts=lambda: [],
        load_rosters=lambda: [],
        load_packages=lambda: [],
        get_school_logo_file=lambda school_id, filename: None,
    )


def test_print_sheet_has_rosters_and_quick_reference_but_no_staff_page() -> None:
    broadcast = {
        "home_team": "Home Tigers",
        "visitor_team": "Visitor Wolves",
        "home_school_id": "home-1",
        "visitor_school_id": "visitor-2",
        "date": "2026-09-05",
        "scheduled_start": "7:00 PM",
        "venue": "Tiger Stadium",
        "sport": "Football",
        "level": "Varsity",
        "broadcast_id": "bc-1",
    }
    document = make_service()._render_document(broadcast, None, None)

    assert document.index('class="pc-page"') < document.index('class="quick-reference"')
    assert "staff-page" not in document
    assert "COACHING &amp; STAFF" not in document
    assert "load_personnel" not in inspect.signature(BroadcasterPrintService).parameters
