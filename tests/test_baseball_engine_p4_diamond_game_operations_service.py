"""Baseball engine P4: diamond_game_operations_service.py -- the
"game_operations_service baseball extensions" deferred from P2 to P4.
Exercises the persistence/locking boundary itself (load/save/lock,
duplicate-command protection, generic ACTIONS dispatch) rather than
re-testing the P1/P2 service logic those actions call into (already
covered by their own test files).
"""

from __future__ import annotations

import threading

import pytest

from diamond_game_operations_service import DiamondGameOperationsService


class _FakeStateStore:
    def __init__(self, state: dict) -> None:
        self.state = state
        self.saved: list[dict] = []

    def load(self) -> dict:
        return self.state

    def save(self, state: dict) -> None:
        self.state = state
        self.saved.append(state)


def _service(store: _FakeStateStore) -> DiamondGameOperationsService:
    return DiamondGameOperationsService(
        load_state=store.load,
        save_state=store.save,
        transaction_lock=threading.Lock(),
    )


def _baseball_state(**overrides) -> dict:
    state = {
        "sport": "baseball",
        "status": "live",
        "country": "US",
        "broadcast_id": "b1",
        "home_score": 0,
        "visitor_score": 0,
    }
    state.update(overrides)
    return state


def test_initialize_diamond_rejects_football() -> None:
    store = _FakeStateStore({"sport": "Football"})
    result = _service(store).initialize_diamond()
    assert result.code == "NOT_A_DIAMOND_SPORT"


def test_initialize_diamond_creates_a_fresh_diamond_for_baseball() -> None:
    store = _FakeStateStore(_baseball_state())
    result = _service(store).initialize_diamond()
    assert result.ok
    assert result.data["state"]["diamond"]["inning"] == 1
    assert store.state["diamond"]["inning"] == 1


def test_dispatch_unknown_action() -> None:
    store = _FakeStateStore(_baseball_state())
    result = _service(store).dispatch("not_a_real_action")
    assert result.code == "UNKNOWN_ACTION"


def test_dispatch_rejects_football() -> None:
    store = _FakeStateStore({"sport": "Football"})
    result = _service(store).dispatch("substitute", {"side": "home", "slot": 1, "incoming_player_id": "p1"})
    assert result.code == "NOT_A_DIAMOND_SPORT"


def test_dispatch_record_plate_appearance_syncs_score_and_persists() -> None:
    store = _FakeStateStore(_baseball_state())
    service = _service(store)
    result = service.dispatch("record_plate_appearance", {
        "battingTeam": "visitor", "batterId": "b1", "pitcherId": "p1",
        "resultCode": "HR",
        "runnerOutcomes": [{"from": "batter", "to": "score", "playerId": "b1"}],
        "outsRecorded": 0, "hits": 1,
    })
    assert result.ok
    assert store.state["diamond"]["visitor_score"] == 1
    assert store.state["visitor_score"] == 1
    assert len(store.saved) == 1


def test_dispatch_lineup_start_then_substitute() -> None:
    store = _FakeStateStore(_baseball_state())
    service = _service(store)
    start = service.dispatch("start_lineup", {
        "side": "home",
        "starters": {1: "h1", 2: "h2"},
        "defense": {"P": "h1"},
    })
    assert start.ok
    assert store.state["diamond"]["lineup"]["home"]["slots"]["1"]["active_player_id"] == "h1"

    sub = service.dispatch("substitute", {"side": "home", "slot": 1, "incoming_player_id": "h9"})
    assert sub.ok
    assert store.state["diamond"]["lineup"]["home"]["slots"]["1"]["active_player_id"] == "h9"


def test_dispatch_undo_reverses_the_last_plate_appearance() -> None:
    store = _FakeStateStore(_baseball_state())
    service = _service(store)
    service.dispatch("record_plate_appearance", {
        "battingTeam": "visitor", "batterId": "b1", "pitcherId": "p1",
        "resultCode": "HR",
        "runnerOutcomes": [{"from": "batter", "to": "score", "playerId": "b1"}],
        "outsRecorded": 0, "hits": 1,
    })
    assert store.state["diamond"]["visitor_score"] == 1

    undone = service.dispatch("undo")
    assert undone.ok
    assert store.state["diamond"]["visitor_score"] == 0
    assert store.state["visitor_score"] == 0


def test_dispatch_suspend_then_resume_round_trips_status() -> None:
    store = _FakeStateStore(_baseball_state())
    service = _service(store)
    suspended = service.dispatch("suspend", {"reason": "rain"})
    assert suspended.ok
    assert store.state["status"] == "suspended"
    assert store.state["diamond"]["suspension"]["suspended"] is True

    resumed = service.dispatch("resume")
    assert resumed.ok
    assert store.state["status"] == "live"


def test_dispatch_is_idempotent_for_a_repeated_command_id() -> None:
    store = _FakeStateStore(_baseball_state())
    service = _service(store)
    payload = {
        "command_id": "cmd-1",
        "battingTeam": "visitor", "batterId": "b1", "pitcherId": "p1",
        "resultCode": "BB",
        "runnerOutcomes": [{"from": "batter", "to": "first", "playerId": "b1"}],
        "outsRecorded": 0,
    }
    first = service.dispatch("record_plate_appearance", payload)
    second = service.dispatch("record_plate_appearance", payload)
    assert first.ok and second.ok
    assert len(store.saved) == 1  # the duplicate never re-saved
