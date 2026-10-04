from __future__ import annotations

import base64
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from social_media_preview_service import SocialMediaPreviewService  # noqa: E402


TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
    "+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def make_service(
    tmp_path: Path,
    *,
    broadcasts: list[dict] | None = None,
    sponsors: list[dict] | None = None,
    storylines: list[str] | None = None,
    rng: random.Random | None = None,
    players: list[dict] | None = None,
) -> SocialMediaPreviewService:
    output_dir = tmp_path / "Cards"
    logos_dir = tmp_path / "Logos" / "home-high"
    logos_dir.mkdir(parents=True, exist_ok=True)
    (logos_dir / "logo.png").write_bytes(TINY_PNG)
    assets_dir = tmp_path / "Assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    static_dir = tmp_path / "static"
    background_dir = static_dir / "friday-night-stadium" / "clash"
    background_dir.mkdir(parents=True, exist_ok=True)
    for name in (
        "football-field-background.png",
        "basketball-court-background.png",
        "baseball-ballpark-background.png",
        "softball-ballpark-background.png",
    ):
        (background_dir / name).write_bytes(TINY_PNG)

    default_broadcasts = broadcasts if broadcasts is not None else [
        {
            "broadcast_id": "BC-1",
            "home_team": "Home High",
            "visitor_team": "Visitor High",
            "home_school_id": "home-high",
            "visitor_school_id": "visitor-high",
            "home_identity": {"school_id": "home-high", "logo": "/school-logos/home-high/logo.png", "mascot": "Bears", "primary_color": "#0A2342"},
            "visitor_identity": {"mascot": "Wolves"},
            "status": "planned",
            "date": "2026-09-04",
            "scheduled_start": "7:00 PM",
            "venue": "Home Field",
            "sport": "Football",
        }
    ]

    class _Sponsors:
        def list_payload(self):
            return {"sponsors": sponsors if sponsors is not None else []}

    class _Theme:
        def status(self):
            class _Result:
                data = {
                    "theme": {
                        "active": {
                            "id": "collegiate_traditional",
                            "name": "Collegiate Tech",
                            "tokens": {
                                "primary_color": "#C9203B",
                                "secondary_color": "#111111",
                                "accent_color": "#FFFFFF",
                                "surface": "#07101A",
                                "surface_alt": "#122033",
                                "text": "#F8FBFF",
                                "muted": "#B9C7D8",
                                "border": "#BFC9D4",
                                "font_stack": "Arial, sans-serif",
                                "radius_px": 8,
                                "panel_opacity": 0.96,
                                "shadow": "0 18px 38px rgba(0,0,0,.5)",
                            },
                        }
                    }
                }
            return _Result()

    return SocialMediaPreviewService(
        load_broadcasts=lambda: default_broadcasts,
        load_state=lambda: {},
        load_final_state_archive=lambda broadcast_id: {
            "home_score": 24,
            "visitor_score": 17,
            "events": [{"team": "home", "event": "TD"}],
        } if broadcast_id == "BC-1" else None,
        get_school_logo_file=lambda school_id, filename: tmp_path / "Logos" / school_id / filename,
        get_asset_upload_dir=lambda: assets_dir,
        get_sponsor_service=lambda: _Sponsors(),
        get_theme_service=lambda: _Theme(),
        build_statistics=lambda state: {
            "scoring_summary": [
                {
                    "quarter": "3",
                    "team_name": "Home High",
                    "label": "TD",
                    "description": "12-yard run by #21",
                    "home_score": 24,
                    "visitor_score": 17,
                }
            ],
            "players": players or [],
        } if state else {"scoring_summary": [], "players": []},
        load_config=lambda: {
            "organization": {"short_name": "CSRN"},
            "streaming": {"youtube_live": "", "facebook_live": ""},
        },
        get_storylines=lambda broadcast_id: storylines if storylines is not None else [],
        get_static_dir=lambda: static_dir,
        output_dir=output_dir,
        rng=rng,
    )


def test_broadcast_not_found_returns_error(tmp_path: Path) -> None:
    service = make_service(tmp_path, broadcasts=[])
    result = service.generate("missing")
    assert result.code == "BROADCAST_NOT_FOUND"


