"""Coverage for the coaching/staff directory page added to the Broadcaster
Print Sheet (2026-09) -- the deferred "page 6" the owner asked to finally
build. Exercises the pure HTML-assembly logic (_staff_page and friends)
directly, without invoking generate()'s real Playwright PDF render.
"""
from __future__ import annotations

from broadcaster_print_service import BroadcasterPrintService


def make_service(personnel: list[dict] | None = None, *, wire_personnel: bool = True) -> BroadcasterPrintService:
    return BroadcasterPrintService(
        load_broadcasts=lambda: [],
        load_rosters=lambda: [],
        load_packages=lambda: [],
        get_school_logo_file=lambda school_id, filename: None,
        load_personnel=(lambda: personnel or []) if wire_personnel else None,
    )


def test_staff_page_lists_each_teams_personnel_under_their_own_column() -> None:
    personnel = [
        {"id": "1", "full_name": "Jane Smith", "title": "Head Coach", "category": "Coach", "school_id": "home-1", "status": "active"},
        {"id": "2", "full_name": "Tom Reed", "title": "Offensive Coordinator", "category": "Coach", "school_id": "home-1", "status": "active"},
        {"id": "3", "full_name": "Pat Alvarez", "title": "Head Coach", "category": "Coach", "school_id": "visitor-2", "status": "active"},
    ]
    service = make_service(personnel)
    html = service._staff_page("Home Tigers", "Visitor Wolves", "home-1", "visitor-2")

    assert "Jane Smith" in html
    assert "Tom Reed" in html
    assert "Pat Alvarez" in html
    assert "Head Coach" in html
    assert "Offensive Coordinator" in html
    assert 'class="staff-page"' in html


def test_staff_page_excludes_inactive_and_other_schools_personnel() -> None:
    personnel = [
        {"id": "1", "full_name": "Retired Coach", "title": "Head Coach", "category": "Coach", "school_id": "home-1", "status": "inactive"},
        {"id": "2", "full_name": "Rival Coach", "title": "Head Coach", "category": "Coach", "school_id": "some-other-school", "status": "active"},
    ]
    service = make_service(personnel)
    html = service._staff_page("Home Tigers", "Visitor Wolves", "home-1", "visitor-2")

    assert "Retired Coach" not in html
    assert "Rival Coach" not in html
    assert "No staff on file for this team." in html


def test_staff_page_sorts_coaches_before_other_categories() -> None:
    personnel = [
        {"id": "1", "full_name": "Zed Producer", "title": "Producer", "category": "Production Staff", "school_id": "home-1", "status": "active"},
        {"id": "2", "full_name": "Ann Coach", "title": "Head Coach", "category": "Coach", "school_id": "home-1", "status": "active"},
    ]
    service = make_service(personnel)
    html = service._staff_page("Home Tigers", "Visitor Wolves", "home-1", "")

    assert html.index("Ann Coach") < html.index("Zed Producer")


def test_staff_page_includes_pronunciation_when_present() -> None:
    personnel = [
        {"id": "1", "full_name": "Siobhan O'Malley", "title": "Head Coach", "category": "Coach", "pronunciation": "shi-VAWN", "school_id": "home-1", "status": "active"},
    ]
    service = make_service(personnel)
    html = service._staff_page("Home Tigers", "Visitor Wolves", "home-1", "")

    assert "Pronounced: shi-VAWN" in html


def test_staff_page_omitted_entirely_when_no_personnel_loader_wired() -> None:
    service = make_service(wire_personnel=False)
    html = service._staff_page("Home Tigers", "Visitor Wolves", "home-1", "visitor-2")
    assert html == ""


def test_render_document_appends_staff_page_after_quick_reference() -> None:
    personnel = [
        {"id": "1", "full_name": "Jane Smith", "title": "Head Coach", "category": "Coach", "school_id": "home-1", "status": "active"},
    ]
    service = make_service(personnel)
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
    document = service._render_document(broadcast, None, None)

    quick_index = document.index('class="quick-reference"')
    staff_index = document.index('class="staff-page"')
    assert quick_index < staff_index
    assert "Jane Smith" in document
    assert document.index("</html>") > staff_index
