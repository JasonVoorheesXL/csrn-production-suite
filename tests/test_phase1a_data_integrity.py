from __future__ import annotations

import copy
import threading
import time
from contextlib import nullcontext
from typing import Any, Mapping

from flask import Flask

from event_service import EventService
from game_operations_service import GameOperationsService
from live_command_service import LEDGER_FIELD
from routes.live_game_routes import (
    LiveGameRoutesDependencies,
    create_live_game_blueprint,
)
from routes.system_routes import SystemRoutesDependencies, create_system_blueprint
from rules_service import RulesService
from runtime_state_cache import (
    install_runtime_state_cache,
    invalidate_runtime_state_cache,
)
from state_read_cache import install_state_read_cache, invalidate_state_read_cache
from state_service import StateService


def base_state() -> dict[str, Any]:
    return {
        "broadcast_created": True,
        "broadcast_id": "B-PHASE1A",
        "status": "planned",
        "broadcast_phase": "pregame",
        "sport": "Football",
        "home_team": "Caledonia",
        "visitor_team": "Opponent",
        "home_school_id": "H",
        "visitor_school_id": "V",
        "home_identity": {},
        "visitor_identity": {},
        "home_score": 14,
        "visitor_score": 7,
        "possession": "home",
        "down": "1st",
        "distance": "10",
        "ball_spot": "LEFT 20",
        "quarter": "1",
        "clock_seconds": 720,
        "clock_running": False,
        "clock_visible": True,
        "home_direction": "right",
        "visitor_direction": "left",
        "game_data_authority": "broadcaster",
        "statistician_enabled": False,
        "next_play_number": 1,
        "state_revision": 500,
        "history": [],
        "events": [],
        "plays": [],
        "correction_log": [],
        "redo_stack": [],
        "graphics_queue": [],
        "player_graphic": {"visible": False},
    }


def default_state() -> dict[str, Any]:
    state = base_state()
    state.update(
        {
            "broadcast_created": False,
            "broadcast_id": "",
            "home_score": 0,
            "visitor_score": 0,
            "state_revision": 0,
        }
    )
    return state


class MemoryState:
    def __init__(self, state: Mapping[str, Any] | None = None) -> None:
        self.state = copy.deepcopy(dict(state or base_state()))
        self.saved: list[dict[str, Any]] = []

    def load(self) -> dict[str, Any]:
        return copy.deepcopy(self.state)

    def save(self, incoming: Mapping[str, Any]) -> dict[str, Any]:
        self.state = copy.deepcopy(dict(incoming))
        self.saved.append(copy.deepcopy(self.state))
        return copy.deepcopy(self.state)


def push_history(state: dict[str, Any]) -> None:
    state.setdefault("history", []).append(
        {key: copy.deepcopy(value) for key, value in state.items() if key != "history"}
    )


def score_service(
    store: MemoryState,
    *,
    lock: Any | None = None,
) -> GameOperationsService:
    return GameOperationsService(
        load_state=store.load,
        save_state=store.save,
        default_state=default_state,
        push_history=push_history,
        source_allowed=lambda _state, _source: True,
        locked_payload=lambda state: {"error": "CONTROL_SOURCE_LOCKED", "authority": state.get("game_data_authority", "broadcaster")},
        update_linked_status=lambda *args: None,
        load_config=lambda: {"obs": {"controlled_commands": False}},
        command_scorebug_visibility=lambda _visible: None,
        transaction_lock=lock or nullcontext(),
    )


def event_service(store: MemoryState) -> EventService:
    return EventService(
        load_state=store.load,
        save_state=store.save,
        public_state=lambda state: copy.deepcopy(dict(state)),
        push_history=push_history,
        update_linked_status=lambda *args: None,
        automation_player=lambda _roster_id, _player_id: (None, None),
        manual_player=lambda _data, _team_name: None,
        player_display=lambda _player: "",
        show_player_graphic=lambda *_args, **_kwargs: None,
        apply_penalty=lambda *_args, **_kwargs: {},
        spot_to_coord=lambda _value: 20,
        team_direction=lambda _state, _team: 1,
        normalize_state=lambda state: copy.deepcopy(dict(state)),
        default_player_graphic=lambda: {"visible": False},
        transaction_lock=threading.Lock(),
        now=lambda: 1_700_000_000.0,
    )


