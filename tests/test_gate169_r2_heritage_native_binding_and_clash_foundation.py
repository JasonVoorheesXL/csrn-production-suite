from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def read(rel): return (ROOT/rel).read_text(encoding="utf-8")

def test_heritage_is_integrated_media_theme():
    js=read("static/csrn-production-theme-runtime.js")
    assert 'alias === "heritage_press"' in js
    assert 'if (alias === "eight_bit_gameday") return "clash";' in js
    assert 'if (alias === "friday_night_stadium") return "clash";' in js
    assert 'if (alias === "heritage_press") return "broadcast";' in js
    assert 'return alias === "heritage_press" ? "broadcast" : "clash"' not in js

def test_heritage_highlight_uses_true_inner_video_window():
    js=read("static/csrn-production-theme-runtime.js")
    assert '.hp-opening' in js
    assert '.hp-highlight-feature[data-video-mode="highlight"]' in js
    assert '.hp-highlight-window[data-module="video.board"]' in js
    assert "windowHost.parentElement !== feature" in js

def test_heritage_sponsor_uses_opening_mode_section():
    js=read("static/csrn-production-theme-runtime.js")
    assert '.hp-sponsor-feature[data-video-mode="sponsor"]' in js
    assert "sponsorHost.parentElement !== opening" in js

def test_heritage_football_state_overrides_are_authoritative():
    js=read("static/csrn-production-theme-runtime.js")
    assert 'root.querySelectorAll(\'[data-bind="game.period"]\')' in js
    assert 'root.querySelectorAll(\'[data-bind="game.clock"]\')' in js
    assert 'root.querySelectorAll(\'[data-bind="game.downDistance"]\')' in js

def test_heritage_clash_foundation_uses_native_broadcast_opening():
    js=read("static/csrn-production-theme-runtime.js")
    assert "function mountHeritageFootballClash" in js
    assert '.hp-opening > .hp-live-opening[data-video-mode="broadcast"]' in js
    assert "csrn-heritage-clash-foundation" in js
    assert 'mountHeritageFootballClash(scoreTarget, runtime, state, activeVideoMode, alias)' in js

def test_heritage_clash_foundation_is_football_only():
    js=read("static/csrn-production-theme-runtime.js")
    assert 'String(state?.sport || runtime?.sport || "football").toLowerCase() !== "football"' in js

def test_heritage_native_css_preserves_newspaper_surface():
    css=read("static/csrn-production-theme-runtime.css")
    assert ".package-heritage-newspaper .hp-highlight-window.csrn-production-native-video-mode" in css
    assert ".package-heritage-newspaper .hp-sponsor-feature.csrn-production-native-video-mode.csrn-production-sponsor-board" in css
    assert ".package-heritage-newspaper .csrn-heritage-clash-foundation" in css
