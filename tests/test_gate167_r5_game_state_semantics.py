from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")

def test_gate167_r5_ot_is_authoritative_across_period_aliases():
    js = read("static/csrn-production-theme-runtime.js")
    assert 'periodIsOt' in js
    assert 'periodIsOt ? "OT" : rawPeriod' in js
    for token in (
        "base.game.period = periodDisplay",
        "base.game.quarter = periodDisplay",
        "base.game.periodLabel = periodDisplay",
        "base.period = periodDisplay",
        "base.quarter = periodDisplay",
    ):
        assert token in js

def test_gate167_r5_down_distance_off_uses_dash_not_fixture_defaults():
    js = read("static/csrn-production-theme-runtime.js")
    assert "productionDownDistance(source)" in js
    assert 'down: downOff ? "-" : downDigits' in js
    assert 'distance: distanceOff ? "-" : distanceDigits' in js
    assert "base.game.downDistance = productionDown.combined" in js
    assert "base.game.down_distance = productionDown.combined" in js
    assert 'downDistance = "3RD & 7"' not in js
    assert 'down_distance = "3RD & 7"' not in js

def test_gate167_r5_clock_visibility_is_authoritative():
    js = read("static/csrn-production-theme-runtime.js")
    assert "productionClock(source)" in js
    assert "runtime.clock_visible === false" in js
    assert "runtime.clock_seconds" in js

def test_gate167_r5_preserves_live_ticker_and_themed_player_contracts():
    js = read("static/csrn-production-theme-runtime.js")
    assert "runtime.events" in js
    assert "track.animate(" in js
    assert 'activeComponents:["player"]' in js
    assert "runtime.player_graphic" in js
