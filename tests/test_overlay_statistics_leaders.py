"""Player-leader rails stuck on "Awaiting Stats" at halftime (2026-10-30).

No plays were added while the rails were blank, and the server was slow
(1 s+ responses) at halftime. The overlay's statistics feed rebuilt the
whole game per call (deep copy, 346 KB with the full play register) for two
pollers per overlay page, and a freshly loaded overlay had nothing to show
until a fetch landed. The operator can't refresh a browser source on air.

* /api/statistics/overlay-state is built once per committed state revision
  and leaves out play_register, which no overlay reads.
* Each call is logged to runtime diagnostics.
* The overlay keeps this game's last stats in localStorage, shows them at
  once after a reload, and no longer holds its render on a slow fetch.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from flask import Flask

from routes.live_game_routes import LiveGameRoutesDependencies, create_live_game_blueprint
from runtime_diagnostics_service import get_runtime_diagnostics

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_JS = (ROOT / "static" / "csrn-production-theme-runtime.js").read_text(encoding="utf-8")


class Result:
    def __init__(self, data: dict[str, Any]) -> None:
        self.code = "OK"
        self.data = data


class CountingStatistics:
    def __init__(self) -> None:
        self.calls = 0

    def report(self, state: dict[str, Any]) -> Result:
        self.calls += 1
        return Result({"statistics": {
            "broadcast_id": state["broadcast_id"],
            "players": [{"team": "home", "number": "12", "passing_yards": state["state_revision"]}],
            "play_register": [{"play_id": "P1"}] * 50,
        }})


def build_client(peek: bool = True):
    state = {"broadcast_id": "FB-TEST-1", "state_revision": 7}
    statistics = CountingStatistics()

    def unused(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("not used")

    app = Flask(__name__)
    app.register_blueprint(create_live_game_blueprint(LiveGameRoutesDependencies(
        require_auth=lambda view: view,
        get_game_operations_service=unused,
        get_event_service=unused,
        get_rules_service=unused,
        get_statistics_service=lambda: statistics,
        load_state=lambda: dict(state),
        peek_state=(lambda reader: reader(state)) if peek else None,
    )))
    return app.test_client(), state, statistics


def test_overlay_statistics_leave_out_the_play_register() -> None:
    client, _, _ = build_client()
    body = client.get("/api/statistics/overlay-state").get_json()
    assert "play_register" not in body
    assert body["players"][0]["number"] == "12"


def test_overlay_statistics_are_built_once_per_state_revision() -> None:
    client, state, statistics = build_client()
    first = client.get("/api/statistics/overlay-state").get_json()
    second = client.get("/api/statistics/overlay-state").get_json()
    assert statistics.calls == 1
    assert first == second

    state["state_revision"] = 8  # a play was recorded
    third = client.get("/api/statistics/overlay-state").get_json()
    assert statistics.calls == 2
    assert third["players"][0]["passing_yards"] == 8

    state["broadcast_id"] = "FB-TEST-2"  # a different game, same revision
    state["state_revision"] = 8
    client.get("/api/statistics/overlay-state")
    assert statistics.calls == 3


def test_overlay_statistics_without_peek_state_are_never_cached() -> None:
    client, _, statistics = build_client(peek=False)
    client.get("/api/statistics/overlay-state")
    client.get("/api/statistics/overlay-state")
    assert statistics.calls == 2


def test_overlay_statistics_calls_are_logged() -> None:
    client, _, _ = build_client()
    client.get("/api/statistics/overlay-state")
    client.get("/api/statistics/overlay-state")
    events = [
        event for event in get_runtime_diagnostics().snapshot(limit=50)["events"]
        if event.get("event_type") == "SERVER_STATISTICS_OVERLAY"
    ][-2:]
    assert [event["cache_hit"] for event in events] == [False, True]
    assert events[-1]["broadcast_id"] == "FB-TEST-1"
    assert events[-1]["player_count"] == 1


def test_overlay_restores_this_games_stats_after_a_reload() -> None:
    assert 'const COLLEGIATE_STATISTICS_STORAGE_KEY = "csrn.collegiateStatistics.v1";' in RUNTIME_JS
    body = RUNTIME_JS[RUNTIME_JS.index("async function fetchCollegiateStatistics("):]
    body = body[: body.index("\n}\n")]
    assert "collegiateStatisticsCache.data = storedCollegiateStatistics(broadcastId);" in body
    assert "storeCollegiateStatistics(broadcastId, data);" in body
    # Render with what we have; don't wait on a slow fetch.
    assert body.rstrip().endswith("return collegiateStatisticsCache.data || collegiateStatisticsCache.promise;")
    # Saved stats from another game never show.
    assert "saved.broadcastId === broadcastId" in RUNTIME_JS
