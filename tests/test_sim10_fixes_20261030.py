"""Fixes from the 10-game simulation of 2026-10-30 (MHSAA 2025 and 2024 finals).

1. Penalty and Timeout stay on the team cards while a kickoff or try is pending.
2. A foul after a play that earned a first down starts the new series (NFHS):
   D3 54-yard run to the MT 18, personal foul after the play -> 1st & Goal at
   the 9, not 1st & 1. Pre-snap fouls before the next snap do not.
3. Flag on the play for kickoffs and punts: enforced from the end of the return
   (or the spot of the foul), then the team with the ball has 1st & 10.
4. A foul by the team that gained a turnover leaves the turnover standing.
5. An interception downed in the end zone is a touchback.
6. "Returner out of bounds" is separate from the kick going out of bounds.
"""
from __future__ import annotations

from pathlib import Path

from tests.test_rules_service import base_state, build_service

HTML = (Path(__file__).resolve().parents[1] / "templates" / "index.html").read_text(encoding="utf-8")


def _state(**extra) -> dict:
    state = base_state()  # Caledonia (home) drives right, New Hope (visitor) left
    state.update(extra)
    return state


def _flag(team: str, unit: str, name: str, yards: int, enforcement: str = "end_of_play", **extra) -> dict:
    return {"team": team, "unit": unit, "name": name, "yards": yards, "outcome": "accepted",
            "enforcement": enforcement, **extra}


# ---------------------------------------------------------------- 2. new series
def test_a_defensive_foul_after_a_first_down_run_starts_the_new_series() -> None:
    # D3 Q3: 3rd & 2 at DeWitt's 28, run for 54 to the MT 18, personal foul on
    # Mt. Pleasant after the play: half the distance to the 9, 1st & Goal.
    service, current, *_ = build_service(_state(ball_spot="LEFT 28", down="3rd", distance="2"))
    result = service.play({"team": "home", "play_type": "run", "player_number": "22",
                           "start_spot": "LEFT 28", "end_spot": "RIGHT 18",
                           "flag": _flag("visitor", "Defensive", "Personal Foul", 15, "after_play")})
    assert result.code == "OK"
    assert (current["ball_spot"], current["down"], current["distance"]) == ("RIGHT 9", "1st", "9")


def test_an_offensive_foul_after_a_first_down_run_is_still_first_and_ten() -> None:
    # D2 Q2: Dexter runs for a first down, then a personal foul on Dexter: 1st & 10, not 1st & 25.
    service, current, *_ = build_service(_state(ball_spot="LEFT 29", down="3rd", distance="1"))
    result = service.play({"team": "home", "play_type": "run", "player_number": "22",
                           "start_spot": "LEFT 29", "end_spot": "LEFT 31",
                           "flag": _flag("home", "Offensive", "Personal Foul", 15, "after_play")})
    assert result.code == "OK"
    assert (current["ball_spot"], current["down"], current["distance"]) == ("LEFT 16", "1st", "10")


def test_a_dead_ball_foul_without_a_first_down_counts_the_down() -> None:
    service, current, *_ = build_service(_state(ball_spot="LEFT 30", down="2nd", distance="8"))
    service.play({"team": "home", "play_type": "run", "player_number": "22", "start_spot": "LEFT 30",
                  "end_spot": "LEFT 33", "flag": _flag("home", "Offensive", "Personal Foul", 15, "after_play")})
    assert (current["ball_spot"], current["down"], current["distance"]) == ("LEFT 18", "3rd", "20")


# ---------------------------------------------------------------- 3. kick flags
def test_a_face_mask_by_the_punting_team_is_enforced_from_the_end_of_the_return() -> None:
    service, current, *_ = build_service(_state(ball_spot="LEFT 30", down="4th", distance="8"))
    result = service.play({"team": "home", "play_type": "punt", "kicker_number": "7", "returner_number": "4",
                           "start_spot": "LEFT 30", "landing_spot": "RIGHT 20", "end_spot": "RIGHT 35",
                           "flag": _flag("home", "Special Teams", "Face Mask", 15)})
    assert result.code == "OK"
    assert (current["possession"], current["ball_spot"], current["down"], current["distance"]) == \
        ("visitor", "50", "1st", "10")
    assert "penalty on Caledonia: Face Mask" in current["plays"][-1]["result"]


