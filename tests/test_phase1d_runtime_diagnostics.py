from __future__ import annotations

import copy
import pathlib
import shutil
import time

import pytest
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable

from flask import Flask, jsonify, request

import routes.live_game_routes as live_game_routes_module
from routes.live_game_routes import LiveGameRoutesDependencies, create_live_game_blueprint
from routes.system_routes import SystemRoutesDependencies, create_system_blueprint
from runtime_diagnostics_service import (
    RuntimeDiagnosticsService,
    default_log_dir,
    get_runtime_diagnostics,
)


ROOT = pathlib.Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "templates" / "index.html"
TEST_TMP = ROOT / "work" / "phase1d_test_tmp"


def local_tmp(name: str) -> pathlib.Path:
    path = TEST_TMP / name
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)
    return path


@dataclass(frozen=True)
class StubResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.code == "OK"


class PlayStore:
    def __init__(self) -> None:
        self.state = {
            "broadcast_created": True,
            "broadcast_id": "B-DIAG",
            "state_revision": 10,
            "plays": [],
            "events": [],
            "recent_commands": {},
        }

    def load(self) -> dict[str, Any]:
        return copy.deepcopy(self.state)


class StubRulesService:
    def __init__(self, store: PlayStore) -> None:
        self.store = store
        self.results: dict[str, StubResult] = {}

    def play(self, incoming: dict[str, Any]) -> StubResult:
        command_id = str(incoming.get("command_id") or "")
        if command_id and command_id in self.store.state["recent_commands"]:
            return StubResult("OK", copy.deepcopy(self.store.state["recent_commands"][command_id]))
        play_number = len(self.store.state["plays"]) + 1
        play_type = str(incoming.get("play_type") or "run")
        play = {
            "play_id": f"B-DIAG-{play_number:04d}",
            "play_number": play_number,
            "play_type": play_type,
            "pass_outcome": str(incoming.get("pass_outcome") or ""),
        }
        event = {"id": f"evt-{play_number}", "play_id": play["play_id"]}
        self.store.state["plays"].append(play)
        self.store.state["events"].append(event)
        self.store.state["state_revision"] += 1
        result = {
            "state": {"state_revision": self.store.state["state_revision"], "broadcast_id": "B-DIAG"},
            "play": copy.deepcopy(play),
            "event": copy.deepcopy(event),
            "command_id": command_id,
        }
        if command_id:
            self.store.state["recent_commands"][command_id] = copy.deepcopy(result)
        return StubResult("OK", result)

    def clock_control(self, incoming: dict[str, Any]) -> StubResult:
        self.store.state["state_revision"] += 1
        return StubResult("OK", {"state": {"state_revision": self.store.state["state_revision"]}})

    def field_direction(self, incoming: dict[str, Any]) -> StubResult:
        return StubResult("OK", {"state": {}})


class StubGameOperations:
    def score(self, incoming: dict[str, Any]) -> StubResult:
        return StubResult("OK", {"state": {"state_revision": 11}})

    def set_values(self, incoming: dict[str, Any]) -> StubResult:
        return StubResult("OK", {"state": {"state_revision": 11}})


class StubEvents:
    def trigger(self, incoming: dict[str, Any]) -> StubResult:
        return StubResult("OK", {"state": {"state_revision": 11}, "event": {"id": "evt-1"}})

    def quick_correction(self, incoming: dict[str, Any]) -> StubResult:
        return StubResult("OK", {"state": {"state_revision": 11}})

    def undo(self, incoming: dict[str, Any]) -> StubResult:
        return StubResult("OK", {"state": {"state_revision": 11}})

    def restore(self, incoming: dict[str, Any]) -> StubResult:
        return StubResult("OK", {"state": {"state_revision": 11}})