def rules_service(store: MemoryState, *, lock: Any | None = None) -> RulesService:
    return RulesService(
        load_state=store.load,
        save_state=store.save,
        push_history=push_history,
        source_allowed=lambda _state, source: source == "statistician",
        locked_payload=lambda state: {"error": "CONTROL_SOURCE_LOCKED", "authority": state.get("game_data_authority", "broadcaster")},
        resolve_player=lambda _state, _team, number: {"number": str(number or ""), "name": "", "resolved": False},
        show_player_graphic=lambda *_args, **_kwargs: None,
        transaction_lock=lock or threading.Lock(),
        now=lambda: 1_700_000_000.0,
    )


def route_client(state: Mapping[str, Any] | None = None):
    store = MemoryState(state)
    shared_lock = threading.Lock()
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="phase1a-route-test")
    app.register_blueprint(
        create_live_game_blueprint(
            LiveGameRoutesDependencies(
                require_auth=lambda view: view,
                get_game_operations_service=lambda: score_service(store, lock=shared_lock),
                get_event_service=lambda: event_service(store),
                get_rules_service=lambda: rules_service(store, lock=shared_lock),
                get_statistics_service=lambda: None,
                load_state=store.load,
            )
        )
    )
    return app.test_client(), store


def state_service_store(
    state: Mapping[str, Any] | None = None,
    *,
    snapshots: list[dict[str, Any]] | None = None,
) -> tuple[MemoryState, StateService]:
    store = MemoryState(state)
    service = StateService(
        load_raw=store.load,
        replace_raw=store.save,
        default_state=default_state,
        persist_linked_snapshot=snapshots.append if snapshots is not None else None,
    )
    return store, service


def save_via(service: StateService):
    def _save(state: Mapping[str, Any]) -> dict[str, Any]:
        return service.save(state).data["state"]

    return _save


def score_service_with_state_service(
    store: MemoryState,
    service: StateService,
    *,
    lock: Any | None = None,
) -> GameOperationsService:
    return GameOperationsService(
        load_state=store.load,
        save_state=save_via(service),
        default_state=default_state,
        push_history=push_history,
        source_allowed=lambda _state, _source: True,
        locked_payload=lambda state: {"error": "CONTROL_SOURCE_LOCKED", "authority": state.get("game_data_authority", "broadcaster")},
        update_linked_status=lambda *args: None,
        load_config=lambda: {"obs": {"controlled_commands": False}},
        command_scorebug_visibility=lambda _visible: None,
        transaction_lock=lock or nullcontext(),
    )


def event_service_with_state_service(
    store: MemoryState,
    service: StateService,
) -> EventService:
    return EventService(
        load_state=store.load,
        save_state=save_via(service),
        public_state=lambda state: copy.deepcopy(dict(state)),
        push_history=push_history,
        update_linked_status=lambda *args: None,
        automation_player=lambda _roster_id, _player_id: (None, None),
        manual_player=lambda _data, _team_name: None,
        player_display=lambda _player: "",
        show_player_graphic=lambda *_args, **_kwargs: None,
        apply_penalty=lambda *_args, **_kwargs: {},
        spot_to_coord=lambda _value: 20,
        team_direction=lambda _state, _team: 1,
        normalize_state=lambda state: copy.deepcopy(dict(state)),
        default_player_graphic=lambda: {"visible": False},
        transaction_lock=threading.Lock(),
        now=lambda: 1_700_000_000.0,
    )


def rules_service_with_state_service(
    store: MemoryState,
    service: StateService,
    *,
    lock: Any | None = None,
) -> RulesService:
    return RulesService(
        load_state=store.load,
        save_state=save_via(service),
        push_history=push_history,
        source_allowed=lambda _state, source: source == "statistician",
        locked_payload=lambda state: {"error": "CONTROL_SOURCE_LOCKED", "authority": state.get("game_data_authority", "broadcaster")},
        resolve_player=lambda _state, _team, number: {"number": str(number or ""), "name": "", "resolved": False},
        show_player_graphic=lambda *_args, **_kwargs: None,
        transaction_lock=lock or threading.Lock(),
        now=lambda: 1_700_000_000.0,
    )


def test_identical_state_save_does_not_advance_revision() -> None:
    store, service = state_service_store()
    result = service.save(store.load())
    assert result.data["state"]["state_revision"] == 500
    assert store.state["state_revision"] == 500


