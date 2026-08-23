from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")

def test_gate168_r2_r2_generalized_native_host_is_authoritative():
    js = read("static/csrn-production-theme-runtime.js")
    assert 'eight_bit_gameday: ".bl-8bit-video-board"' in js
    assert 'friday_night_stadium: ".bl-fns-video-board"' in js
    assert "const board = root.querySelector(auditedNativeBoards[alias])" in js

def test_gate168_r2_r2_no_gate167_test_requires_old_hardcoded_8bit_query():
    retired = 'root.querySelector(' + '".bl-8bit-video-board"' + ')'
    for path in (ROOT / "tests").glob("test_gate167_r*.py"):
        text = path.read_text(encoding="utf-8")
        assert retired not in text, path.name

def test_gate168_r2_r2_both_native_hosts_use_direct_mode_child():
    js = read("static/csrn-production-theme-runtime.js")
    assert 'board.querySelector(`:scope > [data-video-mode="${mode}"]`)' in js


