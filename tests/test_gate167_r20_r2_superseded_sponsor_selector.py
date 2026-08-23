from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")

def test_r20_r2_history_is_superseded_by_generalized_native_host():
    js = read("static/csrn-production-theme-runtime.js")
    assert "function nativeVideoBoardHost(root, alias, mode)" in js
    assert 'eight_bit_gameday: ".bl-8bit-video-board"' in js
    assert 'friday_night_stadium: ".bl-fns-video-board"' in js
    assert "const board = root.querySelector(auditedNativeBoards[alias])" in js
    assert 'nativeVideoBoardHost(root, alias, "highlight")' in js
    assert 'nativeVideoBoardHost(root, alias, "sponsor")' in js