def test_sponsor_selection_keeps_all_when_within_limit(tmp_path: Path) -> None:
    sponsors = [{"name": f"Sponsor {i}", "active": True, "logo_url": ""} for i in range(5)]
    service = make_service(tmp_path, sponsors=sponsors)
    selected = service._select_sponsors()
    assert len(selected) == 5


def test_sponsor_selection_randomizes_down_to_limit(tmp_path: Path) -> None:
    sponsors = [{"name": f"Sponsor {i}", "active": True, "logo_url": ""} for i in range(25)]
    service = make_service(tmp_path, sponsors=sponsors, rng=random.Random(42))
    selected = service._select_sponsors()
    assert len(selected) == 6
    names = {s["name"] for s in selected}
    assert len(names) == 6  # no duplicates picked


def test_sponsor_selection_excludes_inactive_and_expired(tmp_path: Path) -> None:
    sponsors = [
        {"name": "Active Co", "active": True, "logo_url": ""},
        {"name": "Inactive Co", "active": False, "logo_url": ""},
        {"name": "Expired Co", "active": True, "effective_status": "Expired", "logo_url": ""},
    ]
    service = make_service(tmp_path, sponsors=sponsors)
    selected = service._select_sponsors()
    assert [s["name"] for s in selected] == ["Active Co"]


def test_storylines_capped_at_five(tmp_path: Path) -> None:
    service = make_service(tmp_path, storylines=[f"Storyline {i}" for i in range(8)])
    storylines = service._storylines("BC-1")
    assert len(storylines) == 5
    assert storylines[0] == "Storyline 0"


