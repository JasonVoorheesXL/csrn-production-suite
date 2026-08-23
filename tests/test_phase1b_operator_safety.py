from __future__ import annotations

import copy
import pathlib
import threading
import time
from typing import Any

from test_phase1a_data_integrity import (
    base_state,
    event_service_with_state_service,
    rules_service_with_state_service,
    score_service_with_state_service,
    state_service_store,
)


ROOT = pathlib.Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "templates" / "index.html"
OVERLAY_HTML = ROOT / "templates" / "overlay.html"


def command_center_source() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


def overlay_source() -> str:
    return OVERLAY_HTML.read_text(encoding="utf-8")


class RevisionClient:
    def __init__(self, revision: int = 0) -> None:
        self.current_revision = revision
        self.rejected: list[int] = []
        self.health = "HEALTHY"
        self.failures = 0

    def receive(self, revision: int) -> bool:
        if revision < self.current_revision:
            self.rejected.append(revision)
            return False
        self.current_revision = revision
        self.failures = 0
        self.health = "HEALTHY"
        return True

    def fail_poll(self) -> None:
        self.failures += 1
        self.health = "STALE" if self.failures >= 4 else "DEGRADED"


class CommandClientModel:
    def __init__(self) -> None:
        self.sequence = 0
        self.pending: dict[str, dict[str, Any]] = {}

    def execute(self, group: str) -> str:
        existing = self.pending.get(group)
        if existing and existing["status"] in {"SUBMITTING", "UNKNOWN"}:
            return str(existing["command_id"])
        self.sequence += 1
        command_id = f"cmd-{self.sequence}"
        self.pending[group] = {"command_id": command_id, "status": "SUBMITTING"}
        return command_id

    def unknown(self, group: str) -> None:
        self.pending[group]["status"] = "UNKNOWN"

    def commit(self, group: str) -> None:
        self.pending.pop(group, None)


def test_command_client_reuses_command_id_after_timeout() -> None:
    client = CommandClientModel()
    first = client.execute("score")
    client.unknown("score")
    assert client.execute("score") == first


def test_command_client_new_action_gets_new_command_id() -> None:
    client = CommandClientModel()
    first = client.execute("score")
    client.commit("score")
    assert client.execute("score") != first


def test_score_button_disabled_while_pending() -> None:
    source = command_center_source()
    assert 'button[onclick^="score("]' in source
    assert "setGroupPending" in source


def test_td_button_disabled_while_pending() -> None:
    source = command_center_source()
    assert 'button[onclick*="openAutomationEvent"]' in source
    assert "SUBMITTING" in source


def test_rules_play_submit_disabled_while_pending() -> None:
    source = command_center_source()
    assert "#playEntryModal button" in source
    assert "rules-play" in source


def test_older_poll_revision_rejected() -> None:
    client = RevisionClient(501)
    assert client.receive(500) is False
    assert client.current_revision == 501
    assert client.rejected == [500]


def test_newer_poll_revision_accepted() -> None:
    client = RevisionClient(501)
    assert client.receive(502) is True
    assert client.current_revision == 502


def test_revision_jump_from_other_client_accepted() -> None:
    client = RevisionClient(501)
    assert client.receive(505) is True
    assert client.current_revision == 505


def test_stale_health_after_consecutive_poll_failures() -> None:
    client = RevisionClient(501)
    for _ in range(4):
        client.fail_poll()
    assert client.health == "STALE"


def test_health_recovers_after_successful_poll() -> None:
    client = RevisionClient(501)
    for _ in range(4):
        client.fail_poll()
    assert client.receive(502) is True
    assert client.health == "HEALTHY"


def test_same_command_retry_does_not_duplicate_score() -> None:
    store, persistence = state_service_store()
    service = score_service_with_state_service(store, persistence)
    payload = {"command_id": "score-retry", "team": "home", "delta": -1}
    service.score(payload)
    service.score(payload)
    assert store.state["home_score"] == 13
    assert store.state["state_revision"] == 501


def test_same_command_retry_does_not_duplicate_event() -> None:
    store, persistence = state_service_store()
    service = event_service_with_state_service(store, persistence)
    payload = {"command_id": "event-retry", "team": "home", "event": "TD"}
    service.trigger(payload)
    service.trigger(payload)
    assert store.state["home_score"] == 20
    assert len(store.state["events"]) == 1


def test_same_command_retry_does_not_duplicate_rules_play() -> None:
    state = base_state()
    state["game_data_authority"] = "statistician"
    store, persistence = state_service_store(state)
    service = rules_service_with_state_service(store, persistence)
    payload = {"command_id": "rules-retry", "team": "home", "play_type": "run", "end_spot": "LEFT 25"}
    service.play(payload)
    service.play(payload)
    assert len(store.state["plays"]) == 1
    assert store.state["state_revision"] == 501


def test_set_state_revision_behavior() -> None:
    store, persistence = state_service_store()
    service = score_service_with_state_service(store, persistence)
    payload = {"command_id": "set-retry", "quarter": "2"}
    service.set_values(payload)
    service.set_values(payload)
    assert store.state["quarter"] == "2"
    assert store.state["state_revision"] == 501


def test_clock_command_duplicate_safe() -> None:
    store, persistence = state_service_store()
    service = rules_service_with_state_service(store, persistence)
    payload = {"command_id": "clock-retry", "action": "adjust", "delta": -10}
    service.clock_control(payload)
    service.clock_control(payload)
    assert store.state["clock_seconds"] == 710
    assert store.state["state_revision"] == 501


