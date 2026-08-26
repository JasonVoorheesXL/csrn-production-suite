from __future__ import annotations

from pathlib import Path

from broadcaster_print_service import BroadcasterPrintService
from runtime_diagnostics_service import get_runtime_diagnostics


def make_service(
    *,
    broadcasts: list[dict] | None = None,
    rosters: list[dict] | None = None,
    packages: list[dict] | None = None,
) -> BroadcasterPrintService:
    return BroadcasterPrintService(
        load_broadcasts=lambda: list(broadcasts or []),
        load_rosters=lambda: list(rosters or []),
        load_packages=lambda: list(packages or []),
        get_school_logo_file=lambda school_id, filename: Path(school_id) / filename,
    )


def broadcast(**overrides) -> dict:
    base = {
        "broadcast_id": "BC-1",
        "sport": "Football",
        "season": "2026",
        "level": "Varsity",
        "division": "Boys",
        "home_school_id": "home-school",
        "visitor_school_id": "visitor-school",
        "home_team": "Home Tigers",
        "visitor_team": "Visitor Bears",
    }
    base.update(overrides)
    return base


def roster(**overrides) -> dict:
    base = {
        "id": "roster-1",
        "school_id": "home-school",
        "sport": "Football",
        "season": "2026",
        "level": "Varsity",
        "division": "Boys",
        "players": [],
    }
    base.update(overrides)
    return base


def last_fallback_log() -> dict:
    events = get_runtime_diagnostics().snapshot(limit=50)["events"]
    return next(
        event
        for event in reversed(events)
        if event.get("event_type") == "BROADCASTER_PRINT_ROSTER_FALLBACK"
    )


def test_exact_four_field_match_still_works() -> None:
    game = broadcast()
    rosters = [roster(id="home-roster", school_id="home-school")]
    home = BroadcasterPrintService._fallback_roster(rosters, game, "home-school", "home")
    assert home is not None
    assert home["id"] == "home-roster"


def test_division_formatting_mismatch_is_relaxed() -> None:
    game = broadcast(division="boys ")
    rosters = [roster(id="home-roster", division="Boys")]
    home = BroadcasterPrintService._fallback_roster(rosters, game, "home-school", "home")
    assert home is not None
    assert home["id"] == "home-roster"

    log = last_fallback_log()
    assert log["result"] == "RELAXED_MATCH"
    assert log["relaxed_fields"] == ["division"]
    assert log["matched_fields"] == ["sport", "season", "level"]


def test_level_mismatch_is_relaxed_after_division() -> None:
    # Mirrors the real production case (FB-2026-4A-W00-002, Houston vs
    # Caledonia): a Junior Varsity broadcast, but only a Varsity roster
    # exists on file for the school.
    game = broadcast(level="Junior Varsity")
    rosters = [roster(id="home-roster", level="Varsity")]
    home = BroadcasterPrintService._fallback_roster(rosters, game, "home-school", "home")
    assert home is not None
    assert home["id"] == "home-roster"

    log = last_fallback_log()
    assert log["result"] == "RELAXED_MATCH"
    assert set(log["relaxed_fields"]) == {"level", "division"}
    assert log["matched_fields"] == ["sport", "season"]


def test_sport_mismatch_is_never_relaxed() -> None:
    game = broadcast(sport="Basketball")
    rosters = [roster(id="home-roster", sport="Football")]
    home = BroadcasterPrintService._fallback_roster(rosters, game, "home-school", "home")
    assert home is None

    log = last_fallback_log()
    assert log["result"] == "NO_MATCH"
    assert log["sport_matched"] is False


def test_season_mismatch_is_never_relaxed() -> None:
    game = broadcast(season="2025")
    rosters = [roster(id="home-roster", season="2026")]
    home = BroadcasterPrintService._fallback_roster(rosters, game, "home-school", "home")
    assert home is None

    log = last_fallback_log()
    assert log["result"] == "NO_MATCH"
    assert log["season_matched"] is False


def test_no_roster_for_school_is_reported_distinctly() -> None:
    game = broadcast()
    home = BroadcasterPrintService._fallback_roster([], game, "home-school", "home")
    assert home is None

    log = last_fallback_log()
    assert log["result"] == "NO_ROSTER_FOR_SCHOOL"


