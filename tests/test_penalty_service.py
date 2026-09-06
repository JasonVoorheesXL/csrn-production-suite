"""Regression coverage for PenaltyService.enforce()'s down/distance math.

2026-09 bug: an accepted penalty's ball-spot movement was always correct,
but distance-to-go could come out inverted (or off by 2x the enforced
yardage) depending on which physical end zone the offense happened to be
driving toward this half (state[f"{team}_direction"]). The bug was keying
the distance branch off `move_sign` (which folds in `direction`) instead of
the direction-independent `against_offense`/`against_defense` flags -- see
penalty_service.py's enforce() for the full explanation. These tests pin
the fix for BOTH values of team_direction so the sign can never silently
flip back.
"""
from __future__ import annotations

import pytest

from penalty_service import PenaltyService


def spot_to_coord(value) -> int:
    # Test double: ball_spot is just a plain 0-100 coordinate string, so the
    # penalty math under test is fully isolated from real yard-line-string
    # parsing (owned by RulesService, not PenaltyService).
    return int(str(value))


def coord_to_spot(coord: int) -> str:
    return str(int(coord))


def make_team_direction(direction: int):
    def _team_direction(state, team):
        # Offense drives the same physical way regardless of which team is
        # "home"/"visitor" here -- only `direction`'s sign matters for the
        # bug (it flips halfway through every game and can be overridden).
        return direction if team == state.get("possession", "home") else -direction

    return _team_direction


def base_state(*, ball_spot: str = "30", down: str = "1st", distance: str = "10") -> dict:
    return {
        "possession": "home",
        "down": down,
        "distance": distance,
        "ball_spot": ball_spot,
        "special_game_phase": "",
        "home_direction": "right",
        "visitor_direction": "left",
    }


@pytest.mark.parametrize("direction", [1, -1])
def test_false_start_always_increases_distance_by_the_enforced_yardage(direction: int) -> None:
    # 1st & 10 at the 30. False start (Offensive, 5 yards, no loss of down):
    # ball moves back 5 (away from the line-to-gain) and the down is
    # replayed from farther out, so distance must become 15 -- regardless
    # of team_direction.
    state = base_state(ball_spot="30", down="1st", distance="10")
    result = PenaltyService.enforce(
        state,
        selected_team="home",
        requested_unit="Offensive",
        name="False Start",
        yards=5,
        outcome="accepted",
        spot_to_coord=spot_to_coord,
        coord_to_spot=coord_to_spot,
        team_direction=make_team_direction(direction),
    )
    assert result["applied"] is True
    assert state["down"] == "1st"
    assert state["distance"] == "15"


@pytest.mark.parametrize("direction", [1, -1])
def test_defensive_offside_always_decreases_distance_by_the_enforced_yardage(direction: int) -> None:
    # 1st & 10 at the 30. Defensive Offside (5 yards, not automatic first
    # down): ball moves 5 toward the line-to-gain, so distance must become
    # 5 -- regardless of team_direction.
    state = base_state(ball_spot="30", down="1st", distance="10")
    result = PenaltyService.enforce(
        state,
        selected_team="visitor",
        requested_unit="Defensive",
        name="Offside",
        yards=5,
        outcome="accepted",
        spot_to_coord=spot_to_coord,
        coord_to_spot=coord_to_spot,
        team_direction=make_team_direction(direction),
    )
    assert result["applied"] is True
    assert state["down"] == "1st"
    assert state["distance"] == "5"


@pytest.mark.parametrize("direction", [1, -1])
def test_defensive_foul_that_reaches_the_line_to_gain_awards_a_first_down(direction: int) -> None:
    # 3rd & 3. A 5-yard defensive foul more than covers the distance, so it
    # should award a fresh 1st & 10, regardless of team_direction.
    state = base_state(ball_spot="30", down="3rd", distance="3")
    PenaltyService.enforce(
        state,
        selected_team="visitor",
        requested_unit="Defensive",
        name="Offside",
        yards=5,
        outcome="accepted",
        spot_to_coord=spot_to_coord,
        coord_to_spot=coord_to_spot,
        team_direction=make_team_direction(direction),
    )
    assert state["down"] == "1st"
    assert state["distance"] == "10"


@pytest.mark.parametrize("direction", [1, -1])
def test_automatic_first_down_penalty_is_unaffected_by_direction(direction: int) -> None:
    # Defensive Pass Interference is automatic_first_down regardless of
    # enforced yardage; this branch never touched move_sign even before the
    # fix, but is covered here as a direction-invariance sanity check.
    state = base_state(ball_spot="30", down="2nd", distance="8")
    PenaltyService.enforce(
        state,
        selected_team="visitor",
        requested_unit="Defensive",
        name="Pass Interference",
        yards=15,
        outcome="accepted",
        spot_to_coord=spot_to_coord,
        coord_to_spot=coord_to_spot,
        team_direction=make_team_direction(direction),
    )
    assert state["down"] == "1st"
    assert state["distance"] == "10"


@pytest.mark.parametrize("direction", [1, -1])
def test_offensive_loss_of_down_penalty_advances_the_down_and_adds_distance(direction: int) -> None:
    # Intentional Grounding: 5 yards + loss of down. Distance still moves
    # away from the line-to-gain (like any offensive foul); the down also
    # advances. Neither consequence should depend on team_direction.
    state = base_state(ball_spot="30", down="2nd", distance="8")
    PenaltyService.enforce(
        state,
        selected_team="home",
        requested_unit="Offensive",
        name="Intentional Grounding",
        yards=5,
        outcome="accepted",
        spot_to_coord=spot_to_coord,
        coord_to_spot=coord_to_spot,
        team_direction=make_team_direction(direction),
    )
    assert state["down"] == "3rd"
    assert state["distance"] == "13"


def test_declined_penalty_leaves_state_untouched() -> None:
    state = base_state(ball_spot="30", down="1st", distance="10")
    result = PenaltyService.enforce(
        state,
        selected_team="home",
        requested_unit="Offensive",
        name="False Start",
        yards=5,
        outcome="declined",
        spot_to_coord=spot_to_coord,
        coord_to_spot=coord_to_spot,
        team_direction=make_team_direction(1),
    )
    assert result["applied"] is False
    assert state["down"] == "1st"
    assert state["distance"] == "10"
    assert state["ball_spot"] == "30"