def test_an_illegal_block_by_the_receiving_team_on_a_kickoff_return() -> None:
    # 2024 D2: kickoff returned to the OLSM 20, illegal block on OLSM 10 yards -> 1st & 10 at the OLSM 10.
    state = _state(ball_spot="LEFT 40", special_game_phase="kickoff", kicking_team="home", receiving_team="visitor")
    service, current, *_ = build_service(state)
    result = service.play({"team": "home", "play_type": "kickoff", "kicker_number": "7", "returner_number": "4",
                           "start_spot": "LEFT 40", "landing_spot": "RIGHT 3", "end_spot": "RIGHT 20",
                           "flag": _flag("visitor", "Special Teams", "Illegal Block", 10)})
    assert result.code == "OK"
    assert (current["possession"], current["ball_spot"], current["down"], current["distance"]) == \
        ("visitor", "RIGHT 10", "1st", "10")
    assert not current.get("special_game_phase")


# ---------------------------------------------------------------- 4. turnovers
def _interception(flag: dict) -> dict:
    return {"team": "home", "play_type": "pass", "passer_number": "12", "pass_outcome": "interception",
            "start_spot": "LEFT 40", "turnover_spot": "RIGHT 32", "return_end_spot": "RIGHT 47",
            "end_spot": "RIGHT 47", "returner_number": "24", "flag": flag}


def test_holding_by_the_intercepting_team_keeps_the_interception() -> None:
    # 2024 D1: intercepted at the CT 32, returned to the CT 47, holding on CT 10 yards -> 1st & 10 at the CT 37.
    service, current, *_ = build_service(_state(ball_spot="LEFT 40"))
    result = service.play(_interception(_flag("visitor", "Defensive", "Holding", 10)))
    assert result.code == "OK"
    assert (current["possession"], current["ball_spot"], current["down"], current["distance"]) == \
        ("visitor", "RIGHT 37", "1st", "10")


def test_a_foul_by_the_team_that_threw_it_still_wipes_out_the_interception() -> None:
    service, current, saved, *_ = build_service(_state(ball_spot="LEFT 40"))
    result = service.play(_interception(_flag("home", "Offensive", "Holding", 10)))
    assert result.code == "FLAG_NEEDS_NO_PLAY"
    assert saved == []


# ---------------------------------------------------------------- 5. touchback
def test_an_interception_downed_in_the_end_zone_is_a_touchback() -> None:
    # D7: intercepted in Menominee's end zone and downed there -> ball at the 20.
    service, current, *_ = build_service(_state(ball_spot="RIGHT 39"))
    result = service.play({"team": "home", "play_type": "pass", "passer_number": "12", "pass_outcome": "interception",
                           "start_spot": "RIGHT 39", "turnover_spot": "RIGHT GOAL", "return_end_spot": "RIGHT GOAL",
                           "end_spot": "RIGHT GOAL", "returner_number": "24", "touchback": True})
    assert result.code == "OK"
    assert (current["possession"], current["ball_spot"], current["down"], current["distance"]) == \
        ("visitor", "RIGHT 20", "1st", "10")
    assert (current["home_score"], current["visitor_score"]) == (0, 0)
    assert "touchback" in current["plays"][-1]["result"]
    assert current["plays"][-1]["entry"]["touchback"] is True


# ---------------------------------------------------------------- 6. returner out of bounds
def test_a_returner_out_of_bounds_is_noted_without_the_kick_out_of_bounds_rule() -> None:
    state = _state(ball_spot="LEFT 40", special_game_phase="kickoff", kicking_team="home", receiving_team="visitor")
    service, current, *_ = build_service(state)
    result = service.play({"team": "home", "play_type": "kickoff", "kicker_number": "7", "returner_number": "4",
                           "start_spot": "LEFT 40", "landing_spot": "RIGHT 5", "end_spot": "RIGHT 34",
                           "return_out_of_bounds": True})
    assert result.code == "OK"
    assert current["ball_spot"] == "RIGHT 34"
    assert current["plays"][-1]["result"].endswith("out of bounds")
    assert current["plays"][-1]["entry"]["return_out_of_bounds"] is True


# ---------------------------------------------------------------- console markup
def test_console_markup_for_the_fixes() -> None:
    for needle in (
        "const anyPhase=btn.classList.contains('timeout-button')||(btn.getAttribute('onclick')||'').includes('openPenalty')",
        "kickPhase?'Special Teams'",
        "const PRE_SNAP_FOULS=['False Start'", "function newSeriesPending()",
        "document.getElementById('penaltyNewSeries').checked=newSeriesPending()&&!PRE_SNAP_FOULS.includes(name)",
        "show('playFlagWrap',['run','pass','kickoff','punt'].includes(kind))", "function playFlagIsKick()",
        "'kicking team':'offense'", "['Face Mask',15],['Unsportsmanlike Conduct',15],",
        'id="playReturnOob"', "return_out_of_bounds:", "'Kick out of bounds':'Out of bounds'",
        "document.getElementById('playTouchbackWrap').classList.toggle('hidden',!turnover)",
        "end_of_play:'End of the return (or of the kick)'",
    ):
        assert needle in HTML, needle
