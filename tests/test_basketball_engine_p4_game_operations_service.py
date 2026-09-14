"""Basketball engine P4: hoops_game_operations_service.py -- the
"game_operations_service" boundary docs/BASKETBALL_ENGINE_SCOPING_PLAN.md
Sec.2 calls for, delivered here in P4 (mirroring how baseball deferred its
own diamond_game_operations_service.py to its P4). Exercises the
persistence/locking boundary itself (load/save/lock, duplicate-command
protection, generic ACTIONS dispatch) rather than re-testing the P1/P2
service logic those actions call into (already covered by their own test
files).
"""

from __future__ import annotations

import threading

from hoops_game_operations_service import HoopsGameOperationsService


class _FakeStateStore:
    def __init__(self, state: dict) -> None:
        self.state = state
        self.saved: list[dict] = []

    def load(self) -> dict:
        return self.state

    def save(self, state: dict) -> None:
        self.state = state
        self.saved.append(state)


def _service(store: _FakeStateStore) -> HoopsGameOperationsService:
    return HoopsGameOperationsService(
        load_state=store.load,
        save_state=store.save,
        transaction_lock=threading.Lock(),
    )


def _basketball_state(**overrides) -> dict:
    state = {
        "sport": "basketball",
        "status": "live",
        "country": "US",
        "region": None,
        "association": "NFHS",
        "broadcast_id": "b1",
        "home_score": 0,
        "visitor_score": 0,
    }
    state.update(overrides)
    return state


def test_initialize_hoops_rejects_football() -> None:
    store = _FakeStateStore({"sport": "Football"})
    result = _service(store).initialize_hoops()
    assert result.code == "NOT_A_HOOPS_SPORT"


def test_initialize_hoops_seeds_period_clock_and_timeouts_from_the_ruleset() -> None:
    store = _FakeStateStore(_basketball_state())
    result = _service(store).initialize_hoops()
    assert result.ok
    assert result.data["state"]["period"] == "1"
    assert result.data["state"]["clock_seconds"] == 480
    assert result.data["state"]["hoops"]["home_timeouts"] == 5
    assert store.state["period"] == "1"


def test_dispatch_unknown_action() -> None:
    store = _FakeStateStore(_basketball_state())
    result = _service(store).dispatch("not_a_real_action")
    assert result.code == "UNKNOWN_ACTION"


def test_dispatch_rejects_football() -> None:
    store = _FakeStateStore({"sport": "Football"})
    result = _service(store).dispatch("shot", {"team": "home", "made": True, "points": 2, "shooterId": "h1"})
    assert result.code == "NOT_A_HOOPS_SPORT"


def _initialized_store() -> _FakeStateStore:
    store = _FakeStateStore(_basketball_state())
    _service(store).initialize_hoops()
    store.saved.clear()  # so callers can assert on saves from their OWN actions only
    return store


def test_dispatch_shot_syncs_score_and_persists() -> None:
    store = _initialized_store()
    service = _service(store)
    result = service.dispatch("shot", {"team": "home", "made": True, "points": 2, "shooterId": "h1"})
    assert result.ok
    assert store.state["home_score"] == 2
    assert len(store.saved) == 1


def test_dispatch_set_starting_five_then_substitute() -> None:
    store = _initialized_store()
    service = _service(store)
    started = service.dispatch("set_starting_five", {"team": "home", "player_ids": ["h1", "h2", "h3", "h4", "h5"]})
    assert started.ok
    assert store.state["hoops"]["home_on_floor"] == ["h1", "h2", "h3", "h4", "h5"]

    subbed = service.dispatch("substitute", {"team": "home", "out_player_id": "h1", "in_player_id": "h6"})
    assert subbed.ok
    assert store.state["hoops"]["home_on_floor"] == ["h6", "h2", "h3", "h4", "h5"]


def test_dispatch_undo_reverses_the_last_shot() -> None:
    store = _initialized_store()
    service = _service(store)
    service.dispatch("shot", {"team": "home", "made": True, "points": 2, "shooterId": "h1"})
    assert store.state["home_score"] == 2

    undone = service.dispatch("undo")
    assert undone.ok
    assert store.state["home_score"] == 0


def test_dispatch_foul_five_times_then_correct_foul_keeps_bonus_right() -> None:
    # The whole-payload binding path (foul()'s "payload" parameter) PLUS
    # the by-name binding path (correct_foul()'s event_id/replacement_payload/
    # reason) in the same scenario -- confirms _bind_kwargs()'s special
    # case doesn't accidentally swallow correct_foul()'s extra arguments.
    store = _initialized_store()
    service = _service(store)
    fourth = None
    for i in range(4):
        result = service.dispatch("foul", {"team": "visitor", "playerId": "v1", "foulType": "personal"})
        fourth = result
    assert store.state["hoops"]["visitor_team_fouls"] == 4
    assert store.state["hoops"]["home_bonus"] == "NONE"

    fourth_event_id = fourth.data["event"]["event_id"]
    corrected = service.dispatch("correct_foul", {
        "event_id": fourth_event_id,
        "replacement_payload": {"team": "visitor", "playerId": "v4", "foulType": "personal"},
        "reason": "mis-attributed to v1",
    })
    assert corrected.ok
    assert store.state["hoops"]["visitor_team_fouls"] == 4
    assert store.state["hoops"]["player_fouls"]["v1"] == 3
    assert store.state["hoops"]["player_fouls"]["v4"] == 1


def test_dispatch_violation_ruling_timeout_and_set_value() -> None:
    # P5 addendum: these four actions were added after P4's own dispatch
    # wiring landed -- confirms they're reachable through the same
    # generic ACTIONS table, not just callable directly on the service.
    store = _initialized_store()
    service = _service(store)

    violation = service.dispatch("violation", {"team": "home", "violationType": "traveling", "possessionTo": "visitor"})
    assert violation.ok
    assert store.state["possession"] == "visitor"

    ruling = service.dispatch("ruling", {"scoreAdjustment": {"team": "home", "points": 2}})
    assert ruling.ok
    assert store.state["home_score"] == 2

    timeout = service.dispatch("timeout", {"team": "home"})
    assert timeout.ok
    assert store.state["hoops"]["home_timeouts"] == 4

    set_value = service.dispatch("set_value", {"field": "visitor_team_fouls", "value": 5})
    assert set_value.ok
    assert store.state["hoops"]["visitor_team_fouls"] == 5
    assert store.state["hoops"]["home_bonus"] == "DOUBLE"


def test_dispatch_confirm_game_end_sets_shared_status() -> None:
    store = _initialized_store()
    service = _service(store)
    result = service.dispatch("confirm_game_end", {"reason": "REGULATION"})
    assert result.ok
    assert store.state["status"] == "completed"
    assert store.state["hoops"]["official_end_reason"] == "REGULATION"


def test_dispatch_is_idempotent_for_a_repeated_command_id() -> None:
    store = _initialized_store()
    service = _service(store)
    payload = {"command_id": "cmd-1", "team": "home", "made": True, "points": 2, "shooterId": "h1"}
    first = service.dispatch("shot", payload)
    second = service.dispatch("shot", payload)
    assert first.ok and second.ok
    assert store.state["home_score"] == 2  # applied once, not twice
    assert len(store.saved) == 1  # the duplicate never re-saved
