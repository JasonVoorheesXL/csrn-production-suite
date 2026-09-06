"""Coverage for the "Muffed Punt" outcome added to the statistician's punt
entry form (2026-09) -- previously a muffed punt recovered by the kicking
team could only be recorded with the generic Fumble/Fumble-lost checkboxes,
which mis-attributed the turnover to the receiving team (opposite(team))
instead of the kicking team that actually recovered it, and reported it as
a plain "fumble_recovery" rather than the distinct "muff_recovery" type
statistics_service already understands.
"""
from __future__ import annotations

import threading

from rules_service import RulesService


def make_state() -> dict:
    return {
        "home_team": "Home Tigers",
        "visitor_team": "Visitor Wolves",
        "possession": "home",
        "down": "4th",
        "distance": "8",
        "ball_spot": "HOME 35",
        "quarter": "2",
        "clock_seconds": 400,
        "home_direction": "right",
        "visitor_direction": "left",
        "broadcast_id": "TEST-GAME",
        "next_play_number": 1,
        "team_roles": {},
        "special_game_phase": "",
    }


def make_service(state: dict) -> RulesService:
    return RulesService(
        load_state=lambda: state,
        save_state=lambda s: state.update(s),
        push_history=lambda s: None,
        source_allowed=lambda s, src: True,
        locked_payload=lambda s: s,
        resolve_player=lambda s, team, number: {},
        show_player_graphic=lambda *a, **k: None,
        transaction_lock=threading.Lock(),
    )


BASE_PAYLOAD = {
    "team": "home",
    "play_type": "punt",
    "start_spot": "HOME 35",
    "landing_spot": "VISITOR 30",
    "end_spot": "VISITOR 32",
    "kicker_number": "9",
    "returner_number": "22",
}


def test_muffed_punt_recovered_by_kicking_team_is_a_turnover_and_keeps_possession() -> None:
    state = make_state()
    service = make_service(state)
    payload = {**BASE_PAYLOAD, "muffed_punt": True, "fumble_lost": True}

    result = service.play(payload)

    assert result.ok
    play = result.data["play"]
    assert state["possession"] == "home"  # kicking team retains the ball
    assert play["turnover"] is True
    assert play["turnover_type"] == "muff_recovery"
    assert play["turnover_team"] == "home"
    assert play["muffed_punt"] is True
    # No jersey was captured for the kicking-team recovery, so this must not
    # be misattributed to the receiving team's returner.
    assert play["turnover_player_number"] == ""
    assert play["turnover_player_name"] == ""
    assert "muffed" in play["result"].lower()
    assert "recovered by the kicking team" in play["result"]


def test_muffed_punt_recovered_by_receiving_team_is_not_a_turnover() -> None:
    state = make_state()
    service = make_service(state)
    payload = {**BASE_PAYLOAD, "muffed_punt": True, "fumble_lost": False}

    result = service.play(payload)

    assert result.ok
    play = result.data["play"]
    assert state["possession"] == "visitor"  # normal punt possession flip
    assert play["turnover"] is False
    assert play["turnover_type"] == ""
    assert play["muffed_punt"] is True
    assert "recovered by the receiving team" in play["result"]


def test_ordinary_punt_is_unaffected() -> None:
    state = make_state()
    service = make_service(state)
    payload = {**BASE_PAYLOAD, "end_spot": "VISITOR 25"}

    result = service.play(payload)

    assert result.ok
    play = result.data["play"]
    assert state["possession"] == "visitor"
    assert play["turnover"] is False
    assert play.get("muffed_punt") is False
    assert "muffed" not in play["result"].lower()
