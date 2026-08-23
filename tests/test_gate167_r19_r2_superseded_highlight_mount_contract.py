from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
def read(relative): return (ROOT / relative).read_text(encoding="utf-8")
def test_r19_r2_full_board_intent_is_superseded_by_native_host():
    js=read("static/csrn-production-theme-runtime.js")
    assert "function nativeVideoBoardHost(root, alias, mode)" in js
    assert "csrn-production-highlight-video" in js
def test_r19_r2_nested_placeholder_is_replaced_in_native_mode():
    js=read("static/csrn-production-theme-runtime.js")
    assert "host.replaceChildren()" in js