def test_metadata_only_secondary_save_does_not_advance_active_revision() -> None:
    store, service = state_service_store()
    state = store.load()
    state[LEDGER_FIELD] = {"metadata-only": {"status": "cached"}}
    result = service.save(state)
    assert result.data["state"]["state_revision"] == 500
    assert store.state["state_revision"] == 500


def test_revision_never_regresses() -> None:
    store, service = state_service_store()
    stale = store.load()
    stale["state_revision"] = 499
    result = service.save(stale)
    assert result.data["state"]["state_revision"] == 500
    assert store.state["state_revision"] == 500


def test_score_command_advances_revision_once() -> None:
    store, persistence = state_service_store()
    service = score_service_with_state_service(store, persistence)
    result = service.score({"command_id": "score-once", "team": "home", "delta": -1})
    assert result.data["state"]["state_revision"] == 501
    assert store.state["state_revision"] == 501
    assert [saved["state_revision"] for saved in store.saved] == [501]


def test_event_command_advances_revision_once() -> None:
    store, persistence = state_service_store()
    service = event_service_with_state_service(store, persistence)
    result = service.trigger({"command_id": "event-once", "team": "home", "event": "FIRST_DOWN"})
    assert result.data["state"]["state_revision"] == 501
    assert store.state["state_revision"] == 501
    assert [saved["state_revision"] for saved in store.saved] == [501]


def test_rules_play_advances_revision_once() -> None:
    state = base_state()
    state["game_data_authority"] = "statistician"
    store, persistence = state_service_store(state)
    service = rules_service_with_state_service(store, persistence)
    result = service.play({"command_id": "rules-once", "team": "home", "play_type": "run", "end_spot": "LEFT 24"})
    assert result.data["state"]["state_revision"] == 501
    assert store.state["state_revision"] == 501
    assert [saved["state_revision"] for saved in store.saved] == [501]


def test_duplicate_score_command_does_not_advance_revision() -> None:
    store, persistence = state_service_store()
    service = score_service_with_state_service(store, persistence)
    service.score({"command_id": "score-dup", "team": "home", "delta": -1})
    result = service.score({"command_id": "score-dup", "team": "home", "delta": -1})
    assert result.data["state"]["state_revision"] == 501
    assert store.state["state_revision"] == 501
    assert len(store.saved) == 1


def test_duplicate_event_command_does_not_advance_revision() -> None:
    store, persistence = state_service_store()
    service = event_service_with_state_service(store, persistence)
    service.trigger({"command_id": "event-dup", "team": "home", "event": "FIRST_DOWN"})
    result = service.trigger({"command_id": "event-dup", "team": "home", "event": "FIRST_DOWN"})
    assert result.data["state"]["state_revision"] == 501
    assert store.state["state_revision"] == 501
    assert len(store.saved) == 1


def test_duplicate_rules_play_command_does_not_advance_revision() -> None:
    state = base_state()
    state["game_data_authority"] = "statistician"
    store, persistence = state_service_store(state)
    service = rules_service_with_state_service(store, persistence)
    payload = {"command_id": "rules-dup", "team": "home", "play_type": "run", "end_spot": "LEFT 24"}
    service.play(payload)
    result = service.play(payload)
    assert result.data["state"]["state_revision"] == 501
    assert store.state["state_revision"] == 501
    assert len(store.saved) == 1


def test_rejected_command_does_not_advance_revision() -> None:
    store, persistence = state_service_store()
    service = score_service_with_state_service(store, persistence)
    result = service.score({"command_id": "score-rejected", "team": "home", "delta": 4})
    assert result.code == "INVALID_SCORE_REQUEST"
    assert store.state["state_revision"] == 500
    assert store.saved == []


def test_command_internal_ledger_write_does_not_double_increment_revision() -> None:
    store, persistence = state_service_store()
    service = score_service_with_state_service(store, persistence)
    service.score({"command_id": "ledger-once", "team": "home", "delta": -1})
    assert store.state[LEDGER_FIELD]["ledger-once"]["resulting_revision"] == 501
    assert store.state["state_revision"] == 501
    assert len(store.saved) == 1


def test_history_write_does_not_double_increment_revision() -> None:
    store, persistence = state_service_store()
    service = event_service_with_state_service(store, persistence)
    service.trigger({"command_id": "history-once", "team": "home", "event": "FIRST_DOWN"})
    assert len(store.state["history"]) == 1
    assert store.state["state_revision"] == 501
    assert len(store.saved) == 1


