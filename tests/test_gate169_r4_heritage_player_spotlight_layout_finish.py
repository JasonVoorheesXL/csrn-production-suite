from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def read(rel): return (ROOT/rel).read_text(encoding="utf-8")

def test_r4_player_spotlight_inline_layout_is_authoritative():
    js=read("static/csrn-production-theme-runtime.js")
    assert "grid-template-columns:minmax(320px,44%) minmax(0,1fr)" in js
    assert "align-items:flex-start" in js
    assert "text-align:left" in js

def test_r4_player_spotlight_image_is_forced_grayscale():
    js=read("static/csrn-production-theme-runtime.js")
    css=read("static/csrn-production-theme-runtime.css")
    assert "filter:grayscale(1) contrast(1.08) sepia(.06)" in js
    assert "-webkit-filter:grayscale(1) contrast(1.08) sepia(.06)!important" in css

def test_r4_highlight_video_grayscale_backstop_present():
    css=read("static/csrn-production-theme-runtime.css")
    assert "hp-highlight-window.csrn-production-heritage-highlight-window .csrn-production-highlight-video" in css
    assert "-webkit-filter:grayscale(1) contrast(1.06) sepia(.05)!important" in css

def test_r4_cache_bust():
    overlay=read("templates/overlay.html")
    assert "/static/csrn-production-theme-runtime.css?v=18.5-r11" in overlay
    assert "/static/csrn-production-theme-runtime.js?v=18.5-r11" in overlay






