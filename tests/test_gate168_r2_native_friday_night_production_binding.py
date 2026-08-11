from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")

def test_gate168_r2_runtime_supports_both_audited_native_boards():
    js = read("static/csrn-production-theme-runtime.js")
    assert 'eight_bit_gameday: ".bl-8bit-video-board"' in js
    assert 'friday_night_stadium: ".bl-fns-video-board"' in js
    assert 'board.querySelector(`:scope > [data-video-mode="${mode}"]`)' in js

def test_gate168_r2_friday_highlight_uses_native_board():
    css = read("static/csrn-production-theme-runtime.css")
    assert ".package-stadium-approved .bl-fns-video-board" in css
    assert '[data-video-mode="highlight"].csrn-production-native-video-mode' in css
    assert ".csrn-production-highlight-video" in css
    assert "object-fit:contain!important" in css

def test_gate168_r2_friday_sponsor_uses_native_board():
    css = read("static/csrn-production-theme-runtime.css")
    assert '[data-video-mode="sponsor"].csrn-production-native-video-mode' in css
    assert ".csrn-production-sponsor-media-wrap" in css
    assert ".csrn-production-sponsor-copy" in css
    assert "font-size:84px!important" in css

def test_gate168_r2_native_modes_neutralize_transitions():
    css = read("static/csrn-production-theme-runtime.css")
    block = css[css.rindex("/* Gate 16.8 R2"):]
    assert "transition:none!important" in block
    assert "animation:none!important" in block
    assert "transform:none!important" in block

def test_gate168_r2_does_not_modify_frozen_engine_sources():
    # Contract test: production binding belongs only in runtime CSS/JS.
    js = read("static/csrn-production-theme-runtime.js")
    css = read("static/csrn-production-theme-runtime.css")
    assert ".bl-fns-video-board" in js
    assert ".bl-fns-video-board" in css

def test_gate168_r2_cache_bust():
    overlay = read("templates/overlay.html")
    assert "/static/csrn-production-theme-runtime.css?v=19.2-r18-r3" in overlay
    assert "/static/csrn-production-theme-runtime.js?v=19.2-r18-r3" in overlay