def test_direct_score_audit_record_shares_command_revision() -> None:
    store, persistence = state_service_store()
    service = score_service_with_state_service(store, persistence)
    service.score({"command_id": "audit-revision", "client_id": "operator-1", "team": "home", "delta": -1})
    entry = store.state["correction_log"][-1]
    assert entry["state_revision"] == 501
    assert store.state[LEDGER_FIELD]["audit-revision"]["resulting_revision"] == 501
    assert store.state["state_revision"] == 501


def test_linked_snapshot_preserves_source_revision() -> None:
    snapshots: list[dict[str, Any]] = []
    store, service = state_service_store(snapshots=snapshots)
    result = service.save(store.load())
    assert result.data["state"]["state_revision"] == 500
    assert store.state["state_revision"] == 500
    assert snapshots[-1]["state_revision"] == 500


def test_cache_immediately_returns_committed_revision() -> None:
    invalidate_state_read_cache()
    invalidate_runtime_state_cache()
    state = {"state_revision": 500}
    app = Flask(__name__)
    app.register_blueprint(
        create_system_blueprint(
            SystemRoutesDependencies(
                require_auth=lambda view: view,
                get_configuration_service=lambda: None,
                diagnostic_status=lambda: {},
                load_state=lambda: copy.deepcopy(state),
                load_runtime_state=lambda: copy.deepcopy(state),
                public_state=lambda incoming: copy.deepcopy(dict(incoming)),
                runtime_state=lambda incoming: copy.deepcopy(dict(incoming)),
                readiness_payload=lambda: {},
                load_build_journal=lambda: [],
            )
        )
    )
    install_state_read_cache(app)
    install_runtime_state_cache(app)
    client = app.test_client()
    assert client.get("/api/state").get_json()["state_revision"] == 500
    state["state_revision"] = 501
    invalidate_state_read_cache()
    invalidate_runtime_state_cache()
    assert client.get("/api/state").get_json()["state_revision"] == 501
    assert client.get("/api/runtime-state").get_json()["state_revision"] == 501


def test_revision_sequence_matches_phase1a1_scenario() -> None:
    store, persistence = state_service_store()
    service = event_service_with_state_service(store, persistence)
    first = service.trigger({"command_id": "td-500", "team": "home", "event": "TD"})
    duplicate = service.trigger({"command_id": "td-500", "team": "home", "event": "TD"})
    store.state["special_game_phase"] = ""
    distinct = service.trigger({"command_id": "td-501", "team": "home", "event": "TD"})
    identical = persistence.save(store.load())
    snapshot_state = store.load()
    snapshot_state[LEDGER_FIELD]["secondary"] = {"status": "metadata"}
    secondary = persistence.save(snapshot_state)
    assert first.data["state"]["state_revision"] == 501
    assert duplicate.data["state"]["state_revision"] == 501
    assert distinct.data["state"]["state_revision"] == 502
    assert identical.data["state"]["state_revision"] == 502
    assert secondary.data["state"]["state_revision"] == 502


def test_set_values_advances_revision_once() -> None:
    store, persistence = state_service_store()
    service = score_service_with_state_service(store, persistence)
    result = service.set_values({"quarter": "2", "possession": "visitor"})
    assert result.data["state"]["state_revision"] == 501
    assert store.state["state_revision"] == 501
    assert [saved["state_revision"] for saved in store.saved] == [501]


def test_toggle_scorebug_advances_revision_once() -> None:
    store, persistence = state_service_store()
    service = score_service_with_state_service(store, persistence)
    result = service.toggle_scorebug()
    assert result.data["state"]["state_revision"] == 501
    assert store.state["state_revision"] == 501


def test_toggle_halftime_advances_revision_once() -> None:
    state = base_state()
    state["broadcast_phase"] = "live"
    store, persistence = state_service_store(state)
    service = score_service_with_state_service(store, persistence)
    result = service.toggle_halftime()
    assert result.data["state"]["state_revision"] == 501
    assert store.state["state_revision"] == 501


def test_end_game_advances_revision_once() -> None:
    store, persistence = state_service_store()
    service = score_service_with_state_service(store, persistence)
    result = service.end_game()
    assert result.data["state"]["state_revision"] == 501
    assert store.state["state_revision"] == 501