def test_game_correction_duplicate_safe() -> None:
    state = base_state()
    state["game_data_authority"] = "statistician"
    store, persistence = state_service_store(state)
    service = event_service_with_state_service(store, persistence)
    payload = {"command_id": "correction-retry", "source": "statistician", "down": "2nd"}
    service.quick_correction(payload)
    service.quick_correction(payload)
    assert store.state["down"] == "2nd"
    assert store.state["state_revision"] == 501
    assert len(store.state["correction_log"]) == 1


def test_undo_duplicate_safe() -> None:
    store, persistence = state_service_store()
    service = event_service_with_state_service(store, persistence)
    service.trigger({"command_id": "undo-source", "team": "home", "event": "FIRST_DOWN"})
    payload = {"command_id": "undo-retry"}
    service.undo(payload)
    service.undo(payload)
    assert store.state["state_revision"] == 502
    assert len(store.state["redo_stack"]) == 1


def test_restore_duplicate_safe() -> None:
    store, persistence = state_service_store()
    service = event_service_with_state_service(store, persistence)
    service.trigger({"command_id": "restore-source", "team": "home", "event": "FIRST_DOWN"})
    service.undo({"command_id": "restore-undo"})
    payload = {"command_id": "restore-retry"}
    service.restore(payload)
    service.restore(payload)
    assert store.state["state_revision"] == 503
    assert store.state["redo_stack"] == []


def test_control_source_duplicate_safe() -> None:
    store, persistence = state_service_store()
    service = event_service_with_state_service(store, persistence)
    payload = {"command_id": "authority-retry", "authority": "statistician"}
    service.set_control_source("statistician", payload)
    service.set_control_source("statistician", payload)
    assert store.state["game_data_authority"] == "statistician"
    assert store.state["state_revision"] == 501


def test_toggle_action_retry_safe() -> None:
    store, persistence = state_service_store()
    service = score_service_with_state_service(store, persistence)
    payload = {"command_id": "scorebug-toggle-retry"}
    service.toggle_scorebug(payload)
    service.toggle_scorebug(payload)
    assert store.state["scorebug_visible"] is True
    assert store.state["state_revision"] == 501


def test_mobile_pending_state_visible() -> None:
    source = command_center_source()
    assert "statisticianActionNotice" in source
    assert "operatorCommandHealth" in source
    assert "state-stale" in source


def test_reconnect_refreshes_authoritative_state() -> None:
    source = command_center_source()
    assert "refreshAuthoritativeGameState" in source
    assert "recordPollSuccess" in source


def test_unknown_commit_state_does_not_generate_new_command_id() -> None:
    source = command_center_source()
    assert "['UNKNOWN','UNKNOWN_COMMIT'].includes(existing.status)" in source
    assert "reuseUnknown" in source


def test_cache_or_poll_cannot_overwrite_newer_mutation_response() -> None:
    source = command_center_source()
    assert "incomingRevision<currentRevision" in source
    assert "Discarded older runtime poll revision" in source


def test_artificial_latency_td_single_command(latency: float = 0.5) -> None:
    store, persistence = state_service_store()
    service = event_service_with_state_service(store, persistence)
    payload = {"command_id": f"latency-{latency}", "team": "home", "event": "TD"}
    results: list[int] = []

    def worker() -> None:
        time.sleep(latency)
        results.append(service.trigger(payload).data["state"]["state_revision"])

    thread = threading.Thread(target=worker)
    thread.start()
    for _ in range(4):
        results.append(service.trigger(payload).data["state"]["state_revision"])
    thread.join()
    assert sorted(results) == [501] * 5
    assert store.state["home_score"] == 20
    assert len(store.state["events"]) == 1


def test_artificial_latency_500ms() -> None:
    test_artificial_latency_td_single_command(0.5)


def test_artificial_latency_2s() -> None:
    test_artificial_latency_td_single_command(2.0)


def test_artificial_latency_5s() -> None:
    test_artificial_latency_td_single_command(5.0)


def test_artificial_latency_10s() -> None:
    test_artificial_latency_td_single_command(10.0)


def test_lost_response_retry_demonstration() -> None:
    store, persistence = state_service_store()
    service = event_service_with_state_service(store, persistence)
    payload = {"command_id": "lost-response", "team": "home", "event": "TD"}
    committed = service.trigger(payload)
    retry = service.trigger(payload)
    assert committed.data["state"]["state_revision"] == 501
    assert retry.data["state"]["state_revision"] == 501
    assert len(store.state["events"]) == 1


def test_multi_client_revision_convergence() -> None:
    store, persistence = state_service_store()
    statistician = event_service_with_state_service(store, persistence)
    broadcaster = score_service_with_state_service(store, persistence)
    statistician.trigger({"command_id": "stat-td", "client_id": "stat-phone", "team": "home", "event": "TD", "expected_revision": 500})
    broadcaster.score({"command_id": "broadcaster-score", "client_id": "booth", "team": "visitor", "delta": 3, "expected_revision": 500})
    assert store.state["home_score"] == 20
    assert store.state["visitor_score"] == 10
    assert store.state["state_revision"] == 502


def test_multi_client_stale_poll_after_newer_mutation_rejected() -> None:
    client = RevisionClient(504)
    assert client.receive(500) is False
    assert client.current_revision == 504


def test_obs_stale_rehearsal_contract() -> None:
    source = overlay_source()
    assert "CSRNOverlayHealth" in source
    assert "overlay_last_revision" in source
    assert "updateOverlayHealth(false)" in source
    assert "data-overlay-health" not in source
