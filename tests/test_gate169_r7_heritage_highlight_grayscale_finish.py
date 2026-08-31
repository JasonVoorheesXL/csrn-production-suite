from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def read(rel):
    return (ROOT/rel).read_text(encoding="utf-8")

def test_r7_history_is_superseded_by_r8_newsprint_tone():
    css=read("static/csrn-production-theme-runtime.css")
    assert ".hp-highlight-window video" in css
    assert ".hp-highlight-window .csrn-production-highlight-video" in css
    assert "grayscale(100%) sepia(18%) contrast(.96) brightness(1.02)!important" in css
    assert "mix-blend-mode:multiply!important" in css

def test_r8_remains_heritage_scoped():
    css=read("static/csrn-production-theme-runtime.css")
    assert "package-heritage-newspaper" in css