def test_reset_data_advances_from_current_revision() -> None:
    store, persistence = state_service_store()
    service = score_service_with_state_service(store, persistence)
    result = service.reset_data()
    assert result.data["state"]["state_revision"] == 501
    assert store.state["state_revision"] == 501


def test_new_broadcast_advances_from_current_revision() -> None:
    store, persistence = state_service_store()
    service = score_service_with_state_service(store, persistence)
    result = service.new_broadcast()
    assert result.data["state"]["state_revision"] == 501
    assert store.state["state_revision"] == 501


def test_control_source_advances_revision_once() -> None:
    store, persistence = state_service_store()
    service = event_service_with_state_service(store, persistence)
    result = service.set_control_source("statistician")
    assert result.data["state"]["state_revision"] == 501
    assert store.state["state_revision"] == 501


def test_quick_correction_advances_revision_once() -> None:
    state = base_state()
    state["game_data_authority"] = "statistician"
    store, persistence = state_service_store(state)
    service = event_service_with_state_service(store, persistence)
    result = service.quick_correction({"source": "statistician", "down": "2nd"})
    assert result.data["state"]["state_revision"] == 501
    assert store.state["state_revision"] == 501


def test_undo_restore_advance_revision_from_current_state() -> None:
    store, persistence = state_service_store()
    service = event_service_with_state_service(store, persistence)
    service.trigger({"command_id": "undo-restore-source", "team": "home", "event": "FIRST_DOWN"})
    undo = service.undo()
    restore = service.restore()
    assert undo.data["state"]["state_revision"] == 502
    assert restore.data["state"]["state_revision"] == 503
    assert store.state["state_revision"] == 503


def test_clock_control_advances_revision_once() -> None:
    store, persistence = state_service_store()
    service = rules_service_with_state_service(store, persistence)
    result = service.clock_control({"action": "set", "seconds": 600})
    assert result.data["state"]["state_revision"] == 501
    assert store.state["state_revision"] == 501


def test_field_direction_advances_revision_once() -> None:
    store, persistence = state_service_store()
    service = rules_service_with_state_service(store, persistence)
    result = service.field_direction({"team": "home", "direction": "left"})
    assert result.data["state"]["state_revision"] == 501
    assert store.state["state_revision"] == 501


def test_score_command_id_idempotent_under_duplicate_post() -> None:
    store = MemoryState()
    service = score_service(store)
    payload = {"command_id": "score-1", "team": "home", "delta": -1}
    first = service.score(payload)
    second = service.score(payload)
    assert first.ok and second.ok
    assert store.state["home_score"] == 13
    assert len(store.saved) == 1


def test_touchdown_command_id_idempotent_under_duplicate_post() -> None:
    store = MemoryState()
    service = event_service(store)
    payload = {"command_id": "td-1", "team": "home", "event": "TD"}
    first = service.trigger(payload)
    second = service.trigger(payload)
    assert first.ok and second.ok
    assert store.state["home_score"] == 20
    assert len(store.state["events"]) == 1


def test_rules_play_command_id_idempotent_under_duplicate_post() -> None:
    state = base_state()
    state["game_data_authority"] = "statistician"
    store = MemoryState(state)
    service = rules_service(store)
    payload = {
        "command_id": "play-1",
        "team": "home",
        "play_type": "run",
        "start_spot": "LEFT 20",
        "end_spot": "LEFT 25",
    }
    service.play(payload)
    service.play(payload)
    assert len(store.state["plays"]) == 1


def test_duplicate_command_returns_original_state_revision() -> None:
    store = MemoryState()
    service = score_service(store)
    payload = {"command_id": "score-rev", "team": "home", "delta": -1}
    first = service.score(payload)
    second = service.score(payload)
    assert first.data["state"]["state_revision"] == 501
    assert second.data["state"]["state_revision"] == 501


def test_duplicate_command_does_not_advance_state_revision() -> None:
    store = MemoryState()
    service = score_service(store)
    payload = {"command_id": "score-no-advance", "team": "home", "delta": -1}
    service.score(payload)
    service.score(payload)
    assert store.state["state_revision"] == 501


def test_duplicate_touchdown_does_not_append_second_event() -> None:
    store = MemoryState()
    service = event_service(store)
    payload = {"command_id": "td-event", "team": "home", "event": "TD"}
    service.trigger(payload)
    service.trigger(payload)
    assert [event["event"] for event in store.state["events"]] == ["TD"]


