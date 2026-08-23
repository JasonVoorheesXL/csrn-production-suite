from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")

def test_r19_highlight_polish_survives_generalized_native_board():
    js = read("static/csrn-production-theme-runtime.js")
    css = read("static/csrn-production-theme-runtime.css")
    assert "function nativeVideoBoardHost(root, alias, mode)" in js
    assert 'eight_bit_gameday: ".bl-8bit-video-board"' in js
    assert 'friday_night_stadium: ".bl-fns-video-board"' in js
    assert "const board = root.querySelector(auditedNativeBoards[alias])" in js
    assert 'nativeVideoBoardHost(root, alias, "highlight")' in js
    assert "csrn-production-highlight-video" in js
    assert "object-fit:contain!important" in css

def test_r19_highlight_video_autoplay_is_resilient():
    js = read("static/csrn-production-theme-runtime.js")
    assert 'video.autoplay = true' in js
    assert 'video.playsInline = true' in js
    assert 'video.muted = true' in js
    assert 'video.play().catch' in js

def test_r19_sponsor_has_media_fallback_chain():
    js = read("static/csrn-production-theme-runtime.js")
    assert 'const primaryUrl = imageCandidate(graphic.media_url)' in js
    assert 'const logoUrl = imageCandidate(graphic.sponsor_logo)' in js
    assert 'installImage(primaryUrl, logoUrl)' in js
    assert 'installImage(logoUrl)' in js

def test_r19_sponsor_typography_is_production_scaled():
    css = read("static/csrn-production-theme-runtime.css")
    assert ".csrn-production-sponsor-copy small" in css
    assert ".csrn-production-sponsor-copy strong" in css

def test_r19_cache_bust_superseded_by_gate168():
    overlay = read("templates/overlay.html")
    assert "/static/csrn-production-theme-runtime.css?v=18.5-r11" in overlay
    assert "/static/csrn-production-theme-runtime.js?v=18.5-r11" in overlay





