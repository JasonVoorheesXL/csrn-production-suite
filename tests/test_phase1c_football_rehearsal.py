from __future__ import annotations

import copy
import pathlib
import threading
from typing import Any, Mapping

from flask import Flask

from canonical_state_service import CanonicalStateFoundation
from routes.coin_toss_routes import create_coin_toss_blueprint
from routes.system_routes import SystemRoutesDependencies, create_system_blueprint
from test_phase1a_data_integrity import (
    MemoryState,
    base_state,
    event_service_with_state_service,
    score_service_with_state_service,
    state_service_store,
)


ROOT = pathlib.Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "templates" / "index.html"
OVERLAY_HTML = ROOT / "templates" / "overlay.html"


def source(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def pending_try_state(team: str = "home", score: int = 6) -> dict[str, Any]:
    state = base_state()
    state[f"{team}_score"] = score
    CanonicalStateFoundation.enter_pending_try(state, team)
    return state


def coin_toss_client(state: Mapping[str, Any] | None = None):
    current = copy.deepcopy(dict(state or base_state()))
    current.update(
        {
            "home_score": 0,
            "visitor_score": 0,
            "quarter": "1",
            "broadcast_created": True,
            "events": [],
            "game_data_authority": "broadcaster",
        }
    )
    store = MemoryState(current)
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="phase1c-coin-toss")
    app.register_blueprint(
        create_coin_toss_blueprint(
            require_auth=lambda view: view,
            load_state=store.load,
            save_state=store.save,
            public_state=lambda incoming: copy.deepcopy(dict(incoming)),
            transaction_lock=threading.Lock(),
            clock=lambda: 1_800_000_000.0,
        )
    )
    return app.test_client(), store


