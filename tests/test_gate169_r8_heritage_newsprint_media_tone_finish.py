from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def read(rel):
    return (ROOT/rel).read_text(encoding="utf-8")

def test_r8_player_image_uses_newsprint_tone():
    css=read("static/csrn-production-theme-runtime.css")
    assert ".csrn-heritage-player-photo img" in css
    assert "grayscale(100%) sepia(18%) contrast(.96) brightness(1.02)!important" in css
    assert "mix-blend-mode:multiply!important" in css

def test_r8_highlight_video_uses_same_newsprint_tone():
    css=read("static/csrn-production-theme-runtime.css")
    assert ".hp-highlight-window video" in css
    assert ".hp-highlight-window .csrn-production-highlight-video" in css
    assert "grayscale(100%) sepia(18%) contrast(.96) brightness(1.02)!important" in css

def test_r8_clash_uses_same_newsprint_tone():
    css=read("static/csrn-production-theme-runtime.css")
    assert ".csrn-heritage-clash-image.csrn-production-highlight-video" in css
    assert ".csrn-heritage-clash-artwork img" in css
    assert "mix-blend-mode:multiply!important" in css

def test_r8_media_backdrops_use_heritage_paper():
    css=read("static/csrn-production-theme-runtime.css")
    assert "background:var(--hp-paper)!important" in css

def test_r8_sponsor_remains_color():
    css=read("static/csrn-production-theme-runtime.css")
    assert ".hp-sponsor-feature.csrn-production-heritage-sponsor-host" in css
    assert "filter:none!important" in css
    assert "-webkit-filter:none!important" in css
    assert "mix-blend-mode:normal!important" in css

def test_r8_cache_bust():
    overlay=read("templates/overlay.html")
    assert "/static/csrn-production-theme-runtime.css?v=18.5-r11" in overlay
    assert "/static/csrn-production-theme-runtime.js?v=18.5-r11" in overlay





