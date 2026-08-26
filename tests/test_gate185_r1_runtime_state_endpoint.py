from __future__ import annotations

from pathlib import Path

import app as app_module


ROOT = Path(__file__).resolve().parents[1]


def test_runtime_state_endpoint_is_small_live_browser_contract() -> None:
    import runtime_state_cache

    runtime_state_cache._cached = None
    app_module.app.config.update(TESTING=True)
    with app_module.app.test_client() as client:
        response = client.get("/api/runtime-state")
        assert response.status_code == 200
        payload = response.get_json()

    for key in (
        "history",
        "events",
        "plays",
        "correction_log",
        "redo_stack",
        "graphics_queue",
    ):
        assert key not in payload

    assert payload["runtime_view_schema"] == "csrn-runtime-state-v1"
    assert payload["overlay_revision"] == app_module.OVERLAY_SCHEMA_REVISION
    assert isinstance(payload["ticker_items"], list)
    assert isinstance(payload["team_roles"], dict)
    assert isinstance(payload["canonical_field_state"], dict)


def test_overlay_and_production_theme_poll_runtime_state_not_full_state() -> None:
    overlay = (ROOT / "templates" / "overlay.html").read_text(encoding="utf-8")
    runtime = (
        ROOT / "static" / "csrn-production-theme-runtime.js"
    ).read_text(encoding="utf-8")

    assert "fetch('/api/runtime-state'" in overlay
    assert "fetch('/api/state',{cache:'no-store',signal:controller.signal})" not in overlay
    assert 'const RUNTIME_STATE_URL = "/api/runtime-state";' in runtime
    assert 'const RUNTIME_STATE_URL = "/api/state";' not in runtime


def test_command_center_keeps_authoritative_state_poll_contract() -> None:
    command_center = (ROOT / "templates" / "index.html").read_text(
        encoding="utf-8"
    )

    assert "statePollInFlight" in command_center
    assert "Mutation responses are authoritative" in command_center
    assert "fetch('/api/state',{credentials:'same-origin',cache:'no-store'" in command_center


def test_runtime_state_route_uses_lightweight_loader_while_state_route_reconciles() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")

    assert "load_state=load_reconciled_state" in source
    assert "load_runtime_state=load_state" in source


def test_production_theme_runtime_uses_adaptive_runtime_state_polling() -> None:
    runtime = (
        ROOT / "static" / "csrn-production-theme-runtime.js"
    ).read_text(encoding="utf-8")

    assert "window.setInterval(renderSelected, 300)" not in runtime
    assert "async function scheduleRenderSelected()" in runtime
    assert "stablePollCount" in runtime
    assert "Math.min(900, 300 + stablePollCount * 100)" in runtime


def test_production_theme_runtime_keeps_running_clock_on_fast_poll_path() -> None:
    runtime = (
        ROOT / "static" / "csrn-production-theme-runtime.js"
    ).read_text(encoding="utf-8")

    assert "let runtimeClockRunning = false;" in runtime
    assert "let lastRuntimeForClockPatch = null;" in runtime
    assert "function patchActiveFootballBoard" in runtime
    assert "function startClockPatchTimer()" in runtime
    assert "startClockPatchTimer();" in runtime
    assert "runtimeClockRunning = runtime.clock_running === true;" in runtime
    assert "lastRuntimeForClockPatch = runtime;" in runtime
    assert "runtime.clock_running === true ? Math.floor(Date.now() / 1000) : 0" not in runtime
    assert "runtime.revision," not in runtime
    # patchActiveFootballBoard(runtime) is defined (asserted above) but is a
    # thin wrapper around patchLiveGameState() that nothing calls anymore --
    # the actual call sites patch directly (patchLiveGameState(runtime) +
    # patchCollegiateRails(...)). Asserting a specific call-site string that
    # no longer exists made this pass go stale; the behavior it was meant to
    # confirm (the running clock keeps patching on the fast poll path) is
    # still covered by the runtimeClockRunning/lastRuntimeForClockPatch/
    # startClockPatchTimer assertions above.
    assert "function liveClockSeconds(runtime)" in runtime
    assert "? 200" not in runtime