def system_client():
    state = base_state()
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="phase1c-system")
    app.register_blueprint(
        create_system_blueprint(
            SystemRoutesDependencies(
                require_auth=lambda view: view,
                get_configuration_service=lambda: None,
                get_streaming_links=lambda: {},
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
    return app.test_client()


def test_halftime_legacy_toggle_resumes_third_quarter_live() -> None:
    state = base_state()
    state.update({"broadcast_phase": "halftime", "quarter": "2", "down": "2nd", "distance": "5"})
    store, persistence = state_service_store(state)
    service = score_service_with_state_service(store, persistence)
    result = service.toggle_halftime({"command_id": "half-resume"})
    assert result.ok
    assert store.state["broadcast_phase"] == "live"
    assert store.state["quarter"] == "3"
    assert store.state["down"] == "1st"
    assert store.state["distance"] == "10"
    assert store.state["state_revision"] == 501


def test_halftime_retry_does_not_advance_revision_twice() -> None:
    state = base_state()
    state.update({"broadcast_phase": "halftime", "quarter": "2"})
    store, persistence = state_service_store(state)
    service = score_service_with_state_service(store, persistence)
    payload = {"command_id": "half-retry"}
    service.toggle_halftime(payload)
    service.toggle_halftime(payload)
    assert store.state["quarter"] == "3"
    assert store.state["state_revision"] == 501


def test_touchdown_creates_one_pending_try() -> None:
    store, persistence = state_service_store()
    service = event_service_with_state_service(store, persistence)
    service.trigger({"command_id": "td-once", "team": "home", "event": "TD"})
    assert store.state["special_game_phase"] == "pending_try"
    assert store.state["possession"] == "home"
    assert store.state["home_score"] == 20
    assert len(store.state["events"]) == 1


def test_xp_and_two_point_outcomes_clear_pending_try_once() -> None:
    store, persistence = state_service_store(pending_try_state("home", 20))
    service = event_service_with_state_service(store, persistence)
    assert service.trigger({"command_id": "xp-good", "team": "home", "event": "XP", "conversion_outcome": "good"}).ok
    assert store.state["home_score"] == 21
    assert store.state.get("special_game_phase") == "kickoff"

    store, persistence = state_service_store(pending_try_state("visitor", 13))
    service = event_service_with_state_service(store, persistence)
    assert service.trigger({"command_id": "two-fail", "team": "visitor", "event": "2PT", "conversion_outcome": "failed"}).ok
    assert store.state["visitor_score"] == 13
    assert store.state.get("special_game_phase") == "kickoff"


def test_duplicate_conversion_retry_is_idempotent() -> None:
    store, persistence = state_service_store(pending_try_state("home", 20))
    service = event_service_with_state_service(store, persistence)
    payload = {"command_id": "xp-retry", "team": "home", "event": "XP", "conversion_outcome": "good"}
    service.trigger(payload)
    service.trigger(payload)
    assert store.state["home_score"] == 21
    assert len(store.state["events"]) == 1
    assert store.state["state_revision"] == 501


def test_undo_touchdown_clears_pending_try_coherently() -> None:
    store, persistence = state_service_store()
    service = event_service_with_state_service(store, persistence)
    service.trigger({"command_id": "td-before-undo", "team": "home", "event": "TD"})
    service.undo({"command_id": "td-undo"})
    assert store.state["home_score"] == 14
    assert store.state.get("special_game_phase") != "pending_try"
    assert len(store.state.get("redo_stack", [])) == 1


def test_coin_toss_record_and_undo_are_command_safe() -> None:
    client, store = coin_toss_client()
    payload = {
        "command_id": "coin-record",
        "source": "broadcaster",
        "winner": "home",
        "election": "defer",
        "opening_drive_direction": "right",
    }
    first = client.post("/api/coin-toss", json=payload)
    second = client.post("/api/coin-toss", json=payload)
    assert first.status_code == 200
    assert second.status_code == 200
    assert store.state["state_revision"] == 501
    assert store.state["coin_toss"]["second_half_receiving_team"] == "home"
    assert first.get_json()["command_id"] == "coin-record"

    undo = {"command_id": "coin-undo"}
    assert client.post("/api/coin-toss/undo", json=undo).status_code == 200
    assert client.post("/api/coin-toss/undo", json=undo).status_code == 200
    assert store.state["state_revision"] == 502
    assert store.state["coin_toss"]["recorded"] is False


def test_coin_toss_uses_command_client_and_pending_selectors() -> None:
    html = source(INDEX_HTML)
    assert "GameStateManager.mutate('/api/coin-toss'" in html
    assert "GameStateManager.mutate('/api/coin-toss/undo'" in html
    assert "route.startsWith('/api/coin-toss')" in html
    assert "#coinTossModal button" in html


def test_overlay_health_endpoint_reports_stale_and_recovery() -> None:
    client = system_client()
    healthy = client.post(
        "/api/overlay-health",
        json={"status": "HEALTHY", "overlay_last_revision": 501, "overlay_last_success": 1, "reported_at": 1},
    )
    assert healthy.status_code == 200
    assert healthy.get_json()["status"] == "HEALTHY"

    degraded = client.post(
        "/api/overlay-health",
        json={"status": "DEGRADED", "overlay_last_revision": 501, "consecutive_failures": 2},
    )
    assert degraded.get_json()["status"] == "DEGRADED"
    recovered = client.post(
        "/api/overlay-health",
        json={"status": "HEALTHY", "overlay_last_revision": 502, "consecutive_failures": 0},
    )
    assert recovered.get_json()["overlay_last_revision"] == 502
    assert client.get("/api/overlay-health").status_code == 200


def test_obs_health_is_visible_without_new_fast_poll_loop() -> None:
    index = source(INDEX_HTML)
    overlay = source(OVERLAY_HTML)
    assert "operatorObsHealth" in index
    assert "refreshOverlayHealth" in index
    assert "now-overlayHealthLastFetch<4000" in index
    assert "reportOverlayHealth" in overlay
    assert "fetch('/api/overlay-health'" in overlay
