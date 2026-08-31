from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")

def test_gate167_r18_player_spotlight_no_longer_requires_detail():
    index = read("templates/index.html")
    assert "if(!p.player_id){status.textContent='Select a player first.'" in index
    assert "if(!p.player_id||!p.play_detail)" not in index
    assert "api('/api/graphics/player',{...p,action:'show',visible:true})" in index

def test_gate167_r18_uses_native_theme_video_board_modes():
    js = read("static/csrn-production-theme-runtime.js")
    assert "function themeVideoModeFor(alias, runtime)" in js
    assert 'return "highlight"' in js
    assert 'return "sponsor"' in js
    assert "videoMode:activeVideoMode" in js

def test_gate167_r18_maps_highlight_and_sponsor_state():
    js = read("static/csrn-production-theme-runtime.js")
    assert "function mergeManualMediaState(state, runtime)" in js
    assert "runtime.player_highlight" in js
    assert "runtime.sponsor_spotlight" in js
    assert "state.highlight =" in js
    assert "state.sponsor =" in js

def test_gate167_r18_mounts_media_inside_central_board():
    js = read("static/csrn-production-theme-runtime.js")
    assert "function mountCentralBoardMedia(root, runtime, mode, alias)" in js
    # R20 supersedes direct highlight/sponsor selector ownership for 8-Bit.
    # Both media modes route through the bounded center-board host.
    assert "function nativeVideoBoardHost(root, alias, mode)" in js
    assert "bl-8bit-video-board" in js
    assert 'nativeVideoBoardHost(root, alias, "highlight")' in js
    assert 'nativeVideoBoardHost(root, alias, "sponsor")' in js
    assert 'document.createElement("video")' in js

def test_gate167_r18_suppresses_legacy_takeovers_only_when_theme_owns_mode():
    css = read("static/csrn-production-theme-runtime.css")
    assert "html.csrn-production-theme-highlight-active #playerHighlight" in css
    assert "html.csrn-production-theme-sponsor-active #sponsorSpotlight" in css
