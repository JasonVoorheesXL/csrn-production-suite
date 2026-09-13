"""Baseball engine P2 acceptance -- diamond_event_service (undo/redo parity,
Sec.15.2 EVENT_VOIDED/EVENT_CORRECTED, COR-01) and game_suspension_service
(Sec.11.4, SUS-01). No UI, no routes -- direct service-to-service calls,
matching P0/P1/lineup's own discipline.
"""

from __future__ import annotations

from at_bat_rules_service import AtBatRulesService
from diamond_event_service import DiamondEventService
from diamond_state_service import DiamondStateFoundation, default_state
from game_suspension_service import GameSuspensionService
from lineup_service import LineupService
from lineup_service import default_state as lineup_default_state


def _new_game() -> dict:
    state = {"sport": "baseball", "status": "live", "home_score": 0, "visitor_score": 0}
    state.update(default_state())
    state.update(lineup_default_state())
    return state


def _score(team: str, runs: int) -> dict:
    return {
        "battingTeam": team,
        "runnerOutcomes": [{"from": "batter", "to": "score"} for _ in range(runs)],
        "outsRecorded": 0,
    }


def _out(team: str) -> dict:
    return {"battingTeam": team, "runnerOutcomes": [], "outsRecorded": 1}


# --- undo/redo parity with football's contract -------------------------


def test_undo_voids_the_most_recent_event_and_recomputes_state() -> None:
    state = _new_game()
    AtBatRulesService.record_plate_appearance(state, _score("visitor", 1))
    AtBatRulesService.record_plate_appearance(state, _score("visitor", 1))
    assert state["visitor_score"] == 2

    result = DiamondEventService.undo(state)
    assert result.ok
    assert state["visitor_score"] == 1
    # the undone event is retained in the ledger, marked voided -- not deleted.
    voided = [e for e in state["diamond_events"] if e["voided"]]
    assert len(voided) == 1


def test_redo_restores_the_most_recently_undone_event() -> None:
    state = _new_game()
    AtBatRulesService.record_plate_appearance(state, _score("visitor", 1))
    AtBatRulesService.record_plate_appearance(state, _score("visitor", 2))
    DiamondEventService.undo(state)
    assert state["visitor_score"] == 1

    result = DiamondEventService.redo(state)
    assert result.ok
    assert state["visitor_score"] == 3


def test_undo_with_no_events_is_a_clean_no_op_result() -> None:
    state = _new_game()
    result = DiamondEventService.undo(state)
    assert result.code == "NO_EVENTS_TO_UNDO"


def test_redo_with_nothing_voided_is_a_clean_no_op_result() -> None:
    state = _new_game()
    AtBatRulesService.record_plate_appearance(state, _score("visitor", 1))
    result = DiamondEventService.redo(state)
    assert result.code == "NO_EVENTS_TO_REDO"


# --- Sec.15.2 EVENT_VOIDED / COR-01 EVENT_CORRECTED ---------------------


def test_void_event_targets_a_specific_earlier_event_not_just_the_latest() -> None:
    state = _new_game()
    AtBatRulesService.record_plate_appearance(state, _score("visitor", 1))  # event 1
    AtBatRulesService.record_plate_appearance(state, _score("home", 2))  # event 2
    AtBatRulesService.record_plate_appearance(state, _score("visitor", 1))  # event 3
    assert state["visitor_score"] == 2 and state["home_score"] == 2

    result = DiamondEventService.void_event(state, "evt-1", reason="scorer error")
    assert result.ok
    # visitor's first run is gone; home's run and visitor's third-event run remain.
    assert state["visitor_score"] == 1
    assert state["home_score"] == 2


