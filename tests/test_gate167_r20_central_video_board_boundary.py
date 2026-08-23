from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")

def test_r20_geometry_intent_is_superseded_by_generalized_native_host():
    js = read("static/csrn-production-theme-runtime.js")
    assert "function nativeVideoBoardHost(root, alias, mode)" in js
    assert 'eight_bit_gameday: ".bl-8bit-video-board"' in js
    assert "const board = root.querySelector(auditedNativeBoards[alias])" in js
    assert 'board.querySelector(`:scope > [data-video-mode="${mode}"]`)' in js

def test_r20_no_percentage_overlay_is_authoritative():
    js = read("static/csrn-production-theme-runtime.js")
    native = js[js.index("function nativeVideoBoardHost"):js.index("function mountCentralBoardMedia")]
    assert "22.5%" not in native
    assert "23.5%" not in native
    assert "55%" not in native
    assert "57.5%" not in native

def test_r20_highlight_remains_contained_by_native_board():
    css = read("static/csrn-production-theme-runtime.css")
    assert ".bl-8bit-video-board" in css
    assert "object-fit:contain!important" in css

def test_r20_sponsor_uses_native_board():
    js = read("static/csrn-production-theme-runtime.js")
    assert 'nativeVideoBoardHost(root, alias, "sponsor")' in js

def test_r20_cache_bust_superseded_by_gate168():
    overlay = read("templates/overlay.html")
    assert "/static/csrn-production-theme-runtime.css?v=18.5-r11" in overlay
    assert "/static/csrn-production-theme-runtime.js?v=18.5-r11" in overlay






