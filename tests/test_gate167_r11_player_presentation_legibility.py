from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")

def test_gate167_r11_increases_integrated_player_text_legibility():
    css = read("static/csrn-production-theme-runtime.css")
    assert "#csrnProductionThemeLayout .bl-fns-player-replacement > small" in css
    assert "font-size:18px!important" in css
    assert "#csrnProductionThemeLayout .bl-fns-player-replacement > strong" in css
    assert "font-size:34px!important" in css
    assert "#csrnProductionThemeLayout .bl-fns-player-replacement > span" in css
    assert "font-size:20px!important" in css

def test_gate167_r11_preserves_player_transition_reliability():
    js = read("static/csrn-production-theme-runtime.js")
    assert "cancelLegacyPlayerMotion()" in js
    assert "restoreLegacyPlayerNeutral()" in js
    assert "preparePlayerMedia(state, runtime)" in js
    assert "videoMode:activeVideoMode" in js
    assert "themeVideoModeFor(alias, runtime)" in js

def test_gate167_r11_duration_contract_survives_r18_media_binding():
    js = read("static/csrn-production-theme-runtime.js")
    assert "runtime.player_highlight" in js
    assert "player_graphic.duration" not in js