def test_COR_01_correcting_a_runner_destination_recomputes_bases_score_and_stats() -> None:
    # Sec.15.2: "Scorer corrects runner destination -> Original event
    # retained; correction recomputes bases/score/stats." Fully ledger-
    # driven (both the runner's initial placement AND the play being
    # corrected are real events), so the correction's rebuild-from-scratch
    # genuinely exercises recomputation rather than starting from state
    # that only existed outside the ledger.
    state = _new_game()
    AtBatRulesService.record_plate_appearance(
        state, {"battingTeam": "home", "runnerOutcomes": [{"from": "batter", "to": "second", "playerId": "runner-9"}], "outsRecorded": 0}
    )
    assert state["base_runners"]["second"]["player_id"] == "runner-9"

    advance = AtBatRulesService.record_plate_appearance(
        state, {"battingTeam": "home", "runnerOutcomes": [{"from": "second", "to": "third"}], "outsRecorded": 0}
    )
    event_id = advance.data["event"]["event_id"]
    assert state["base_runners"]["third"]["player_id"] == "runner-9"
    assert state["base_runners"]["second"] is None
    assert state["home_score"] == 0

    # The scorer realizes the runner actually scored on that play, not just
    # advanced to third.
    result = DiamondEventService.correct_event(
        state, event_id,
        {"battingTeam": "home", "runnerOutcomes": [{"from": "second", "to": "score"}], "outsRecorded": 0},
        reason="runner actually scored, not just advanced to third",
    )
    assert result.ok
    assert state["home_score"] == 1
    assert state["base_runners"]["third"] is None
    assert state["base_runners"]["second"] is None
    # original event retained (voided, not deleted); a new event references it.
    original_event = next(e for e in state["diamond_events"] if e["event_id"] == event_id)
    assert original_event["voided"] is True
    new_event = next(e for e in state["diamond_events"] if e.get("corrects_event_id") == event_id)
    assert new_event["voided"] is False


# --- Sec.11.4 SUS-01 ------------------------------------------------------


def test_SUS_01_suspend_and_resume_restores_exact_count_runners_batter_lineup_and_profile() -> None:
    state = _new_game()
    state["effective_profile_id"] = "baseball/us-nfhs"
    state["effective_profile_version"] = 3
    DiamondStateFoundation.set_count(state, balls=2, strikes=1)
    DiamondStateFoundation.place_runner(state, "first", "runner-1", reason="PLATE_APPEARANCE")
    DiamondStateFoundation.place_runner(state, "third", "runner-3", reason="PLATE_APPEARANCE")
    state["current_batter_id"] = "batter-5"
    LineupService.start_lineup(state, "home", {i: f"home-p{i}" for i in range(1, 10)}, {"P": "home-p1"}, sport="baseball")

    suspend_result = GameSuspensionService.suspend(state, reason="lightning")
    assert suspend_result.ok
    assert state["status"] == "suspended"

    # Simulate time passing / the app being reloaded: mutate live state to
    # prove resume restores from the SNAPSHOT, not incidental live drift.
    state["balls"] = 0
    state["strikes"] = 0
    DiamondStateFoundation.clear_bases(state)
    state["current_batter_id"] = "someone-else"

    resume_result = GameSuspensionService.resume(state)
    assert resume_result.ok
    assert state["status"] == "live"
    assert state["balls"] == 2 and state["strikes"] == 1
    assert state["base_runners"]["first"]["player_id"] == "runner-1"
    assert state["base_runners"]["third"]["player_id"] == "runner-3"
    assert state["current_batter_id"] == "batter-5"
    assert state["lineup"]["home"]["slots"]["1"]["active_player_id"] == "home-p1"
    assert state["effective_profile_id"] == "baseball/us-nfhs"
    assert state["effective_profile_version"] == 3


def test_resume_without_a_suspension_is_a_clean_no_op_result() -> None:
    state = _new_game()
    result = GameSuspensionService.resume(state)
    assert result.code == "NOT_SUSPENDED"


def test_suspending_an_already_suspended_game_is_rejected_not_silently_overwritten() -> None:
    state = _new_game()
    GameSuspensionService.suspend(state, reason="weather")
    result = GameSuspensionService.suspend(state, reason="second reason")
    assert result.code == "ALREADY_SUSPENDED"
