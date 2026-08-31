"""Round 10 Task C: the exported Game Statistics report's Play Register shows
"Player not entered" for plays recorded without a player, instead of the live
broadcast overlay's opposing-team mascot-name fallback.

This is a report-generator concern only. The live overlay keeps rendering the
mascot fallback (rules_service builds it into the stored play/event text and
StatisticsService must not disturb that source data).
"""

from __future__ import annotations

import copy
from typing import Any

from statistics_service import StatisticsService

LABEL = "Player not entered"


def _state(*plays: dict[str, Any]) -> dict[str, Any]:
    return {
        "broadcast_id": "FB-2026-77",
        "sport": "Football",
        "home_team": "Caledonia",
        "visitor_team": "New Hope",
        "home_score": 0,
        "visitor_score": 0,
        "events": [],
        "plays": [dict(p, broadcast_id="FB-2026-77") for p in plays],
    }


def _register(state: dict[str, Any]) -> list[dict[str, Any]]:
    result = StatisticsService(now=lambda: 1_700_000_000).report(state)
    assert result.ok
    return result.data["statistics"]["play_register"]


def test_run_with_no_player_entered_shows_player_not_entered() -> None:
    reg = _register(_state({
        "play_id": "P1", "play_number": "1", "quarter": "1",
        "play_type": "run", "offense": "home", "defense": "visitor",
        "player_number": "", "player_name": "",
        "result": "New Hope run for 3 yards", "yards": 3,
    }))
    assert reg[0]["result"] == LABEL
    assert reg[0]["description"] == LABEL


def test_pass_with_no_passer_entered_shows_player_not_entered() -> None:
    reg = _register(_state({
        "play_id": "P1", "play_number": "1", "quarter": "1",
        "play_type": "pass", "offense": "home", "defense": "visitor",
        "passer_number": "", "passer_name": "",
        "result": "New Hope complete a pass for 8 yards", "yards": 8,
    }))
    assert reg[0]["result"] == LABEL


def test_play_with_a_recorded_player_number_is_left_alone() -> None:
    reg = _register(_state({
        "play_id": "P1", "play_number": "1", "quarter": "1",
        "play_type": "run", "offense": "home", "defense": "visitor",
        "player_number": "22", "player_name": "Smith",
        "result": "#22 Smith run for 3 yards", "yards": 3,
    }))
    assert reg[0]["result"] == "#22 Smith run for 3 yards"


def test_play_with_a_name_but_no_number_is_left_alone() -> None:
    # rules_service only falls back to the mascot when BOTH number and name are
    # missing; a name-only play already reads fine, so it is not overridden.
    reg = _register(_state({
        "play_id": "P1", "play_number": "1", "quarter": "1",
        "play_type": "run", "offense": "home", "defense": "visitor",
        "player_number": "", "player_name": "Smith",
        "result": "Smith run for 3 yards", "yards": 3,
    }))
    assert reg[0]["result"] == "Smith run for 3 yards"


def test_kickoff_without_a_returner_keeps_its_rendered_text() -> None:
    reg = _register(_state({
        "play_id": "P1", "play_number": "1", "quarter": "1",
        "play_type": "kickoff", "offense": "visitor", "defense": "home",
        "kicking_team": "home", "player_number": "", "player_name": "",
        "result": "Kickoff by #9 landed at RIGHT 40, ball at RIGHT 20 — touchback",
        "yards": 0,
    }))
    assert reg[0]["result"].startswith("Kickoff by #9")


def test_report_does_not_mutate_the_source_play_overlay_text() -> None:
    state = _state({
        "play_id": "P1", "play_number": "1", "quarter": "1",
        "play_type": "run", "offense": "home", "defense": "visitor",
        "player_number": "", "player_name": "",
        "result": "New Hope run for 3 yards", "yards": 3,
    })
    before = copy.deepcopy(state["plays"])
    reg = _register(state)
    assert reg[0]["result"] == LABEL
    # The overlay's source data is untouched -- still the mascot fallback.
    assert state["plays"] == before
    assert state["plays"][0]["result"] == "New Hope run for 3 yards"
