from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
def read(relative): return (ROOT / relative).read_text(encoding="utf-8")
def test_r19_r3_integrity_survives_native_r23_binding():
    js=read("static/csrn-production-theme-runtime.js")
    assert "function mountCentralBoardMedia" in js
    assert "function nativeVideoBoardHost" in js
    assert "csrn-production-highlight-video" in js
    assert "csrn-production-sponsor-board" in js