def test_duplicate_rules_play_does_not_append_second_play() -> None:
    state = base_state()
    state["game_data_authority"] = "statistician"
    store = MemoryState(state)
    service = rules_service(store)
    payload = {"command_id": "run-event", "team": "home", "play_type": "run", "end_spot": "LEFT 21"}
    service.play(payload)
    service.play(payload)
    assert len(store.state["plays"]) == 1


def test_lost_response_retry_with_same_command_id_does_not_duplicate() -> None:
    store = MemoryState()
    service = event_service(store)
    first = service.trigger({"command_id": "ABC", "team": "home", "event": "TD"})
    retry = service.trigger({"command_id": "ABC", "team": "home", "event": "TD"})
    store.state["special_game_phase"] = ""
    distinct = service.trigger({"command_id": "DEF", "team": "home", "event": "TD"})
    assert first.data["state"]["home_score"] == 20
    assert retry.data["state"]["home_score"] == 20
    assert retry.data["state"]["state_revision"] == 501
    assert distinct.data["state"]["home_score"] == 26
    assert distinct.data["state"]["state_revision"] == 502
    assert len(store.state["events"]) == 2


def test_state_revision_increments_for_direct_score() -> None:
    store = MemoryState()
    service = score_service(store)
    service.score({"command_id": "score-inc", "team": "home", "delta": -1})
    assert store.state["state_revision"] == 501


def test_state_revision_increments_for_event() -> None:
    store = MemoryState()
    service = event_service(store)
    service.trigger({"command_id": "event-inc", "team": "home", "event": "FIRST_DOWN"})
    assert store.state["state_revision"] == 501


def test_state_revision_increments_for_rules_play() -> None:
    state = base_state()
    state["game_data_authority"] = "statistician"
    store = MemoryState(state)
    service = rules_service(store)
    service.play({"command_id": "rules-inc", "team": "home", "play_type": "run", "end_spot": "LEFT 24"})
    assert store.state["state_revision"] == 501


def test_runtime_state_returns_state_revision() -> None:
    service = StateService(
        load_raw=lambda: base_state(),
        replace_raw=lambda state: copy.deepcopy(dict(state)),
        default_state=default_state,
    )
    runtime = service.runtime_view(base_state()).data["state"]
    assert runtime["state_revision"] == 500
    assert runtime["revision"] == 500


def test_full_state_returns_state_revision() -> None:
    service = StateService(
        load_raw=lambda: base_state(),
        replace_raw=lambda state: copy.deepcopy(dict(state)),
        default_state=default_state,
    )
    public = service.public(service.load().data["state"]).data["state"]
    assert public["state_revision"] == 500
    assert LEDGER_FIELD not in public


def test_rejected_command_does_not_increment_revision() -> None:
    store = MemoryState()
    service = score_service(store)
    result = service.score({"command_id": "bad", "team": "home", "delta": 4})
    assert result.code == "INVALID_SCORE_REQUEST"
    assert store.state["state_revision"] == 500
    assert store.saved == []


def test_two_distinct_command_ids_are_two_distinct_commands() -> None:
    store = MemoryState()
    service = score_service(store)
    service.score({"command_id": "score-A", "team": "home", "delta": -1})
    service.score({"command_id": "score-B", "team": "home", "delta": -1})
    assert store.state["home_score"] == 12
    assert store.state["state_revision"] == 502


def test_existing_state_without_revision_loads_safely() -> None:
    legacy = base_state()
    legacy.pop("state_revision", None)
    service = StateService(
        load_raw=lambda: legacy,
        replace_raw=lambda state: copy.deepcopy(dict(state)),
        default_state=default_state,
    )
    state = service.load().data["state"]
    assert state["state_revision"] == 0
    assert state[LEDGER_FIELD] == {}


def test_command_ledger_is_bounded() -> None:
    store = MemoryState()
    service = score_service(store)
    for index in range(205):
        service.score({"command_id": f"cmd-{index}", "team": "home", "delta": 1})
    assert len(store.state[LEDGER_FIELD]) == 200
    assert "cmd-0" not in store.state[LEDGER_FIELD]
    assert "cmd-204" in store.state[LEDGER_FIELD]


def test_direct_score_adjustment_is_auditable() -> None:
    store = MemoryState()
    service = score_service(store)
    service.score({"command_id": "score-audit", "client_id": "operator-1", "team": "home", "delta": -1})
    entry = store.state["correction_log"][-1]
    assert entry["type"] == "direct_score_adjustment"
    assert entry["old_score"] == 14
    assert entry["new_score"] == 13
    assert entry["command_id"] == "score-audit"
    assert entry["state_revision"] == 501