def require_auth(view: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(view)
    def protected(*args: Any, **kwargs: Any):
        if request.headers.get("X-Test-Auth") != "yes":
            return jsonify({"error": "AUTH_REQUIRED"}), 401
        return view(*args, **kwargs)

    return protected


def auth_headers() -> dict[str, str]:
    return {"X-Test-Auth": "yes"}


def live_client():
    store = PlayStore()
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="phase1d-live")
    app.register_blueprint(
        create_live_game_blueprint(
            LiveGameRoutesDependencies(
                require_auth=require_auth,
                get_game_operations_service=lambda: StubGameOperations(),
                get_event_service=lambda: StubEvents(),
                get_rules_service=lambda: StubRulesService(store),
                get_statistics_service=lambda: None,
                load_state=store.load,
            )
        )
    )
    return app.test_client(), store


def system_client(store: PlayStore):
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="phase1d-system")
    app.register_blueprint(
        create_system_blueprint(
            SystemRoutesDependencies(
                require_auth=require_auth,
                get_configuration_service=lambda: None,
                get_streaming_links=lambda: {},
                diagnostic_status=lambda: {},
                load_state=store.load,
                load_runtime_state=store.load,
                public_state=lambda state: copy.deepcopy(state),
                runtime_state=lambda state: {"state_revision": state.get("state_revision", 0), "broadcast_id": state.get("broadcast_id", "")},
                readiness_payload=lambda: {},
                load_build_journal=lambda: [],
            )
        )
    )
    return app.test_client()


def test_structured_rules_play_log_contains_command_revision_play_id_and_counts() -> None:
    client, store = live_client()
    response = client.post(
        "/api/rules-play",
        json={"command_id": "play-1", "client_id": "phone-1", "play_type": "run"},
        headers=auth_headers(),
    )
    assert response.status_code == 200
    events = get_runtime_diagnostics().snapshot(limit=20)["events"]
    record = next(ev for ev in reversed(events) if ev.get("event_type") == "SERVER_RULES_PLAY")
    assert record["command_id"] == "play-1"
    assert record["client_id"] == "phone-1"
    assert record["state_revision_before"] == 10
    assert record["state_revision_after"] == 11
    assert record["play_id"] == "B-DIAG-0001"
    assert record["play_count_before"] == 0
    assert record["play_count_after"] == 1
    assert len(store.state["plays"]) == 1


def test_rules_play_logs_committed_mutation_when_response_preparation_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    client, store = live_client()

    def fail_jsonify(*_args: Any, **_kwargs: Any):
        raise RuntimeError("response serialization failed")

    monkeypatch.setattr(live_game_routes_module, "jsonify", fail_jsonify)

    with pytest.raises(RuntimeError, match="response serialization failed"):
        client.post(
            "/api/rules-play",
            json={
                "command_id": "play-response-uncertain",
                "client_id": "phone-1",
                "play_type": "pass",
                "pass_outcome": "incomplete",
            },
            headers=auth_headers(),
        )

    assert store.state["state_revision"] == 11
    assert len(store.state["plays"]) == 1
    assert store.state["plays"][0]["play_id"] == "B-DIAG-0001"

    records = [
        event
        for event in get_runtime_diagnostics().snapshot(limit=40)["events"]
        if event.get("event_type") == "SERVER_RULES_PLAY"
        and event.get("command_id") == "play-response-uncertain"
    ]
    assert len(records) == 1
    record = records[0]
    assert record["client_id"] == "phone-1"
    assert record["state_revision_before"] == 10
    assert record["state_revision_after"] == 11
    assert record["play_count_before"] == 0
    assert record["play_count_after"] == 1
    assert record["play_id"] == "B-DIAG-0001"
    assert record["http_status"] == 200
    assert record["response_uncertain"] is True
    assert record["error_type"] == "RuntimeError"
    assert "response serialization failed" in record["error_message"]


def test_duplicate_command_is_logged_as_replay_not_second_mutation() -> None:
    client, store = live_client()
    payload = {"command_id": "play-retry", "play_type": "run"}
    assert client.post("/api/rules-play", json=payload, headers=auth_headers()).status_code == 200
    assert client.post("/api/rules-play", json=payload, headers=auth_headers()).status_code == 200
    assert len(store.state["plays"]) == 1
    records = [
        ev for ev in get_runtime_diagnostics().snapshot(limit=40)["events"]
        if ev.get("event_type") == "SERVER_RULES_PLAY" and ev.get("command_id") == "play-retry"
    ]
    assert records[-1]["duplicate_replay"] is True
    assert records[-1]["play_count_before"] == records[-1]["play_count_after"] == 1


