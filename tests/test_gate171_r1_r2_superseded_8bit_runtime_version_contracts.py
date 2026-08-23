from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")

def test_gate170_history_tracks_current_authoritative_runtime_without_losing_8bit_contracts():
    js = read("static/csrn-production-theme-runtime.js")
    css = read("static/csrn-production-theme-runtime.css")
    assert "csrn-production-theme-binding-v46" in js
    assert "installEightBitAssetPathShim" in js
    assert 'raw.startsWith("8bit-gameday/") ? `/static/${raw}` : raw' in js
    assert "font-size:66px!important" in css
    assert "font-size:57px!important" in css

def test_friday_night_r1_cache_and_readiness_contract_remain_authoritative():
    overlay = read("templates/overlay.html")
    js = read("static/csrn-production-theme-runtime.js")
    assert "/static/csrn-production-theme-runtime.css?v=18.5-r11" in overlay
    assert "/static/csrn-production-theme-runtime.js?v=18.5-r11" in overlay
    assert "ensureFridayNightDynamicClashReady" in js
    assert 'canvas.dataset.artReady !== "true"' in js
    assert 'root.dataset.productionClashReady = "true"' in js






