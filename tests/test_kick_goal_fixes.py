"""Kick and goal-line fixes from the 2026-10-25 three-game simulation.

* A first down inside the opponent's 10 is "1st & Goal": the stored distance
  is the yards to goal, and the series stays goal to go. It used to keep a
  10-yard line to gain past the goal line ("2nd & 16" at the 14).
* A foul before a kickoff only moves the kick spot ("Off & 15" before).
* Console: the kickoff out-of-bounds choice reaches the rules engine, kickoffs
  offer a fair catch, a pending kickoff starts from the stored kick spot, and
  a field goal fills in its distance and defaults a miss to a touchback.
"""
from __future__ import annotations

from pathlib import Path

from canonical_state_service import CanonicalStateFoundation as C
from penalty_service import PenaltyService
from tests.test_rules_service import base_state, build_service

HTML = (Path(__file__).resolve().parents[1] / "templates" / "index.html").read_text(encoding="utf-8")


def _run(start: str, end: str):
    return {"team": "home", "play_type": "run", "player_number": "22", "start_spot": start, "end_spot": end}


def test_first_down_inside_the_ten_is_first_and_goal() -> None:
    service, current, *_ = build_service()  # home at LEFT 20, driving right
    assert service.play(_run("LEFT 20", "RIGHT 6")).code == "OK"
    assert (current["down"], current["distance"]) == ("1st", "6")
    assert C.goal_to_go(current) is True
    assert service.play(_run("RIGHT 6", "RIGHT 4")).code == "OK"
    assert (current["down"], current["distance"]) == ("2nd", "4")


def test_a_short_gain_inside_the_ten_keeps_the_series_goal_to_go() -> None:
    state = base_state()
    state.update({"ball_spot": "RIGHT 12", "down": "1st", "distance": "10"})  # line to gain at the 2
    service, current, *_ = build_service(state)
    assert service.play(_run("RIGHT 12", "RIGHT 9")).code == "OK"
    assert (current["down"], current["distance"]) == ("2nd", "7")  # not goal to go: line at the 2
    assert C.goal_to_go(current) is False


def test_play_record_after_snapshot_carries_the_capped_distance() -> None:
    service, current, *_ = build_service()
    result = service.play(_run("LEFT 20", "RIGHT 3"))
    assert current["distance"] == "3"
    assert current["events"][-1]["after"]["distance"] == "3"
    assert result.data["play"]["play_type"] == "run"


def _enforce(state: dict, **kwargs):
    return PenaltyService.enforce(
        state,
        selected_team=kwargs.pop("selected_team", "home"),
        requested_unit=kwargs.pop("requested_unit", "General"),
        name=kwargs.pop("name", "Other"),
        yards=kwargs.pop("yards", 5),
        outcome="accepted",
        spot_to_coord=lambda v: C._spot_to_coord(v, state),
        coord_to_spot=lambda c: C._coord_to_spot(c, state),
        team_direction=lambda s, team: 1 if s.get(f"{team}_direction", "right") == "right" else -1,
    )


def test_a_foul_before_the_kickoff_only_moves_the_kick_spot() -> None:
    state = base_state()
    state.update({"special_game_phase": "kickoff", "kicking_team": "home", "possession": "home",
                  "ball_spot": "LEFT 40", "down": "Off", "distance": "Off"})
    result = _enforce(state, yards=5)
    assert result["applied"] is True
    assert state["ball_spot"] == "LEFT 35"
    assert (state["down"], state["distance"]) == ("Off", "Off")


def test_kickoff_fair_catch_is_recorded_without_a_return() -> None:
    state = base_state()
    state.update({"special_game_phase": "kickoff", "kicking_team": "visitor", "possession": "visitor"})
    service, current, *_ = build_service(state)
    result = service.play({"team": "visitor", "play_type": "kickoff", "start_spot": "RIGHT 40",
                           "landing_spot": "LEFT 25", "end_spot": "LEFT 25", "kicker_number": "3",
                           "returner_number": "22", "fair_catch": True})
    assert result.code == "OK"
    assert current["ball_spot"] == "LEFT 25" and current["possession"] == "home"
    assert "fair catch" in result.data["play"]["result"]
    assert "returned" not in result.data["play"]["result"]


def test_console_offers_the_kickoff_out_of_bounds_choice_and_sends_it() -> None:
    assert 'id="playKickOobChoice"' in HTML
    for choice in ("25_yard_line", "rekick", "spot_plus_5"):
        assert f'value="{choice}"' in HTML
    assert "payload.kick_out_of_bounds=true;payload.out_of_bounds_choice=document.getElementById('playKickOobChoice').value" in HTML


def test_console_offers_fair_catch_on_kickoffs() -> None:
    assert "show('playFairCatchWrap',['kickoff','punt'].includes(kind))" in HTML


def test_console_kickoff_starts_from_the_stored_kick_spot_on_the_kicking_side() -> None:
    assert "kickSpotOwnSide?inherited:(teamDirection===1?40:60)" in HTML


def test_console_field_goal_defaults() -> None:
    assert "String(toGoal+17)" in HTML
    assert "document.getElementById('automationKickTouchback').checked=outcome==='no_good'" in HTML
    assert "Enter the field goal distance." in HTML


def test_console_distance_picker_has_goal() -> None:
    assert "['Off','Goal',...Array.from" in HTML


def test_coin_toss_puts_the_opening_kickoff_at_the_kicking_teams_40() -> None:
    from tests.test_phase1c_football_rehearsal import coin_toss_client

    client, store = coin_toss_client()
    before = store.state.get("ball_spot")
    response = client.post("/api/coin-toss", json={
        "command_id": "coin-kick-spot", "source": "broadcaster",
        "winner": "home", "election": "defer", "opening_drive_direction": "right",
    })
    assert response.status_code == 200
    # Home deferred: visitor receives driving right, so home kicks from its own
    # 40 at the right end of the field.
    assert store.state["kicking_team"] == "home"
    assert store.state["ball_spot"] == "RIGHT 40"
    assert client.post("/api/coin-toss/undo", json={"command_id": "coin-kick-undo"}).status_code == 200
    assert store.state.get("ball_spot") == before