def test_runtime_state_delivery_logs_authoritative_register_counts() -> None:
    store = PlayStore()
    store.state["plays"].append({"play_id": "B-DIAG-0001"})
    store.state["events"].append({"id": "evt-1"})
    client = system_client(store)
    response = client.get("/api/runtime-state")
    assert response.status_code == 200
    record = next(ev for ev in reversed(get_runtime_diagnostics().snapshot(limit=30)["events"]) if ev.get("event_type") == "SERVER_RUNTIME_STATE")
    assert record["authoritative_play_count"] == 1
    assert record["latest_play_id"] == "B-DIAG-0001"
    assert record["runtime_contains_plays"] is False


def test_play_register_endpoint_returns_authoritative_plays_for_any_client() -> None:
    client, store = live_client()
    store.state["plays"].append({"play_id": "B-DIAG-0001", "play_number": 1})
    store.state["events"].append({"id": "evt-1", "play_id": "B-DIAG-0001"})
    response = client.get("/api/play-register", headers=auth_headers())
    data = response.get_json()
    assert response.status_code == 200
    assert data["play_count"] == 1
    assert data["latest_play_id"] == "B-DIAG-0001"
    assert data["plays"][0]["play_id"] == "B-DIAG-0001"


def test_rules_play_response_is_slim_but_register_endpoint_has_committed_play() -> None:
    client, _store = live_client()
    response = client.post(
        "/api/rules-play",
        json={"command_id": "play-slim", "client_id": "phone-1", "play_type": "run"},
        headers=auth_headers(),
    )
    data = response.get_json()
    assert response.status_code == 200
    assert "plays" not in data["state"]
    assert data["play"]["play_id"] == "B-DIAG-0001"
    register = client.get("/api/play-register", headers=auth_headers()).get_json()
    assert register["play_count"] == 1
    assert register["plays"][0]["play_id"] == "B-DIAG-0001"


def test_lost_rules_play_response_reconciles_same_command_without_duplicate() -> None:
    client, store = live_client()
    store.state["state_revision"] = 15
    for index in range(8):
        play_id = f"B-DIAG-{index + 1:04d}"
        store.state["plays"].append({"play_id": play_id, "play_number": index + 1})
        store.state["events"].append({"id": f"evt-{index + 1}", "play_id": play_id})
    payload = {
        "command_id": "client-1787438594199-8cd6202286e66:/api/rules-play:1787442153436:15c51ab5220f6",
        "client_id": "phone-1",
        "team": "visitor",
        "play_type": "pass",
        "pass_outcome": "incomplete",
    }

    first = client.post("/api/rules-play", json=payload, headers=auth_headers())
    assert first.status_code == 200
    assert store.state["state_revision"] == 16
    assert len(store.state["plays"]) == 9

    retry = client.post("/api/rules-play", json=payload, headers=auth_headers())
    data = retry.get_json()

    assert retry.status_code == 200
    assert data["state"]["state_revision"] == 16
    assert data["play"]["play_id"] == "B-DIAG-0009"
    assert data["play"]["play_type"] == "pass"
    assert data["play"]["pass_outcome"] == "incomplete"
    assert store.state["state_revision"] == 16
    assert len(store.state["plays"]) == 9
    assert len(
        [
            play
            for play in store.state["plays"]
            if play.get("play_type") == "pass"
            and play.get("pass_outcome") == "incomplete"
        ]
    ) == 1


def test_client_telemetry_endpoint_requires_authentication() -> None:
    client = system_client(PlayStore())
    assert client.post("/api/client-telemetry", json={"event_type": "REGISTER_UPDATED"}).status_code == 401
    assert client.post("/api/client-telemetry", json={"event_type": "REGISTER_UPDATED"}, headers=auth_headers()).status_code == 200


