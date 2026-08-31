from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")

def test_r23_targets_exact_native_8bit_video_board_contract():
    js = read("static/csrn-production-theme-runtime.js")
    assert "function nativeVideoBoardHost(root, alias, mode)" in js
    assert 'eight_bit_gameday: ".bl-8bit-video-board"' in js
    assert "const board = root.querySelector(auditedNativeBoards[alias])" in js
    assert 'board.querySelector(`:scope > [data-video-mode="${mode}"]`)' in js

def test_r23_replaces_native_mode_content_not_theme_root():
    js = read("static/csrn-production-theme-runtime.js")
    native = js[js.index("function nativeVideoBoardHost"):js.index("function mountCentralBoardMedia")]
    assert "22.5%" not in native
    assert "55%" not in native
    assert "csrn-production-video-board-overlay" not in native
    assert "host.replaceChildren()" in js

def test_r23_highlight_remains_native_and_contained():
    css = read("static/csrn-production-theme-runtime.css")
    assert ".package-8bit-approved .bl-8bit-video-board" in css
    assert '[data-video-mode="highlight"] .csrn-production-highlight-video' in css
    assert "object-fit:contain!important" in css

def test_r23_sponsor_remains_native():
    js = read("static/csrn-production-theme-runtime.js")
    assert 'nativeVideoBoardHost(root, alias, "sponsor")' in js