def test_cache_does_not_return_pre_mutation_revision_after_commit() -> None:
    invalidate_state_read_cache()
    invalidate_runtime_state_cache()
    state = {"state_revision": 1}
    app = Flask(__name__)
    app.register_blueprint(
        create_system_blueprint(
            SystemRoutesDependencies(
                require_auth=lambda view: view,
                get_configuration_service=lambda: None,
                diagnostic_status=lambda: {},
                load_state=lambda: copy.deepcopy(state),
                load_runtime_state=lambda: copy.deepcopy(state),
                public_state=lambda incoming: copy.deepcopy(dict(incoming)),
                runtime_state=lambda incoming: copy.deepcopy(dict(incoming)),
                readiness_payload=lambda: {},
                load_build_journal=lambda: [],
            )
        )
    )
    install_state_read_cache(app)
    install_runtime_state_cache(app)
    client = app.test_client()
    assert client.get("/api/state").get_json()["state_revision"] == 1
    assert client.get("/api/runtime-state").get_json()["state_revision"] == 1
    state["state_revision"] = 2
    invalidate_state_read_cache()
    invalidate_runtime_state_cache()
    assert client.get("/api/state").get_json()["state_revision"] == 2
    assert client.get("/api/runtime-state").get_json()["state_revision"] == 2