def test_empty_school_id_returns_none_without_logging() -> None:
    game = broadcast()
    rosters = [roster()]
    before = len(get_runtime_diagnostics().snapshot(limit=200)["events"])
    home = BroadcasterPrintService._fallback_roster(rosters, game, "", "home")
    after = len(get_runtime_diagnostics().snapshot(limit=200)["events"])
    assert home is None
    assert after == before


def test_resolve_rosters_uses_exact_match_before_falling_back_to_relaxed() -> None:
    game = broadcast(
        home_school_id="home-school",
        visitor_school_id="visitor-school",
        level="Junior Varsity",
    )
    rosters = [
        roster(id="home-exact", school_id="home-school", level="Junior Varsity"),
        roster(id="home-varsity", school_id="home-school", level="Varsity"),
        roster(id="visitor-varsity", school_id="visitor-school", level="Varsity"),
    ]
    service = make_service(rosters=rosters)
    home, visitor = service._resolve_rosters(game)
    assert home is not None and home["id"] == "home-exact"
    assert visitor is not None and visitor["id"] == "visitor-varsity"


def test_resolve_rosters_prefers_package_linked_roster_over_fallback() -> None:
    game = broadcast(broadcast_id="BC-1")
    rosters = [
        roster(id="linked-roster", school_id="home-school", level="Junior Varsity"),
        roster(id="fallback-roster", school_id="home-school", level="Varsity"),
    ]
    packages = [{"broadcast_id": "BC-1", "roster_ids": ["linked-roster"]}]
    service = make_service(rosters=rosters, packages=packages)
    home, _ = service._resolve_rosters(game)
    # Linked-by-package match ignores level/division entirely -- it should
    # win even though its level doesn't match the broadcast's.
    assert home is not None and home["id"] == "linked-roster"


def test_resolve_rosters_returns_none_when_nothing_matches() -> None:
    game = broadcast(home_school_id="ghost-school")
    service = make_service(rosters=[roster(school_id="home-school")])
    home, _ = service._resolve_rosters(game)
    assert home is None


def test_render_document_uses_middle_dot_entity_for_matchup_separator() -> None:
    service = make_service()
    document = service._render_document(
        broadcast(),
        roster(id="home-roster", school_id="home-school"),
        roster(id="visitor-roster", school_id="visitor-school"),
    )

    assert "Football &middot; Varsity" in document
    assert "Football ? Varsity" not in document
    assert "Football | Varsity" not in document


def players(count: int) -> list[dict]:
    return [
        {
            "id": f"p{i}",
            "number": str(i),
            "first_name": f"Player{i}",
            "last_name": "Test",
            "position": "WR",
            "pronunciation": "",
            "status": "active",
        }
        for i in range(count)
    ]


def test_roster_pages_stays_a_single_column_at_or_under_capacity() -> None:
    # 38 is ROWS_PER_COLUMN -- exactly at the single-column cutoff.
    service = make_service()
    html = service._roster_pages(roster(players=players(38)), "Team", "")
    assert html.count('<section class="roster-page">') == 1
    assert "roster-columns" not in html


def test_roster_pages_condenses_a_large_roster_to_exactly_two_pages() -> None:
    # A roster over 76 active players (2 x ROWS_PER_COLUMN) previously
    # split into 2 logical chunks that each still overflowed onto extra
    # physical pages -- confirmed against Itawamba AHS's real 82-player
    # roster, which rendered as 4 physical pages instead of 2. Each
    # oversized half now lays out as 2 columns on the same physical page
    # instead of spilling further.
    service = make_service()
    html = service._roster_pages(roster(players=players(82)), "Team", "")
    assert html.count('<section class="roster-page">') == 2
    assert html.count('<div class="roster-columns">') == 2


def test_roster_pages_mid_size_roster_still_uses_two_plain_pages() -> None:
    # 39-76 players: still exactly 2 pages, but each half already fits in
    # a single column (no need for the 2-column layout).
    service = make_service()
    html = service._roster_pages(roster(players=players(72)), "Team", "")
    assert html.count('<section class="roster-page">') == 2
    assert "roster-columns" not in html
