"""Regression coverage for incident FB-2026-5A-W04-001 (Caledonia vs. New
Albany, 2026-09-18) -- six reported bugs, one section per bug.

Section 1/2: ball_spot must follow the direction swap at quarter breaks.
"""

from __future__ import annotations

import pytest

from canonical_state_service import CanonicalStateFoundation as C
from period_service import PeriodService


def _state(**patch):
    state = {
        "broadcast_id": "B1",
        "status": "live",
        "broadcast_phase": "live",
        "quarter": "1",
        "home_score": 0,
        "visitor_score": 0,
        "home_direction": "right",
        "visitor_direction": "left",
        "possession": "home",
        "down": "2nd",
        "distance": "6",
        "ball_spot": "LEFT 34",
        "clock_seconds": 0,
        "clock_running": False,
        "clock_started_at": 0,
        "clock_visible": True,
        "special_game_phase": "",
        "kicking_team": "",
        "receiving_team": "",
        "plays": [],
        "penalty_administration": {},
    }
    state.update(patch)
    return state


# --- Bugs 1 & 2: ball spot mirrors with the direction swap -----------------


@pytest.mark.parametrize(
    "before,after",
    [
        ("LEFT 40", "RIGHT 40"),
        ("RIGHT 40", "LEFT 40"),
        ("LEFT 1", "RIGHT 1"),
        ("RIGHT 1", "LEFT 1"),
        ("LEFT GOAL", "RIGHT GOAL"),
        ("RIGHT GOAL", "LEFT GOAL"),
        ("50", "50"),
        # legacy HOME/VISITOR aliases normalise to the canonical spelling
        ("HOME 30", "RIGHT 30"),
    ],
)
def test_mirror_spot_boundaries(before: str, after: str) -> None:
    assert C.mirror_spot(before) == after


@pytest.mark.parametrize("spot", ["", None, "somewhere", "Own 20"])
def test_mirror_spot_leaves_empty_or_unrecognised_spots_alone(spot) -> None:
    assert C.mirror_spot(spot) == spot


def test_mirror_spot_is_its_own_inverse() -> None:
    for coord in range(0, 101):
        spot = C._coord_to_spot(coord)
        assert C.mirror_spot(C.mirror_spot(spot)) == spot


def test_q1_to_q2_mirrors_ball_spot() -> None:
    r = PeriodService.transition(_state(ball_spot="LEFT 40"), "end_quarter")
    assert r.ok and r.data["transition"] == "Q1_TO_Q2"
    assert r.state["ball_spot"] == "RIGHT 40"
    assert (r.state["home_direction"], r.state["visitor_direction"]) == ("left", "right")


def test_q3_to_q4_mirrors_ball_spot() -> None:
    r = PeriodService.transition(
        _state(quarter="3", home_direction="left", visitor_direction="right", ball_spot="RIGHT 12"),
        "end_quarter",
    )
    assert r.ok and r.data["transition"] == "Q3_TO_Q4"
    assert r.state["ball_spot"] == "LEFT 12"
    assert (r.state["home_direction"], r.state["visitor_direction"]) == ("right", "left")


def test_q2_to_halftime_does_not_move_the_ball() -> None:
    # No change of ends at the end of Q2 -- that happens at start_second_half.
    r = PeriodService.transition(_state(quarter="2", ball_spot="LEFT 40"), "end_quarter")
    assert r.data["transition"] == "Q2_TO_HALFTIME"
    assert r.state["ball_spot"] == "LEFT 40"
    assert (r.state["home_direction"], r.state["visitor_direction"]) == ("right", "left")


def test_halftime_to_q3_leaves_a_correct_kickoff_spot_after_the_swap() -> None:
    """start_second_half swaps directions, then enter_kickoff places the ball.
    The kickoff spot must sit on the *kicking team's own 40* in the new
    orientation, not on the side left over from the first half."""
    state = _state(
        quarter="2",
        broadcast_phase="halftime",
        period_state="halftime",
        ball_spot="LEFT 40",
        plays=[{"play_type": "kickoff", "offense": "home", "undone": False}],
    )
    r = PeriodService.transition(state, "start_second_half")
    assert r.ok and r.data["transition"] == "HALFTIME_TO_Q3_KICKOFF"
    s = r.state
    assert (s["home_direction"], s["visitor_direction"]) == ("left", "right")
    assert s["kicking_team"] == "visitor"  # home kicked off, so visitor kicks to start Q3
    # visitor now drives right (defends the LEFT end), own 40 == LEFT 40
    assert s["ball_spot"] == C._team_own_yard_spot(s, "visitor", 40) == "LEFT 40"


@pytest.mark.parametrize(
    "state_patch,action",
    [
        ({"quarter": "1"}, "end_quarter"),
        ({"quarter": "3", "home_direction": "left", "visitor_direction": "right"}, "end_quarter"),
    ],
)
@pytest.mark.parametrize("spot", ["LEFT 3", "LEFT 49", "50", "RIGHT 49", "RIGHT 3", "LEFT GOAL"])
@pytest.mark.parametrize("possession", ["home", "visitor"])
def test_swap_preserves_yards_to_goal_and_series(state_patch, action, spot, possession) -> None:
    """The point of mirroring: the offense must be exactly as far from the
    goal it is attacking after the teams change ends as it was before."""
    before = _state(ball_spot=spot, possession=possession, **state_patch)
    after = PeriodService.transition(before, action).state
    assert C.yards_to_goal(after) == C.yards_to_goal(before)
    assert (after["down"], after["distance"], after["possession"]) == (
        before["down"],
        before["distance"],
        before["possession"],
    )


def test_swap_mirrors_on_a_110_yard_canadian_field() -> None:
    canadian = _state(country="CA", region="ON", association="CJFL", ball_spot="LEFT 20")
    assert C._field_length(canadian) == 110
    after = PeriodService.transition(canadian, "end_quarter").state
    assert after["ball_spot"] == "RIGHT 20"
    assert C.yards_to_goal(after) == C.yards_to_goal(canadian)
    # midfield on a 110 field is 55
    mid = PeriodService.transition({**canadian, "ball_spot": "55"}, "end_quarter").state
    assert mid["ball_spot"] == "55"


def test_swap_with_no_ball_spot_does_not_invent_one() -> None:
    r = PeriodService.transition(_state(ball_spot=""), "end_quarter")
    assert r.ok and r.state["ball_spot"] == ""
