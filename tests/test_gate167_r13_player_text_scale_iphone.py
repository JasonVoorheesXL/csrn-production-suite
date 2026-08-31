from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")

def test_gate167_r13_applies_iphone_player_text_scale():
    css = read("static/csrn-production-theme-runtime.css")
    assert "font-size:44px!important" in css
    assert "font-size:86px!important" in css
    assert "font-size:52px!important" in css
    assert "font-size:116px!important" in css