def test_two_simultaneous_same_command_id_result_in_one_mutation() -> None:
    store = MemoryState()
    service = score_service(store, lock=threading.Lock())
    results: list[int] = []

    def worker() -> None:
        result = service.score({"command_id": "same-concurrent", "team": "home", "delta": -1})
        results.append(result.data["state"]["state_revision"])

    threads = [threading.Thread(target=worker), threading.Thread(target=worker)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert store.state["home_score"] == 13
    assert store.state["state_revision"] == 501
    assert results == [501, 501]


def test_two_simultaneous_distinct_command_ids_are_ordered() -> None:
    store = MemoryState()
    service = score_service(store, lock=threading.Lock())

    def worker(command_id: str) -> None:
        service.score({"command_id": command_id, "team": "home", "delta": -1})

    threads = [
        threading.Thread(target=worker, args=("distinct-A",)),
        threading.Thread(target=worker, args=("distinct-B",)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert store.state["home_score"] == 12
    assert store.state["state_revision"] == 502


def test_score_route_duplicate_command_returns_original_result() -> None:
    client, store = route_client()
    payload = {"command_id": "route-score", "team": "home", "delta": -1}
    first = client.post("/api/score", json=payload)
    second = client.post("/api/score", json=payload)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.get_json()["state_revision"] == 501
    assert second.get_json()["state_revision"] == 501
    assert store.state["home_score"] == 13
    assert store.state["state_revision"] == 501
    assert len(store.state["correction_log"]) == 1


def test_event_route_duplicate_command_returns_original_result() -> None:
    client, store = route_client()
    payload = {"command_id": "route-td", "team": "home", "event": "TD"}
    first = client.post("/api/event-trigger", json=payload)
    second = client.post("/api/event-trigger", json=payload)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.get_json()["state_revision"] == 501
    assert second.get_json()["state_revision"] == 501
    assert store.state["home_score"] == 20
    assert len(store.state["events"]) == 1
    assert len(store.state["plays"]) == 1


def test_rules_play_route_duplicate_command_returns_original_result() -> None:
    state = base_state()
    state["game_data_authority"] = "statistician"
    client, store = route_client(state)
    payload = {
        "command_id": "route-play",
        "team": "home",
        "play_type": "run",
        "start_spot": "LEFT 20",
        "end_spot": "LEFT 25",
    }
    first = client.post("/api/rules-play", json=payload)
    second = client.post("/api/rules-play", json=payload)
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.get_json()["state_revision"] == 501
    assert second.get_json()["state_revision"] == 501
    assert len(store.state["events"]) == 1
    assert len(store.state["plays"]) == 1


def test_score_route_concurrent_same_command_id_mutates_once() -> None:
    client, store = route_client()
    results: list[int] = []

    def worker() -> None:
        response = client.post(
            "/api/score",
            json={"command_id": "route-concurrent", "team": "home", "delta": -1},
        )
        results.append(response.get_json()["state_revision"])

    threads = [threading.Thread(target=worker), threading.Thread(target=worker)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(results) == [501, 501]
    assert store.state["home_score"] == 13
    assert store.state["state_revision"] == 501

def test_async_linked_snapshot_does_not_block_primary_state_commit() -> None:
    started = threading.Event()
    release = threading.Event()
    snapshots: list[dict[str, Any]] = []

    def persist(snapshot: dict[str, Any]) -> None:
        started.set()
        release.wait(timeout=2)
        snapshots.append(copy.deepcopy(snapshot))

    store = MemoryState()
    service = StateService(
        load_raw=store.load,
        replace_raw=store.save,
        default_state=default_state,
        persist_linked_snapshot=persist,
        async_linked_snapshot=True,
    )
    before = time.perf_counter()
    result = service.save(store.load())
    elapsed = time.perf_counter() - before

    assert result.data["state"]["state_revision"] == 500
    assert elapsed < 0.5
    assert started.wait(timeout=1)
    assert snapshots == []
    release.set()
    deadline = time.time() + 2
    while not snapshots and time.time() < deadline:
        time.sleep(0.01)
    assert snapshots[-1]["state_revision"] == 500


def test_sponsor_media_range_parser_supports_browser_range_requests() -> None:
    from routes.asset_routes import _parse_byte_range

    assert _parse_byte_range("bytes=0-99", 1000) == (0, 99)
    assert _parse_byte_range("bytes=500-", 1000) == (500, 999)
    assert _parse_byte_range("bytes=-100", 1000) == (900, 999)
    assert _parse_byte_range("bytes=1000-", 1000) is None



def test_expected_media_disconnects_are_classified_as_normal_browser_cancellation() -> None:
    from routes.asset_routes import _is_expected_media_disconnect

    assert _is_expected_media_disconnect(ConnectionAbortedError(10053, "aborted"))
    assert _is_expected_media_disconnect(ConnectionResetError(10054, "reset"))
    assert _is_expected_media_disconnect(BrokenPipeError(32, "broken pipe"))
    assert not _is_expected_media_disconnect(RuntimeError("unexpected media failure"))


def test_managed_video_and_audio_assets_use_isolated_media_plane() -> None:
    from routes.asset_routes import _is_isolated_media_asset

    for filename in ("highlight.mp4", "highlight.webm", "bed.mp3", "stinger.wav"):
        assert _is_isolated_media_asset(filename)
    for filename in ("logo.png", "headshot.jpg", "graphic.webp", "document.pdf"):
        assert not _is_isolated_media_asset(filename)


def test_committed_state_cache_avoids_reopening_raw_state_between_commits() -> None:
    raw = base_state()
    loads = 0
    replacements = 0

    def load_raw() -> dict[str, Any]:
        nonlocal loads
        loads += 1
        return copy.deepcopy(raw)

    def replace_raw(incoming: Mapping[str, Any]) -> dict[str, Any]:
        nonlocal replacements, raw
        replacements += 1
        raw = copy.deepcopy(dict(incoming))
        return copy.deepcopy(raw)

    service = StateService(
        load_raw=load_raw,
        replace_raw=replace_raw,
        default_state=default_state,
        cache_committed_state=True,
    )

    first = service.load().data["state"]
    second = service.load().data["state"]
    assert first["state_revision"] == 500
    assert second["state_revision"] == 500
    assert loads == 1

    changed = copy.deepcopy(second)
    changed["home_score"] = 15
    changed["state_revision"] = 501
    saved = service.save(changed).data["state"]
    assert saved["state_revision"] == 501
    assert replacements == 1
    assert loads == 1

    after = service.load().data["state"]
    assert after["home_score"] == 15
    assert after["state_revision"] == 501
    assert loads == 1


def test_uncertain_penalty_blocks_next_play_and_labels_commit_action() -> None:
    from pathlib import Path

    source = (Path(__file__).resolve().parents[1] / "templates" / "index.html").read_text(encoding="utf-8")
    assert "Previous ${action} is still resolving — wait for confirmation before entering the next play." in source
    assert "Connection delayed — penalty status is uncertain. Do not enter the next play yet." in source
    assert "async function submitPlayEntry(){if(blockForPriorUnresolvedCommand('rules-play'))return;" in source
    assert "COMMITTED · ${command.action} · rev" in source
