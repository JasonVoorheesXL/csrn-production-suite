from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")

def test_r23_r2_runtime_native_binding_is_authoritative():
    js = read("static/csrn-production-theme-runtime.js")
    assert "function nativeVideoBoardHost(root, alias, mode)" in js
    assert 'eight_bit_gameday: ".bl-8bit-video-board"' in js
    assert 'friday_night_stadium: ".bl-fns-video-board"' in js
    assert "const board = root.querySelector(auditedNativeBoards[alias])" in js
    assert 'board.querySelector(`:scope > [data-video-mode="${mode}"]`)' in js

def test_r23_r2_runtime_preserves_8bit_native_host_semantics():
    js = read("static/csrn-production-theme-runtime.js")
    assert ".bl-8bit-video-board" in js
    assert 'nativeVideoBoardHost(root, alias, "highlight")' in js
    assert 'nativeVideoBoardHost(root, alias, "sponsor")' in js