def test_format_kickoff_uses_natural_language(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    line = service._format_kickoff(date="2026-09-11", scheduled_start="7:00 PM", venue="Cavalier Stadium")
    assert line == "Friday September 11th at 7pm · Cavalier Stadium"


def test_format_kickoff_keeps_minutes_when_not_on_the_hour(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    line = service._format_kickoff(date="2026-09-04", scheduled_start="7:30 PM", venue="")
    assert line == "Friday September 4th at 7:30pm"


def test_format_kickoff_falls_back_gracefully_on_bad_input(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    line = service._format_kickoff(date="", scheduled_start="", venue="Home Field")
    assert line == "Home Field"


def test_org_logo_uri_falls_back_to_builtin_logo(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    (service._get_static_dir() / "csrn-logo.png").write_bytes(TINY_PNG)
    uri = service._org_logo_uri({})
    assert uri.startswith("data:image/png;base64,")


def test_org_logo_uri_passes_through_data_uri(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    uri = service._org_logo_uri({"logo": "data:image/png;base64,ABC"})
    assert uri == "data:image/png;base64,ABC"


def test_background_resolves_per_sport(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    football = service._background_uri("Football")
    basketball = service._background_uri("basketball")
    unknown = service._background_uri("lacrosse")
    assert football.startswith("data:image/png;base64,")
    assert basketball.startswith("data:image/png;base64,")
    assert unknown == football  # unknown sports fall back to football art


def test_generate_renders_real_png_end_to_end_with_promo_layout(tmp_path: Path) -> None:
    service = make_service(tmp_path, storylines=["Undefeated rivals clash under the lights"])
    result = service.generate("BC-1")
    assert result.ok, result.data
    image_bytes = result.data["image"]
    assert image_bytes[:8] == b"\x89PNG\r\n\x1a\n"
    assert (tmp_path / "Cards" / result.data["filename"]).is_file()
    assert result.data["sponsor_count"] == 0
    assert result.data["storyline_count"] == 1


def test_score_line_hidden_for_planned_games(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    html = service._score_line_html(status="planned", visitor_name="V", home_name="H", visitor_score=0, home_score=0)
    assert html == ""
    html_live = service._score_line_html(status="live", visitor_name="V", home_name="H", visitor_score=7, home_score=3)
    assert "V 7" in html_live and "H 3" in html_live


# -- final score graphic (viewer feedback, 2026-09-26: "a final score graphic similar to the
# pregame social graphic we've built previously") ---------------------------------------------


def _final_document(tmp_path: Path, *, visitor_score: int, home_score: int, players: list[dict] | None = None, sport: str = "Football") -> str:
    broadcast = {
        "broadcast_id": "BC-1", "home_team": "Home High", "visitor_team": "Visitor High",
        "home_school_id": "home-high", "visitor_school_id": "visitor-high",
        "home_identity": {}, "visitor_identity": {}, "status": "completed", "sport": sport,
        "final_home_score": home_score, "final_visitor_score": visitor_score,
    }
    service = make_service(tmp_path, broadcasts=[broadcast], players=players)
    return service._render_final_score_document(
        broadcast=broadcast, state={}, theme=service._theme_tokens(), sponsors=[], players=players or [],
    )


def test_final_score_marks_only_the_winning_side_and_never_a_tie(tmp_path: Path) -> None:
    win = _final_document(tmp_path, visitor_score=24, home_score=17)
    assert 'stage-side stage-side-visitor final-winner"' in win
    assert 'stage-side stage-side-home"' in win  # the loser carries no winner class
    assert 'class="final-tag">FINAL<' in win
    tie = _final_document(tmp_path, visitor_score=14, home_score=14)
    assert 'stage-side stage-side-visitor final-winner"' not in tie
    assert 'stage-side stage-side-home final-winner"' not in tie


def test_final_score_document_has_no_final_record_line(tmp_path: Path) -> None:
    broadcast = {
        "broadcast_id": "BC-1", "home_team": "Home High", "visitor_team": "Visitor High",
        "status": "completed", "sport": "Football", "final_home_score": 24, "final_visitor_score": 17,
        "home_postgame_record": {"wins": 6, "losses": 2, "ties": 0},
        "visitor_postgame_record": {"wins": 5, "losses": 3, "ties": 0},
    }
    service = make_service(tmp_path, broadcasts=[broadcast])
    document = service._render_final_score_document(
        broadcast=broadcast, state={}, theme=service._theme_tokens(), sponsors=[], players=[],
    )
    assert "FINAL RECORD" not in document
    assert "final-records" not in document and "final-banner" not in document


FOOTBALL_PLAYERS = [
    {"team": "home", "name": "Marcus Johnson", "number": "21", "rushing_attempts": 18, "rushing_yards": 142, "rushing_touchdowns": 2,
     "pass_attempts": 0, "passing_yards": 0, "receptions": 0, "receiving_yards": 0, "receiving_touchdowns": 0, "field_goal_distances": []},
    {"team": "home", "name": "Dre Carter", "number": "7", "rushing_attempts": 0, "rushing_yards": 0, "rushing_touchdowns": 0,
     "pass_attempts": 14, "completions": 9, "passing_yards": 168, "passing_touchdowns": 2,
     "receptions": 0, "receiving_yards": 0, "receiving_touchdowns": 0, "field_goal_distances": []},
    {"team": "home", "name": "Tay Brooks", "number": "84", "rushing_attempts": 0, "rushing_yards": 0, "rushing_touchdowns": 0,
     "pass_attempts": 0, "passing_yards": 0, "receptions": 5, "receiving_yards": 96, "receiving_touchdowns": 1, "field_goal_distances": []},
    {"team": "home", "name": "Owen Hale", "number": "9", "rushing_attempts": 0, "rushing_yards": 0, "rushing_touchdowns": 0,
     "pass_attempts": 0, "passing_yards": 0, "receptions": 0, "receiving_yards": 0, "receiving_touchdowns": 0,
     "field_goal_distances": [32, 41]},
    {"team": "visitor", "name": "Jo Ramirez", "number": "3", "rushing_attempts": 12, "rushing_yards": 58, "rushing_touchdowns": 0,
     "pass_attempts": 0, "passing_yards": 0, "receptions": 0, "receiving_yards": 0, "receiving_touchdowns": 0, "field_goal_distances": []},
]


def test_highlights_pick_leaders_per_category_with_touchdowns_and_longest_fg(tmp_path: Path) -> None:
    document = _final_document(tmp_path, visitor_score=7, home_score=24, players=FOOTBALL_PLAYERS)
    assert "M. Johnson — 142 rush yds, 2 TD" in document
    assert "D. Carter — 168 pass yds, 2 TD" in document
    assert "T. Brooks — 96 rec yds, 1 TD" in document
    assert "O. Hale — 41-yd FG" in document  # longest made FG, not the first one recorded
    assert "J. Ramirez — 58 rush yds" in document
    assert "J. Ramirez — 58 rush yds, " not in document  # no TD suffix when there are none


def test_highlights_break_yardage_ties_by_touchdowns_then_lower_jersey(tmp_path: Path) -> None:
    tied = [
        {"team": "visitor", "name": "A Back", "number": "30", "rushing_attempts": 5, "rushing_yards": 40, "rushing_touchdowns": 0},
        {"team": "visitor", "name": "B Back", "number": "22", "rushing_attempts": 5, "rushing_yards": 40, "rushing_touchdowns": 1},
        {"team": "visitor", "name": "C Back", "number": "11", "rushing_attempts": 5, "rushing_yards": 40, "rushing_touchdowns": 0},
    ]
    document = _final_document(tmp_path, visitor_score=7, home_score=0, players=tied)
    assert "B. Back — 40 rush yds, 1 TD" in document  # the touchdown wins the tie
    tied[1]["rushing_touchdowns"] = 0
    document = _final_document(tmp_path, visitor_score=7, home_score=0, players=tied)
    assert "C. Back — 40 rush yds" in document  # then the lower jersey number


def test_highlights_omitted_for_sports_without_confirmed_categories(tmp_path: Path) -> None:
    document = _final_document(tmp_path, visitor_score=3, home_score=2, players=FOOTBALL_PLAYERS, sport="Basketball")
    assert 'class="final-highlights"' not in document


def test_highlights_omitted_when_no_player_stats_are_recorded(tmp_path: Path) -> None:
    document = _final_document(tmp_path, visitor_score=24, home_score=17, players=[])
    assert 'class="final-highlights"' not in document


def test_fg_distance_is_only_shown_when_recorded(tmp_path: Path) -> None:
    kicker_no_distance = [
        {"team": "home", "name": "Owen Hale", "number": "9", "rushing_attempts": 0, "field_goal_distances": []},
    ]
    document = _final_document(tmp_path, visitor_score=0, home_score=0, players=kicker_no_distance)
    assert 'class="final-highlights"' not in document
    assert "-yd FG" not in document

def test_resolve_game_state_falls_back_to_archive_when_live_state_was_cleared_post_game(tmp_path: Path) -> None:
    """Regression: a completed game whose live authority state had its events/plays cleared
    (end_game() archived them) must not resolve to that empty live state -- the highlights
    would silently disappear. The archive is the durable record."""
    broadcast = {"broadcast_id": "BC-1", "home_team": "Home High", "visitor_team": "Visitor High", "status": "completed"}
    service = make_service(tmp_path, broadcasts=[broadcast])
    service._load_state = lambda: {"broadcast_id": "BC-1", "status": "completed", "events": [], "plays": []}
    state = service._resolve_game_state(broadcast)
    assert state.get("events"), "must use the archived play data, not the cleared live state"


def test_generate_final_score_broadcast_not_found(tmp_path: Path) -> None:
    service = make_service(tmp_path, broadcasts=[])
    result = service.generate_final_score("missing")
    assert result.code == "BROADCAST_NOT_FOUND"


def test_generate_final_score_renders_real_png_with_the_frozen_final_score_and_records(tmp_path: Path) -> None:
    """Prefers final_home_score/final_visitor_score (frozen at completion) over whatever
    home_score/visitor_score last was -- a completed broadcast can have a stale in-progress
    score sitting in those generic fields."""
    broadcasts = [{
        "broadcast_id": "BC-1",
        "home_team": "Home High", "visitor_team": "Visitor High",
        "home_school_id": "home-high", "visitor_school_id": "visitor-high",
        "home_identity": {"school_id": "home-high", "logo": "/school-logos/home-high/logo.png", "mascot": "Bears", "primary_color": "#0A2342"},
        "visitor_identity": {"mascot": "Wolves"},
        "status": "completed", "sport": "Football",
        "home_score": 3, "visitor_score": 1,  # stale -- should be ignored in favor of final_*
        "final_home_score": 24, "final_visitor_score": 17,
        "home_postgame_record": {"wins": 6, "losses": 2, "ties": 0},
        "visitor_postgame_record": {"wins": 5, "losses": 3, "ties": 0},
    }]
    service = make_service(tmp_path, broadcasts=broadcasts)
    result = service.generate_final_score("BC-1")
    assert result.ok, result.data
    image_bytes = result.data["image"]
    assert image_bytes[:8] == b"\x89PNG\r\n\x1a\n"
    assert result.data["filename"] == "BC-1-final-score.png"
    assert (tmp_path / "Cards" / result.data["filename"]).is_file()
    assert result.data["filename"] != "BC-1-social-preview.png"  # a distinct file from the pregame graphic

    document = service._render_final_score_document(
        broadcast=broadcasts[0], state={}, theme=service._theme_tokens(), sponsors=[],
    )
    assert ">24<" in document and ">17<" in document
    assert ">3<" not in document and ">1<" not in document  # the stale score never appears
    assert "6-2" not in document and "FINAL RECORD" not in document  # the record line is gone
    assert "kickoff-line" not in document and "storylines" not in document  # pregame-only sections are gone


def test_generate_final_score_falls_back_to_state_score_when_not_yet_archived(tmp_path: Path) -> None:
    """A game that just ended may not have final_*_score written yet -- the live/archived
    state's own home_score/visitor_score (the same fallback generate() already uses) covers it."""
    broadcasts = [{
        "broadcast_id": "BC-1", "home_team": "Home High", "visitor_team": "Visitor High",
        "home_school_id": "home-high", "visitor_school_id": "visitor-high",
        "home_identity": {}, "visitor_identity": {}, "status": "completed", "sport": "Football",
    }]
    service = make_service(tmp_path, broadcasts=broadcasts)
    document = service._render_final_score_document(
        broadcast=broadcasts[0], state={"home_score": 24, "visitor_score": 17}, theme=service._theme_tokens(), sponsors=[],
    )
    assert ">24<" in document and ">17<" in document


if __name__ == "__main__":
    import tempfile

    failures = 0
    tests = [
        test_broadcast_not_found_returns_error,
        test_sponsor_selection_keeps_all_when_within_limit,
        test_sponsor_selection_randomizes_down_to_limit,
        test_sponsor_selection_excludes_inactive_and_expired,
        test_storylines_capped_at_five,
        test_format_kickoff_uses_natural_language,
        test_format_kickoff_keeps_minutes_when_not_on_the_hour,
        test_format_kickoff_falls_back_gracefully_on_bad_input,
        test_org_logo_uri_falls_back_to_builtin_logo,
        test_org_logo_uri_passes_through_data_uri,
        test_background_resolves_per_sport,
        test_generate_renders_real_png_end_to_end_with_promo_layout,
        test_score_line_hidden_for_planned_games,
        test_final_score_marks_only_the_winning_side_and_never_a_tie,
        test_final_score_document_has_no_final_record_line,
        test_highlights_pick_leaders_per_category_with_touchdowns_and_longest_fg,
        test_highlights_break_yardage_ties_by_touchdowns_then_lower_jersey,
        test_highlights_omitted_for_sports_without_confirmed_categories,
        test_highlights_omitted_when_no_player_stats_are_recorded,
        test_fg_distance_is_only_shown_when_recorded,
        test_resolve_game_state_falls_back_to_archive_when_live_state_was_cleared_post_game,
        test_generate_final_score_broadcast_not_found,
        test_generate_final_score_renders_real_png_with_the_frozen_final_score_and_records,
        test_generate_final_score_falls_back_to_state_score_when_not_yet_archived,
    ]
    for test in tests:
        with tempfile.TemporaryDirectory() as td:
            try:
                test(Path(td))
                print(f"PASS {test.__name__}")
            except Exception as exc:  # noqa: BLE001
                failures += 1
                print(f"FAIL {test.__name__}: {exc}")
    if failures:
        raise SystemExit(f"{failures} test(s) failed")
    print("All tests passed.")
