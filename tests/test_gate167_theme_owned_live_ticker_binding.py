from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")

def test_gate167_theme_owned_ticker_still_suppresses_legacy_only_when_active():
    js = read("static/csrn-production-theme-runtime.js")
    css = read("static/csrn-production-theme-runtime.css")
    assert 'TICKER_ACTIVE_CLASS = "csrn-production-theme-ticker-active"' in js
    assert "classList.toggle(TICKER_ACTIVE_CLASS, tickerActive)" in js
    assert "html.csrn-production-theme-ticker-active #eventTicker" in css

def test_gate167_theme_ticker_uses_frozen_visual_targets():
    js = read("static/csrn-production-theme-runtime.js")
    for selector in (
        ".bl-fns-ticker-led",
        ".bl-8bit-ticker-led",
        ".hp-wire-copy",
        ".n2-ticker span",
    ):
        assert selector in js

def test_gate167_legacy_ticker_is_not_used_as_theme_data_source():
    js = read("static/csrn-production-theme-runtime.js")
    assert "document.getElementById(\"tickerTrack\")" not in js
    assert "eventPlainText(runtime)" in js

def test_gate167_gate7_boundary_remains_intact():
    overlay = read("templates/overlay.html")
    for engine in (
        "csrn-broadcast-layout-engine.js",
        "csrn-friday-night-stadium-engine.js",
        "csrn-eight-bit-gameday-engine.js",
        "csrn-heritage-press-engine.js",
        "csrn-neon-r2-engine.js",
    ):
        assert engine not in overlay


