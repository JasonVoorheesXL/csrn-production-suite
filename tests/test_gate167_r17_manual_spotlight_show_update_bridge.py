from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")

def test_gate167_r17_manual_player_spotlight_show_update_explicitly_shows():
    index = read("templates/index.html")
    assert "api('/api/graphics/player',{...p,action:'show',visible:true})" in index

def test_gate167_r17_highlight_and_sponsor_bridge_above_theme_board():
    css = read("static/csrn-production-theme-runtime.css")
    assert "html.csrn-production-theme-scorebug-active #playerHighlight" in css
    assert "html.csrn-production-theme-scorebug-active #sponsorSpotlight" in css
    assert "z-index:80!important" in css

def test_gate167_r17_keeps_themed_player_integration():
    js = read("static/csrn-production-theme-runtime.js")
    assert "videoMode:activeVideoMode" in js
    assert "themeVideoModeFor(alias, runtime)" in js
    assert "preparePlayerMedia(state, runtime)" in js
    assert "cancelLegacyPlayerMotion()" in js

def test_gate167_r17_does_not_fake_highlight_or_sponsor_theme_components():
    js = read("static/csrn-production-theme-runtime.js")
    assert "activeComponents:[\"player_highlight\"]" not in js
    assert "activeComponents:[\"sponsor_spotlight\"]" not in js
