"""Viewer/operator feedback after the Caledonia vs. East Webster broadcast (2026-09-26), Collegiate
Traditional live. Same investigate-then-fix discipline as docs/FOOTBALL_INCIDENT_20260918.md: each item
below was reproduced by execution (a real seeded broadcast, headless-Chrome captures at 1920x1080, then
downscaled to a real phone width) before being fixed, not diagnosed from source alone.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE_CSS = "static/csrn-broadcast-layout-engine.css"
NEON_CSS = "static/csrn-collegiate-neon.css"


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _rule(css: str, selector: str) -> str:
    start = css.index(selector) + len(selector)
    return css[start:css.index("}", start)]


# --- Item 1: Down & Distance too small on a phone-scaled OBS feed ------------------------------------


def test_item1_the_bl_down_class_the_report_named_is_dead_code_not_what_collegiate_renders() -> None:
    """The feedback framed this as 'Collegiate Traditional's .bl-down element ... per-package font-size
    overrides'. Verified live (headless capture, DOM inspection): Collegiate's football board has no
    .bl-down anywhere -- that class belongs to the RETIRED standalone Neon engine (.package-neon /
    .package-neon-approved, archived per docs/NEON_REDESIGN.md), which no live manifest selects any more.
    Collegiate's real Down & Distance is <b data-bind="game.downDistance"> inside .bl-college-field-meta
    (collegiateField() in the engine), confirmed live at a computed 19px before this fix."""
    js = read("static/csrn-broadcast-layout-engine.js")
    assert ".bl-down" not in js.split("function collegiateField(state) {")[1].split("\n  }\n")[0]
    assert 'data-bind="game.downDistance"' in js.split("function collegiateField(state) {")[1].split("\n  }\n")[0]
    css = read(ENGINE_CSS)
    down_rules = [m.start() for m in re.finditer(r"\.bl-down\b", css)]
    for pos in down_rules:
        # every remaining .bl-down selector in the shared engine CSS is scoped under the retired
        # standalone-Neon classes (or the unscoped base rule with no font-size) -- none under Collegiate
        line = css[max(0, pos - 80):pos]
        assert ".bl-collegiate" not in line, css[max(0, pos - 80):pos + 40]
    manifests = read("static/csrn-broadcast-layout-engine.js")
    assert '"package-neon"' not in manifests and "package-neon-approved" not in manifests


def test_item1_collegiates_readout_bar_value_text_was_increased_for_phone_legibility() -> None:
    """19px -> 26px, matching the same board's own Team Snapshot numbers (.bl-college-stat-grid strong,
    also 26px) so the bump lands on an already-established size in Collegiate's own UI rather than an
    arbitrary one. This is the fixed-canvas fix the report called for: the overlay renders into a literal
    1920x1080 canvas with no responsive breakpoint, so legibility at a scaled-down (phone) size can only
    come from a real font-size increase here."""
    css = read(ENGINE_CSS)
    meta = _rule(css, ".bl-college-field-meta b{")
    assert "font-size:26px" in meta
    label = _rule(css, ".bl-college-field-meta small{")
    assert "font-size:15px" in label
    stat_grid = _rule(css, ".bl-college-stat-grid strong{")
    assert "font-size:26px" in stat_grid  # the reference point this size was matched to
    # all four readout cells (Possession, Down, Ball, Line to gain) share one rule, so the bump is
    # uniform across the bar -- Down does not become visually inconsistent with its own siblings.


def test_item1_neons_callout_pill_grew_with_the_base_so_it_stays_the_largest_cell() -> None:
    """Neon overrides only the 2nd cell (Down & Distance, its callout pill) to a larger size than its
    siblings. With the base bumped to 26px the pill's old 25px override would have gone the wrong way --
    the callout would render SMALLER than the cells around it. Re-pinned to 32px, keeping it clearly the
    largest cell in the bar. Verified live under Neon: fits the same fixed 50px-tall row with no clipping."""
    css = read(NEON_CSS)
    pill_value = _rule(css, ".package-collegiate-neon .bl-college-field-meta span:nth-child(2) b {")
    assert "font-size: 32px;" in pill_value
    base_value = _rule(css, ".package-collegiate-neon .bl-college-field-meta b {")
    assert "font-size" not in base_value  # Neon only recolours the other three cells; size still comes from the engine CSS


# --- Item 4: kickoff out-of-bounds is not modeled by the rules engine ----------------------------------
#
# Rule confirmed against a state-association NFHS/NCAA rules-differences summary compiled by George
# Demetriou (NFHS rules interpreter, Colorado), "Free Kick Out-of-Bounds": NFHS gives the receiving team
# three enforcement choices when a free kick goes out of bounds between the goal lines untouched by them:
#   1. take the ball 25 yards from the previous spot (a new series there);
#   2. a 5-yard penalty and a re-kick from 5 yards behind the previous spot; or
#   3. the ball at the out-of-bounds spot plus a 5-yard penalty.
# This is a free-kick-only foul: a punt (a scrimmage kick) going out of bounds is ordinary and already
# handled by the existing return branch; nothing about punts changes here.

import copy  # noqa: E402

from tests.test_rules_service import base_state, build_service  # noqa: E402


def _kickoff_state() -> dict:
    st = base_state()
    st.update({"home_direction": "right", "visitor_direction": "left"})
    return st


def test_kickoff_out_of_bounds_requires_the_spot_and_a_choice() -> None:
    service, current, *_ = build_service(_kickoff_state())
    missing_choice = service.play({
        "team": "home", "play_type": "kickoff", "start_spot": "LEFT 40",
        "kicker_number": "7", "kick_out_of_bounds": True, "landing_spot": "LEFT 15",
    })
    assert missing_choice.code == "OUT_OF_BOUNDS_CHOICE_REQUIRED"
    assert current["possession"] == "home"  # nothing committed

    service, current, *_ = build_service(_kickoff_state())
    missing_spot = service.play({
        "team": "home", "play_type": "kickoff", "start_spot": "LEFT 40",
        "kicker_number": "7", "kick_out_of_bounds": True, "out_of_bounds_choice": "rekick",
    })
    assert missing_spot.code == "OUT_OF_BOUNDS_SPOT_REQUIRED"


def test_kickoff_out_of_bounds_25_yard_line_choice() -> None:
    """Kicked from LEFT 40, out at LEFT 15 -- R takes a new series 25 yards from the previous spot
    (the kick spot), in the direction of the kick: LEFT 40 + 25 = RIGHT 35."""
    service, current, *_ = build_service(_kickoff_state())
    result = service.play({
        "team": "home", "play_type": "kickoff", "start_spot": "LEFT 40", "kicker_number": "7",
        "kick_out_of_bounds": True, "landing_spot": "LEFT 15", "out_of_bounds_choice": "25_yard_line",
    })
    assert result.code == "OK"
    assert current["possession"] == "visitor"
    assert current["ball_spot"] == "RIGHT 35"
    assert current["down"] == "1st" and current["distance"] == "10"
    play = result.data["play"]
    assert play["landing_spot"] == "LEFT 15"
    assert "out of bounds" in play["result"] and "25 yards" in play["result"]


def test_kickoff_out_of_bounds_rekick_choice_keeps_possession_with_the_kicking_team() -> None:
    """A 5-yard penalty against K, re-kick from 5 yards behind the previous spot: LEFT 40 - 5 = LEFT 35.
    Possession does not change; the game goes back into the kickoff phase for the same kicking team."""
    service, current, *_ = build_service(_kickoff_state())
    result = service.play({
        "team": "home", "play_type": "kickoff", "start_spot": "LEFT 40", "kicker_number": "7",
        "kick_out_of_bounds": True, "landing_spot": "LEFT 15", "out_of_bounds_choice": "rekick",
    })
    assert result.code == "OK"
    assert current["possession"] == "home"
    assert current["kicking_team"] == "home"
    assert current["special_game_phase"] == "kickoff"
    assert current["ball_spot"] == "LEFT 35"


def test_kickoff_out_of_bounds_spot_plus_5_choice() -> None:
    """R takes the ball at the out-of-bounds spot plus a 5-yard penalty, further from their own goal:
    LEFT 15 + 5 = LEFT 20."""
    service, current, *_ = build_service(_kickoff_state())
    result = service.play({
        "team": "home", "play_type": "kickoff", "start_spot": "LEFT 40", "kicker_number": "7",
        "kick_out_of_bounds": True, "landing_spot": "LEFT 15", "out_of_bounds_choice": "spot_plus_5",
    })
    assert result.code == "OK"
    assert current["possession"] == "visitor"
    assert current["ball_spot"] == "LEFT 20"


def test_kickoff_out_of_bounds_is_a_free_kick_only_foul_punts_are_unaffected() -> None:
    """kick_out_of_bounds only ever applies to kind == 'kickoff' -- a punt with the same flag set is
    ignored and falls through to the ordinary kickoff/punt return branch, unchanged."""
    service, current, *_ = build_service(_kickoff_state())
    result = service.play({
        "team": "home", "play_type": "punt", "start_spot": "LEFT 20", "kicker_number": "7",
        "kick_out_of_bounds": True, "landing_spot": "RIGHT 30", "end_spot": "RIGHT 30",
        "out_of_bounds_choice": "25_yard_line",
    })
    assert result.code == "OK"
    assert current["possession"] == "visitor"
    assert current["ball_spot"] == "RIGHT 30"  # ordinary punt-return placement, the OOB fields are inert


def test_kickoff_out_of_bounds_clamps_within_the_field_rather_than_going_negative_or_past_the_goal() -> None:
    """A kick out of bounds deep in R's own territory: the 25-yard-line option must not walk the ball
    past R's own goal line (coord 0/length)."""
    st = _kickoff_state()
    service, current, *_ = build_service(st)
    result = service.play({
        "team": "home", "play_type": "kickoff", "start_spot": "LEFT 2", "kicker_number": "7",
        "kick_out_of_bounds": True, "landing_spot": "LEFT 1", "out_of_bounds_choice": "rekick",
    })
    assert result.code == "OK"
    assert current["ball_spot"] == "LEFT GOAL"  # clamped to the goal line, not past it
