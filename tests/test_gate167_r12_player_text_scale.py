from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")

def test_gate167_r12_applies_requested_player_text_scale():
    css = read("static/csrn-production-theme-runtime.css")
    assert "#csrnProductionThemeLayout .bl-fns-player-replacement > small" in css
    assert "font-size:32px!important" in css
    assert "#csrnProductionThemeLayout .bl-fns-player-replacement > strong" in css
    assert "font-size:60px!important" in css
    assert "#csrnProductionThemeLayout .bl-fns-player-replacement > span" in css
    assert "font-size:35px!important" in css

def test_gate167_r12_preserves_player_behavior():
    js = read("static/csrn-production-theme-runtime.js")
    assert "cancelLegacyPlayerMotion()" in js
    assert "restoreLegacyPlayerNeutral()" in js
    assert "preparePlayerMedia(state, runtime)" in js
    assert "videoMode:activeVideoMode" in js
    assert "themeVideoModeFor(alias, runtime)" in js

def test_gate167_r12_manual_spotlight_boundary_is_superseded_by_r18():
    js = read("static/csrn-production-theme-runtime.js")
    assert "runtime.player_highlight" in js
    assert "runtime.sponsor_spotlight" in js
    assert "themeVideoModeFor(alias, runtime)" in js

def test_gate167_r12_cache_bust():
    overlay = read("templates/overlay.html")
    assert "/static/csrn-production-theme-runtime.css?v=18.5-r11" in overlay
    assert "/static/csrn-production-theme-runtime.js?v=18.5-r11" in overlay






