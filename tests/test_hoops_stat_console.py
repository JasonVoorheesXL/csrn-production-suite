"""The tap-the-court basketball console: spots, notes on saved plays, and the
engine fixes it needed. Full click-through runs live in a throwaway app; these pin
the rules underneath."""

from __future__ import annotations

import copy
import re
from pathlib import Path

import pytest

import hoops_game_operations_service as svc
from hoops_box_score_service import HoopsBoxScoreService
from hoops_event_service import HoopsEventService
from hoops_rules_service import HoopsRulesService
from hoops_period_service import HoopsPeriodService
from hoops_shot_geometry import clean_spot, is_three, shots_with_notes, zone
from hoops_state_service import HoopsStateFoundation

ROOT = Path(__file__).resolve().parents[1]
RIGHT_WING_THREE = {"spotX": 62.0, "spotY": 40.0}


def game() -> dict:
    state = {"sport": "basketball", "ruleset_id": "basketball/us-ms-mhsaa", "hoops": {}}
    state["hoops"] = {}
    HoopsPeriodService.start_game(state, HoopsRulesService.active_ruleset(state))
    return state


def shot(state, **extra):
    return HoopsRulesService.shot(state, {"team": "home", "made": True, "points": 3, "shooterId": "p22", **extra}).data["event"]


@pytest.mark.parametrize("x,y,expected", [
    (84, 1, True),  # the corner, outside the straight line
    (80, 4, True),
    (80, 7, False),
    (62, 40, True),
    (66.5, 39, False),  # looks far out, still inside the arc
    (58, 25, True),
    (59.0, 25, False),  # on the line is a 2
    (70, 25, False),
])
def test_three_point_line(x, y, expected) -> None:
    assert is_three(x, y) is expected


@pytest.mark.parametrize("x,y,expected", [
    (77, 26, "rim"), (68, 27, "paint"), (58, 25, "top_three"), (70, 12, "mid_range"),
    (62, 8, "left_wing_three"), (62, 42, "right_wing_three"), (82, 3, "left_corner_three"), (82, 47, "right_corner_three"),
])
def test_zones_are_from_the_shooters_view(x, y, expected) -> None:
    assert zone(x, y) == expected


def test_bad_spots_are_dropped_and_good_ones_are_kept_on_the_court() -> None:
    assert "spotX" not in clean_spot({"team": "home", "spotX": "nope", "spotY": 3, "zone": "rim"})
    assert "zone" not in clean_spot({"team": "home", "spotX": float("nan"), "spotY": 3, "zone": "rim"})
    assert clean_spot({"spotX": 500, "spotY": -4}) == {"spotX": 84.0, "spotY": 0.0, "zone": "left_corner_three"}


def test_a_shot_stores_its_zone_and_can_say_who_has_the_ball_next() -> None:
    state = game()
    event = shot(state, **RIGHT_WING_THREE, possessionAfter="visitor", shotType="")
    assert event["payload"]["zone"] == "right_wing_three"
    assert state["home_score"] == 3 and state["possession"] == "visitor"


def test_who_has_the_ball_survives_a_replay() -> None:
    state = game()
    shot(state, possessionAfter="visitor")
    HoopsRulesService.foul(state, {"team": "home", "playerId": "p1", "foulType": "personal", "possessionAfter": "visitor"})
    HoopsRulesService.free_throw(state, {"team": "visitor", "made": True, "possessionAfter": "home"})
    rebuilt = HoopsStateFoundation.rebuild(state, state["hoops"]["hoops_events"])
    assert rebuilt["possession"] == "home" and rebuilt["visitor_score"] == 1


def test_notes_credit_players_and_undo_takes_back_only_the_note() -> None:
    state = game()
    target = shot(state)["event_id"]
    HoopsRulesService.play_note(state, {"targetEventId": target, "assistId": "p2"})
    assert HoopsBoxScoreService.player_box(state)["p2"]["ast"] == 1
    HoopsEventService.undo(state)
    box = HoopsBoxScoreService.player_box(state)
    assert box["p22"]["pts"] == 3 and box.get("p2", {}).get("ast", 0) == 0


def test_a_note_on_a_deleted_play_does_not_count_and_a_missing_play_is_refused() -> None:
    state = game()
    target = shot(state)["event_id"]
    HoopsRulesService.play_note(state, {"targetEventId": target, "assistId": "p2"})
    HoopsEventService.void_event(state, target)
    assert HoopsBoxScoreService.player_box(state).get("p2", {}).get("ast", 0) == 0
    with pytest.raises(ValueError):
        HoopsRulesService.play_note(state, {"targetEventId": target, "assistId": "p2"})
    with pytest.raises(ValueError):
        HoopsRulesService.play_note(state, {"targetEventId": "nope", "assistId": "p2"})


def test_steal_with_stolen_from_note() -> None:
    state = game()
    event = HoopsRulesService.turnover(state, {"team": "visitor", "stealPlayerId": "p2"}).data["event"]
    HoopsRulesService.play_note(state, {"targetEventId": event["event_id"], "turnoverPlayerId": "n5"})
    box = HoopsBoxScoreService.player_box(state)
    assert box["p2"]["stl"] == 1 and box["n5"]["to"] == 1 and state["possession"] == "home"


def test_a_fouled_shot_keeps_its_spot_without_charging_an_attempt() -> None:
    state = game()
    event = HoopsRulesService.foul(state, {"team": "visitor", "playerId": "n10", "foulType": "shooting", "isShootingFoul": True, "shotPoints": 3, "drewFoulOn": "p22", "possessionAfter": "home", **RIGHT_WING_THREE}).data["event"]
    assert event["payload"]["zone"] == "right_wing_three"
    assert "p22" not in HoopsBoxScoreService.player_box(state)


