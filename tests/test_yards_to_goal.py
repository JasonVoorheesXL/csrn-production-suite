"""CanonicalStateFoundation.yards_to_goal / field_state red-zone coverage.

Spec (from the operator): yards-to-goal is measured toward the end zone the
POSSESSING team is driving toward, not toward whichever team's territory the
yard line happens to be labeled with. It must also stay correct across
halftime, when possession direction flips.

Field-coordinate model (canonical_state_service._spot_to_coord):
    coord 0   = LEFT / HOME goal line
    coord 100 = RIGHT / VISITOR goal line
    "LEFT 30" -> 30,  "RIGHT 30" -> 70
"""

from __future__ import annotations

from canonical_state_service import CanonicalStateFoundation as C


def _state(**over):
    base = {
        "home_team": "Itawamba",
        "visitor_team": "Caledonia",
        "possession": "home",
        "ball_spot": "50",
        "down": "1st",
        "distance": "10",
        "quarter": "1",
        "home_direction": "right",
        "visitor_direction": "left",
    }
    base.update(over)
    return base


# --- the operator's exact example -------------------------------------------
# "Caledonia 30" == 30 yards from Caledonia's goal line. Caledonia's goal is
# the RIGHT goal (visitor drives left / defends right), i.e. coord 100, so the
# spot is coord 70 -> "RIGHT 30".

def test_offense_driving_toward_that_goal_has_the_short_number() -> None:
    # Itawamba (home, driving right toward Caledonia's goal) on the Caledonia 30.
    s = _state(possession="home", ball_spot="RIGHT 30", home_direction="right")
    assert C.yards_to_goal(s) == 30


def test_offense_in_its_own_territory_has_the_long_number() -> None:
    # Same physical spot, but Caledonia (visitor) has it, driving left toward
    # the far goal -- it is their own 30, so 70 to score.
    s = _state(possession="visitor", ball_spot="RIGHT 30", visitor_direction="left")
    assert C.yards_to_goal(s) == 70


# --- direction, not label, is what matters --------------------------------

def test_same_spot_flips_with_possession() -> None:
    spot = "LEFT 25"  # coord 25
    home = _state(possession="home", ball_spot=spot, home_direction="right")
    visitor = _state(possession="visitor", ball_spot=spot, visitor_direction="left")
    assert C.yards_to_goal(home) == 75   # home drives right: 100 - 25
    assert C.yards_to_goal(visitor) == 25  # visitor drives left: 25


def test_own_short_yard_line_is_not_the_red_zone() -> None:
    # Ball on HOME 15 (coord 15), home driving right -> 85 to score, NOT red zone.
    s = _state(possession="home", ball_spot="LEFT 15", home_direction="right")
    assert C.yards_to_goal(s) == 85
    assert C.field_state(s)["red_zone"] is False


def test_opponent_short_yard_line_is_the_red_zone() -> None:
    s = _state(possession="home", ball_spot="RIGHT 8", home_direction="right")
    assert C.yards_to_goal(s) == 8
    fs = C.field_state(s)
    assert fs["red_zone"] is True
    assert fs["yards_to_goal"] == 8


# --- halftime: possession direction flips, math stays right ---------------

def test_survives_halftime_direction_flip() -> None:
    # First half: home drives right. Ball on coord 60 ("RIGHT 40").
    first = _state(possession="home", ball_spot="RIGHT 40",
                   home_direction="right", visitor_direction="left", quarter="2")
    assert C.yards_to_goal(first) == 40

    # Third quarter: ends switched. Home now drives LEFT. Same physical spot,
    # same possession -> now 60 to score.
    second = _state(possession="home", ball_spot="RIGHT 40",
                    home_direction="left", visitor_direction="right", quarter="3")
    assert C.yards_to_goal(second) == 60


# --- edges ---------------------------------------------------------------

def test_midfield_is_fifty_either_way() -> None:
    assert C.yards_to_goal(_state(ball_spot="50", possession="home")) == 50
    assert C.yards_to_goal(_state(ball_spot="50", possession="visitor")) == 50


def test_missing_ball_spot_defaults_to_midfield_not_a_crash() -> None:
    s = _state(possession="home")
    s["ball_spot"] = ""
    assert C.yards_to_goal(s) == 50


def test_field_state_exposes_both_keys() -> None:
    fs = C.field_state(_state(possession="home", ball_spot="RIGHT 5", home_direction="right"))
    assert fs["yards_to_goal"] == 5
    assert fs["red_zone"] is True