def test_runtime_diagnostics_endpoint_requires_authentication() -> None:
    client = system_client(PlayStore())
    assert client.get("/api/runtime-diagnostics").status_code == 401
    assert client.get("/api/runtime-diagnostics", headers=auth_headers()).status_code == 200


def test_incident_export_does_not_mutate_state() -> None:
    store = PlayStore()
    before = copy.deepcopy(store.state)
    tmp_path = local_tmp("incident_export")
    service = RuntimeDiagnosticsService(log_dir=tmp_path)
    try:
        bundle = service.export_bundle(
            load_state=store.load,
            runtime_state=lambda state: {"state_revision": state["state_revision"]},
            overlay_health={"status": "HEALTHY"},
            output_dir=tmp_path,
        )
    finally:
        service.close()
    assert bundle.exists()
    assert store.state == before


def test_ring_buffer_is_bounded() -> None:
    service = RuntimeDiagnosticsService(log_dir=local_tmp("ring_buffer"), ring_limit=100)
    try:
        for idx in range(130):
            service.record("TEST_EVENT", index=idx)
        snapshot = service.snapshot(limit=200)
    finally:
        service.close()
    assert len(snapshot["events"]) == 100
    assert snapshot["events"][0]["index"] == 30


def test_logging_writer_failure_does_not_raise() -> None:
    def broken_writer(_record: dict[str, Any]) -> None:
        raise OSError("disk unavailable")

    service = RuntimeDiagnosticsService(log_dir=local_tmp("writer_failure"), writer=broken_writer)
    service.record("TEST_EVENT", ok=True)
    assert service.snapshot(limit=5)["dropped"] == 1


def test_slow_async_writer_does_not_block_record_call() -> None:
    service = RuntimeDiagnosticsService(log_dir=local_tmp("slow_writer"))

    def slow_write(record: dict[str, Any]) -> None:
        time.sleep(0.2)

    service._write_record = slow_write  # type: ignore[method-assign]
    try:
        started = time.perf_counter()
        service.record("SLOW_TEST", ok=True)
        elapsed = time.perf_counter() - started
    finally:
        service.close()
    assert elapsed < 0.05


def test_default_log_location_is_outside_google_drive_project_tree() -> None:
    path = str(default_log_dir()).lower()
    assert "my drive" not in path
    assert "csrn-production-suite" not in path


def test_client_register_empty_and_poll_rejection_hooks_are_present() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert "REGISTER_EMPTY_UNEXPECTEDLY" in html
    assert "REGISTER_RENDER_ERROR" in html
    assert "POLL_REJECTED_STALE" in html
    assert "REGISTER_UPDATED" in html
    assert "/api/play-register" in html
    assert "refreshPlayRegister('runtime-revision'" in html
    assert "finishCommittedPlayEntry('rules-play-commit')" in html
    assert "plays:Array.isArray(currentState?.plays)?currentState.plays:[]" in html


def test_client_unknown_commit_semantics_and_play_messages_are_present() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert "commitStatus='UNKNOWN_COMMIT'" in html
    assert "status:'UNKNOWN_COMMIT'" in html
    assert "window.CommandClient.retryUnknown('rules-play',rulesPlayStateExtractor)" in html
    assert "if(msg)msg.textContent='RECORDING...'" in html
    assert "Play recorded. Updating play register..." in html
    assert "operatorErrorMessage(e,'Play was not recorded.')" in html
    assert "operatorErrorMessage(e,'Play could not be recorded.')" not in html


def test_diagnostics_panel_and_incident_export_hooks_are_present() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert "runtimeDiagnosticSummary" in html
    assert "Export Incident Bundle" in html
    assert "exportIncidentBundle" in html
    assert "/api/runtime-diagnostics/export" in html


def test_commercial_correlation_hooks_are_present() -> None:
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert "COMMERCIAL_START_REQUESTED" in html
    assert "COMMERCIAL_STARTED" in html
    assert "COMMERCIAL_STOPPED" in html
