from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")

def test_gate167_r15_uses_correct_shared_player_selector():
    css = read("static/csrn-production-theme-runtime.css")
    assert '#csrnProductionThemeLayout [data-video-mode="player"] > small' in css
    assert '#csrnProductionThemeLayout [data-video-mode="player"] > strong' in css
    assert '#csrnProductionThemeLayout [data-video-mode="player"] > span' in css

def test_gate167_r15_applies_requested_final_scale():
    css = read("static/csrn-production-theme-runtime.css")
    assert "font-size:31px!important" in css
    assert "font-size:60px!important" in css
    assert "font-size:36px!important" in css
    assert "font-size:82px!important" in css

def test_gate167_r15_preserves_player_runtime_behavior():
    js = read("static/csrn-production-theme-runtime.js")
    assert "videoMode:activeVideoMode" in js
    assert "themeVideoModeFor(alias, runtime)" in js
    assert "preparePlayerMedia(state, runtime)" in js
    assert "cancelLegacyPlayerMotion()" in js
    assert "restoreLegacyPlayerNeutral()" in js

def test_gate167_r15_cache_bust():
    overlay = read("templates/overlay.html")
    assert "/static/csrn-production-theme-runtime.css?v=18.5-r11" in overlay
    assert "/static/csrn-production-theme-runtime.js?v=18.5-r11" in overlay