def test_opening_tip_sets_ball_and_arrow_and_undoes() -> None:
    state = game()
    HoopsRulesService.opening_tip(state, {"team": "home"})
    assert state["possession"] == "home" and state["hoops"]["possession_arrow"] == "visitor"
    HoopsEventService.undo(state)
    assert state["hoops"]["possession_arrow"] != "visitor"
    with pytest.raises(ValueError):
        HoopsRulesService.opening_tip(state, {"team": "nobody"})


def test_ends_can_be_swapped_and_replay() -> None:
    state = game()
    HoopsRulesService.set_direction(state, {"homeFirstHalfAttacks": "left"})
    assert HoopsStateFoundation.rebuild(state, state["hoops"]["hoops_events"])["hoops"]["home_first_half_attacks"] == "left"
    with pytest.raises(ValueError):
        HoopsRulesService.set_direction(state, {"homeFirstHalfAttacks": "up"})


def test_undoing_a_play_leaves_the_running_clock_alone() -> None:
    state = game()
    shot(state)
    state.update(clock_seconds=312, clock_running=True, clock_started_at=99)
    HoopsEventService.undo(state)
    assert state["home_score"] == 0
    assert (state["clock_seconds"], state["clock_running"], state["clock_started_at"]) == (312, True, 99)
    HoopsEventService.redo(state)
    assert state["home_score"] == 3 and state["clock_seconds"] == 312


def test_deleting_or_correcting_an_old_play_leaves_the_clock_alone() -> None:
    state = game()
    target = shot(state)["event_id"]
    state["clock_seconds"] = 200
    HoopsEventService.correct_event(state, target, {"team": "home", "made": True, "points": 2, "shooterId": "p22", "spotX": 70, "spotY": 25})
    assert state["clock_seconds"] == 200 and state["home_score"] == 2
    assert [e for e in state["hoops"]["hoops_events"] if e["event_type"] == "SHOT"][-1]["payload"]["zone"] == "paint"


def test_ending_a_quarter_moves_on_and_undo_comes_back() -> None:
    state = game()
    state.update(clock_seconds=93, clock_running=True)
    result = HoopsRulesService.end_period(state)
    assert result.data["period_closed"] and state["period"] == "2" and state["clock_seconds"] == 480 and not state["clock_running"]
    HoopsEventService.undo(state)
    assert state["period"] == "1"


def test_ending_the_fourth_with_a_decided_score_proposes_a_final() -> None:
    state = game()
    state["period"] = "4"
    shot(state)
    HoopsRulesService.end_period(state)
    assert state["period"] == "4" and state["hoops"]["game_end_candidate"]


def test_shots_with_notes_merges_for_the_chart_and_skips_deleted() -> None:
    state = game()
    first = shot(state, **RIGHT_WING_THREE)["event_id"]
    gone = shot(state, shooterId="p9")["event_id"]
    HoopsRulesService.play_note(state, {"targetEventId": first, "assistId": "p2", "tags": ["fast_break"]})
    HoopsEventService.void_event(state, gone)
    shots = shots_with_notes(state["hoops"]["hoops_events"])
    assert len(shots) == 1 and shots[0]["assistId"] == "p2" and shots[0]["tags"] == ["fast_break"] and shots[0]["zone"] == "right_wing_three"


def test_the_game_operations_layer_runs_the_new_actions() -> None:
    store = {"state": game()}
    import threading

    service = svc.HoopsGameOperationsService(
        load_state=lambda: copy.deepcopy(store["state"]),
        save_state=lambda value: store.update(state=copy.deepcopy(value)),
        transaction_lock=threading.RLock(),
    )
    assert service.dispatch("opening_tip", {"team": "visitor"}).ok
    assert service.dispatch("set_direction", {"homeFirstHalfAttacks": "left"}).ok
    assert service.dispatch("end_period", {}).ok
    assert store["state"]["period"] == "2"
    assert not service.dispatch("play_note", {"targetEventId": "nope"}).ok


def test_console_only_calls_real_actions_and_is_wired_in() -> None:
    js = (ROOT / "static/csrn-hoops-console.js").read_text(encoding="utf-8")
    index = (ROOT / "templates/index.html").read_text(encoding="utf-8")
    assert '{% include "_hoops_stat_console.html" %}' in index and "/static/csrn-hoops-console.js" in index
    assert "renderHoopsConsole()" in index
    used = set(re.findall(r"hcSend\('([a-z_]+)'", js))
    assert used and used <= set(svc.ACTIONS)


def test_console_and_engine_agree_on_the_court() -> None:
    js = (ROOT / "static/csrn-hoops-console.js").read_text(encoding="utf-8")
    for name in ("rim", "paint", "mid_range", "top_three", "left_wing_three", "right_wing_three", "left_corner_three", "right_corner_three"):
        assert name in js
    assert "rimX: 78.75" in js and "arc: 19.75" in js and "cornerY: 5.25" in js


def test_console_turns_the_clock_on_for_a_new_game_only() -> None:
    js = (ROOT / "static/csrn-hoops-console.js").read_text(encoding="utf-8")
    assert "currentState.clock_visible === false && !hcClockShown && !hcEvents().some(e => e.event_type === 'OPENING_TIP')" in js
    assert "clockAction('set', { seconds: Number(currentState.clock_seconds ?? 0), visible: true })" in js

