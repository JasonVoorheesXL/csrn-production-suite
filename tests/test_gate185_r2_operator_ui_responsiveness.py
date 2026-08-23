from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_statistician_has_direct_quarter_controls() -> None:
    html = read("templates/index.html")

    assert 'id="statQuarterButtons"' in html
    assert "setStateFrom('quarter','1','statistician')" in html
    assert "setStateFrom('quarter','2','statistician')" in html
    assert "setStateFrom('quarter','3','statistician')" in html
    assert "setStateFrom('quarter','4','statistician')" in html
    assert "setStateFrom('quarter','OT','statistician')" in html
    assert "markActive('statQuarterButtons', currentState.quarter);" in html
    assert 'id="periodQuarterButtons"' in html
    assert "markActive('periodQuarterButtons', currentState.quarter);" in html


def test_simple_operator_state_buttons_render_optimistically() -> None:
    html = read("templates/index.html")

    assert "function applyOptimisticGameState(key,value)" in html
    assert "applyOptimisticGameState(key,value);await GameStateManager.mutate('/api/set',{[key]:value,source:'broadcaster'})" in html
    assert "applyOptimisticGameState(key,value);await GameStateManager.mutate('/api/set',{[key]:value,source})" in html
    assert "currentState=previous;render();alert" in html


def test_overlay_clock_ticks_locally_between_runtime_polls() -> None:
    overlay = read("templates/overlay.html")
    runtime = read("static/csrn-production-theme-runtime.js")

    assert "let overlayClockModel=null;" in overlay
    assert "setInterval(paintOverlayClock,250);" in overlay
    assert "syncOverlayClock(s);" in overlay
    assert "document.getElementById('clock').textContent=s.clock" not in overlay
    assert "function liveClockSeconds(runtime)" in runtime


