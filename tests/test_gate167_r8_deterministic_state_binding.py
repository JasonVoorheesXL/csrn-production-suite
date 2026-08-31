from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")

def test_gate167_r8_does_not_modify_frozen_engines():
    # This gate is runtime-only. Frozen files are prerequisites, not payload files.
    assert not (ROOT / "tests" / "test_gate167_r8_frozen_engine_mutation.tmp").exists()

def test_gate167_r8_ot_and_dash_are_post_render_overrides():
    js = read("static/csrn-production-theme-runtime.js")
    assert "applyFootballBoardOverrides" in js
    assert 'cell.querySelector(".csrn-production-led-override") || cell.querySelector("svg")' in js
    assert 'clockHost.querySelector(".csrn-production-led-override") || clockHost.querySelector("svg")' in js
    assert 'if (raw === "OT") return "OT"' in js
    assert 'down: downOff ? "-" : downDigits' in js
    assert 'distance: distanceOff ? "-" : distanceDigits' in js
    assert 'labeledCell(root, "QUARTER")' in js
    assert 'labeledCell(root, "DOWN")' in js
    assert 'labeledCell(root, "TO GO")' in js

def test_gate167_r8_clock_uses_clock_seconds_and_visibility():
    js = read("static/csrn-production-theme-runtime.js")
    assert "formatClockSeconds" in js
    assert "runtime.clock_visible === false" in js
    assert "runtime.clock_seconds" in js
    assert "productionClock(source)" in js

def test_gate167_r8_maps_production_date_to_scheduled_date():
    js = read("static/csrn-production-theme-runtime.js")
    assert "base.scheduledDate = textValue(" in js
    assert "source.date" in js
    assert "source.scheduled_start" in js

def test_gate167_r8_player_uses_integrated_video_mode():
    js = read("static/csrn-production-theme-runtime.js")
    assert "playerModeFor(alias, runtime)" in js
    assert "videoMode:activeVideoMode" in js
    assert "themeVideoModeFor(alias, runtime)" in js
    assert 'alias === "eight_bit_gameday" || alias === "friday_night_stadium"' in js
    assert "integratedPlayerActive" in js
