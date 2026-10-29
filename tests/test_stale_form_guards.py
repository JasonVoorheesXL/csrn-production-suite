"""Server-side guards against stale or duplicate play forms (2026-10-25 game simulation).

* A run/pass/punt form opened before the previous play's state arrived carries
  the old start spot. The server used to trust it, so the yards were measured
  from the wrong spot. It now refuses the play (STALE_PLAY_FORM) unless the
  statistician deliberately corrected the start spot.
* A kickoff submitted when no kickoff is pending was recorded as a second
  kickoff. It is now refused (KICKOFF_NOT_PENDING).
* The defense could punt. A scrimmage punt now has to come from the offense.
* Mutation responses carry the derived team_roles / canonical_field_state, so
  the console no longer keeps the previous play's offense and yards-to-goal.
"""
from __future__ import annotations

from live_command_service import command_result_state
from tests.test_rules_service import base_state, build_service


def _run(start: str, end: str, **extra):
    return {"team": "home", "play_type": "run", "player_number": "22",
            "start_spot": start, "end_spot": end, **extra}


def test_stale_start_spot_is_refused_and_nothing_is_saved() -> None:
    service, current, saved, *_ = build_service()  # ball at LEFT 20, home driving right
    result = service.play(_run("LEFT 14", "LEFT 30", start_spot_corrected=False))
    assert result.code == "STALE_PLAY_FORM"
    assert result.data["ball_spot"] == "LEFT 20"
    assert current["ball_spot"] == "LEFT 20"
    assert current["down"] == "1st"
    assert saved == []


def test_matching_start_spot_is_recorded() -> None:
    service, current, *_ = build_service()
    result = service.play(_run("LEFT 20", "LEFT 24", start_spot_corrected=False))
    assert result.code == "OK"
    assert current["ball_spot"] == "LEFT 24"
    assert current["down"] == "2nd" and current["distance"] == "6"


def test_hand_corrected_start_spot_is_honoured() -> None:
    service, current, *_ = build_service()
    result = service.play(_run("LEFT 25", "LEFT 30", start_spot_corrected=True))
    assert result.code == "OK"
    assert result.data["play"]["yards"] == 5


def test_callers_that_do_not_send_the_flag_keep_the_old_behaviour() -> None:
    service, current, *_ = build_service()
    result = service.play(_run("LEFT 25", "LEFT 30"))
    assert result.code == "OK"


def test_kickoff_without_a_pending_kickoff_is_refused() -> None:
    service, current, saved, *_ = build_service()
    result = service.play({"team": "visitor", "play_type": "kickoff", "start_spot": "RIGHT 40",
                           "landing_spot": "LEFT 5", "end_spot": "LEFT 30", "kicker_number": "3"})
    assert result.code == "KICKOFF_NOT_PENDING"
    assert current["possession"] == "home"
    assert saved == []


def test_kickoff_during_the_kickoff_phase_is_recorded() -> None:
    state = base_state()
    state.update({"special_game_phase": "kickoff", "kicking_team": "visitor", "possession": "visitor"})
    service, current, *_ = build_service(state)
    result = service.play({"team": "visitor", "play_type": "kickoff", "start_spot": "RIGHT 40",
                           "landing_spot": "LEFT 5", "end_spot": "LEFT 30", "kicker_number": "3",
                           "returner_number": "22"})
    assert result.code == "OK"
    assert current["possession"] == "home"
    assert current["special_game_phase"] == ""


def test_defense_cannot_punt_from_scrimmage() -> None:
    service, current, saved, *_ = build_service()
    result = service.play({"team": "visitor", "play_type": "punt", "start_spot": "LEFT 20",
                           "landing_spot": "LEFT 60", "end_spot": "LEFT 60", "kicker_number": "3"})
    assert result.code == "TEAM_ROLE_MISMATCH"
    assert saved == []


def test_offense_punt_is_recorded() -> None:
    service, current, *_ = build_service()
    result = service.play({"team": "home", "play_type": "punt", "start_spot": "LEFT 20",
                           "landing_spot": "RIGHT 40", "end_spot": "RIGHT 40", "kicker_number": "9",
                           "downed": True})
    assert result.code == "OK"
    assert current["possession"] == "visitor"


def test_command_result_state_carries_fresh_derived_fields() -> None:
    state = base_state()
    state.update({"possession": "visitor", "ball_spot": "LEFT 4", "down": "1st", "distance": "10",
                  "team_roles": {"offense": "home", "defense": "visitor"},  # stale copy
                  "canonical_field_state": {"yards_to_goal": 80}})
    result = command_result_state(state)
    assert result["team_roles"]["offense"] == "visitor"
    assert result["canonical_field_state"]["yards_to_goal"] == 4
    assert result["canonical_field_state"]["goal_to_go"] is True
