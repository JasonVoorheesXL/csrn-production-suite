from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def read(rel):
    return (ROOT/rel).read_text(encoding="utf-8")

def test_r1_8bit_idle_mode_is_native_clash():
    js=read("static/csrn-production-theme-runtime.js")
    assert 'if (alias === "eight_bit_gameday") return "clash";' in js

def test_r1_8bit_native_board_contract_is_preserved():
    js=read("static/csrn-production-theme-runtime.js")
    assert 'eight_bit_gameday: ".bl-8bit-video-board"' in js
    assert 'const host = board.querySelector(`:scope > [data-video-mode="${mode}"]`);' in js

def test_r1_selected_team_identity_remains_in_render_signature():
    js=read("static/csrn-production-theme-runtime.js")
    for needle in (
        "runtime.home_school_id",
        "runtime.visitor_school_id",
        "runtime.home_team",
        "runtime.visitor_team",
        "runtime.home_identity",
        "runtime.visitor_identity",
    ):
        assert needle in js

def test_r1_does_not_reimplement_8bit_player_recoloring_in_production_runtime():
    js=read("static/csrn-production-theme-runtime.js")
    # The frozen CSRNEightBitGamedayEngine remains responsible for its own
    # paintClash/material decomposition. Friday Night may independently use
    # primary/secondary layer names in the shared production runtime.
    assert "function paintClash(" not in js
    assert "function paintEightBitClash(" not in js
    assert "function recolorEightBit" not in js

def test_r1_primary_media_still_temporarily_owns_board_modes():
    js=read("static/csrn-production-theme-runtime.js")
    assert 'if (primaryGraphicVisible(runtime.player_highlight)) return "highlight";' in js
    assert 'if (primaryGraphicVisible(runtime.sponsor_spotlight)) return "sponsor";' in js
    assert 'if (playerVisible(runtime)) return "player";' in js

def test_r1_cache_bust():
    overlay=read("templates/overlay.html")
    assert "/static/csrn-production-theme-runtime.css?v=18.5-r11" in overlay
    assert "/static/csrn-production-theme-runtime.js?v=18.5-r11" in overlay





