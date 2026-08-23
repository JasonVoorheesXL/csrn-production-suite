from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")

def r2_block(css):
    marker = "/* Gate 17.0 R2 — 8-Bit Lower Data Readability Polish."
    assert marker in css
    return css.split(marker, 1)[1]

def test_r2_increases_only_production_override_clock_and_small_led_values():
    css = read("static/csrn-production-theme-runtime.css")
    block = r2_block(css)
    assert ".bl-8bit-clock-led.csrn-production-led-override" in block
    assert "font-size:66px!important" in block
    assert ".bl-8bit-small-led.csrn-production-led-override" in block
    assert "font-size:57px!important" in block

def test_r2_reduces_8bit_override_glow():
    css = read("static/csrn-production-theme-runtime.css")
    block = r2_block(css)
    assert "text-shadow:0 0 1px #ffb000,0 0 4px #ffb000!important" in block

def test_r2_does_not_target_possession_ball_on_or_team_scores():
    css = read("static/csrn-production-theme-runtime.css")
    block = r2_block(css)
    assert "POSSESSION" not in block
    assert "BALL ON" not in block
    assert "bl-8bit-score" not in block
    assert "bl-8bit-team-tower" not in block

def test_r2_runtime_binding_and_cache_advance():
    js = read("static/csrn-production-theme-runtime.js")
    overlay = read("templates/overlay.html")
    assert "csrn-production-theme-binding-v46" in js
    assert "/static/csrn-production-theme-runtime.css?v=18.5-r11" in overlay
    assert "/static/csrn-production-theme-runtime.js?v=18.5-r11" in overlay

def test_dynamic_clash_and_asset_path_shim_remain_present():
    js = read("static/csrn-production-theme-runtime.js")
    assert 'alias === "eight_bit_gameday"' in js
    assert 'installEightBitAssetPathShim' in js
    assert 'raw.startsWith("8bit-gameday/") ? `/static/${raw}` : raw' in js




