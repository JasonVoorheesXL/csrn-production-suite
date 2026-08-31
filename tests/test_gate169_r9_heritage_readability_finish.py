from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")

def test_r9_dispatch_copy_is_scaled_for_social_readability():
    css = read("static/csrn-production-theme-runtime.css")
    assert ".hp-dispatch>small" in css
    assert "font:900 15px/1.08 Arial,Helvetica,sans-serif!important" in css
    assert ".hp-dispatch>strong" in css
    assert 'font:900 24px/1.02 Georgia,"Times New Roman",serif!important' in css
    assert ".hp-dispatch>p" in css
    assert 'font:700 18px/1.22 Georgia,"Times New Roman",serif!important' in css
    assert ".hp-dispatch footer" in css
    assert "font:900 12px/1 Arial,Helvetica,sans-serif!important" in css

def test_r9_sports_wire_copy_and_page_id_are_scaled_up():
    css = read("static/csrn-production-theme-runtime.css")
    assert ".hp-wire-title" in css
    assert "font:1000 16px/1 Arial,Helvetica,sans-serif!important" in css
    assert ".hp-wire-copy .csrn-theme-ticker-viewport" in css
    assert "font:900 16px/1.04 Arial,Helvetica,sans-serif!important" in css
    assert ".hp-page-id" in css
    assert "font:900 13px/1 Arial,Helvetica,sans-serif!important" in css
