from __future__ import annotations

from contextlib import nullcontext

from game_operations_service import GameOperationsService
from period_service import PeriodService


def base_state(**patch):
    state = {
        "broadcast_id": "B1",
        "status": "live",
        "broadcast_phase": "live",
        "quarter": "1",
        "home_score": 7,
        "visitor_score": 3,
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
        "scorebug_visible": True,
        "special_game_phase": "",
        "kicking_team": "",
        "receiving_team": "",
        "game_data_authority": "statistician",
        "history": [],
        "plays": [],
        "penalty_administration": {},
    }
    state.update(patch)
    return state


def test_q1_to_q2_preserves_series_and_physical_spot_but_reverses_direction():
    r = PeriodService.transition(base_state(), "end_quarter")
    assert r.ok
    s = r.state
    assert (s["quarter"], s["down"], s["distance"], s["ball_spot"], s["possession"]) == ("2", "2nd", "6", "LEFT 34", "home")
    assert (s["home_direction"], s["visitor_direction"]) == ("left", "right")
    assert s["clock_seconds"] == 720 and not s["clock_running"]


def test_q3_to_q4_has_same_period_reset_contract():
    r = PeriodService.transition(base_state(quarter="3", home_direction="left", visitor_direction="right"), "end_quarter")
    s = r.state
    assert s["quarter"] == "4" and s["clock_seconds"] == 720
    assert (s["home_direction"], s["visitor_direction"]) == ("right", "left")
    assert s["ball_spot"] == "LEFT 34" and s["down"] == "2nd"


def test_q2_end_enters_halftime_without_carrying_directly_into_q3():
    r = PeriodService.transition(base_state(quarter="2"), "end_quarter")
    s = r.state
    assert s["quarter"] == "2"
    assert s["broadcast_phase"] == "halftime"
    assert s["period_state"] == "halftime"
    assert s["halftime_pending_second_half"] is True
    assert s["ball_spot"] == "LEFT 34" and s["down"] == "2nd"


def test_second_half_kickoff_is_derived_from_opening_kick_when_available():
    state = base_state(
        quarter="2",
        broadcast_phase="halftime",
        period_state="halftime",
        plays=[{"play_type": "kickoff", "offense": "home", "undone": False}],
    )
    r = PeriodService.transition(state, "start_second_half")
    assert r.ok
    s = r.state
    # Home kicked the opening kickoff, so home receives to start Q3 and visitor kicks.
    assert s["quarter"] == "3" and s["broadcast_phase"] == "live"
    assert s["second_half_receiving_team"] == "home"
    assert s["kicking_team"] == "visitor" and s["receiving_team"] == "home"
    assert s["special_game_phase"] == "kickoff"
    assert s["clock_seconds"] == 720 and not s["clock_running"]


def test_second_half_requires_receiver_when_opening_kick_cannot_be_inferred():
    r = PeriodService.transition(base_state(quarter="2", broadcast_phase="halftime", period_state="halftime"), "start_second_half")
    assert r.code == "SECOND_HALF_RECEIVER_REQUIRED"
    assert r.state["quarter"] == "2"


def test_pending_try_and_penalty_untimed_down_hold_period_transition():
    pending = PeriodService.transition(base_state(special_game_phase="pending_try"), "end_quarter")
    assert pending.code == "PERIOD_HELD" and pending.state["quarter"] == "1"
    assert pending.state["period_hold_reason"] == "PENDING_TRY"

    untimed = PeriodService.transition(base_state(penalty_administration={"untimed_down": True}), "end_quarter")
    assert untimed.code == "PERIOD_HELD" and untimed.state["quarter"] == "1"
    assert untimed.state["period_hold_reason"] == "UNTIMED_DOWN"


def test_q4_end_requires_explicit_final_or_overtime_decision():
    r = PeriodService.transition(base_state(quarter="4", home_score=21, visitor_score=14), "end_quarter")
    s = r.state
    assert r.ok and s["quarter"] == "4"
    assert s["period_state"] == "q4_complete" and s["awaiting_period_decision"] is True
    assert s["broadcast_phase"] == "live" and s["status"] == "live"


def test_overtime_requires_operator_supplied_association_setup():
    base = base_state(quarter="4", period_state="q4_complete", awaiting_period_decision=True)
    missing = PeriodService.transition(base, "start_overtime")
    assert missing.code == "OVERTIME_SETUP_REQUIRED"
    ok = PeriodService.transition(base, "start_overtime", overtime_possession="visitor", overtime_spot="RIGHT 10")
    s = ok.state
    assert ok.ok and s["quarter"] == "OT" and s["period_state"] == "overtime"
    assert s["possession"] == "visitor" and s["ball_spot"] == "RIGHT 10"
    assert s["down"] == "1st" and s["distance"] == "10"
    assert s["clock_visible"] is False and not s["clock_running"]


def test_final_game_is_explicit_after_q4_complete():
    r = PeriodService.transition(base_state(quarter="4", period_state="q4_complete", awaiting_period_decision=True), "final_game")
    s = r.state
    assert r.ok and s["broadcast_phase"] == "final" and s["status"] == "completed"
    assert s["period_state"] == "final" and s["scorebug_visible"] is False


def build_ops(state):
    store = {"state": state}
    linked = []
    def load_state(): return store["state"]
    def save_state(value): store["state"] = dict(value)
    svc = GameOperationsService(
        load_state=load_state,
        save_state=save_state,
        default_state=lambda: base_state(),
        push_history=lambda s: s.setdefault("history", []).append({"quarter": s.get("quarter")}),
        source_allowed=lambda s, source: source == s.get("game_data_authority"),
        locked_payload=lambda s: {"message": "locked"},
        update_linked_status=lambda *args: linked.append(args),
        load_config=lambda: {},
        command_scorebug_visibility=lambda visible: None,
        transaction_lock=nullcontext(),
    )
    return svc, store, linked


def test_period_action_uses_existing_set_boundary_and_respects_source_authority():
    svc, store, _ = build_ops(base_state())
    blocked = svc.set_values({"source": "broadcaster", "period_action": "end_quarter"})
    assert blocked.code == "CONTROL_SOURCE_LOCKED" and store["state"]["quarter"] == "1"
    ok = svc.set_values({"source": "statistician", "period_action": "end_quarter"})
    assert ok.ok and store["state"]["quarter"] == "2"


def test_final_period_action_persists_linked_final_score():
    svc, store, linked = build_ops(base_state(quarter="4", period_state="q4_complete", awaiting_period_decision=True))
    r = svc.set_values({"source": "statistician", "period_action": "final_game"})
    assert r.ok and store["state"]["status"] == "completed"
    assert linked and linked[0][0:2] == ("B1", "completed")


def test_legacy_direct_quarter_set_remains_backward_compatible():
    svc, store, _ = build_ops(base_state())
    r = svc.set_values({"source": "statistician", "quarter": "3"})
    assert r.ok and store["state"]["quarter"] == "3"


