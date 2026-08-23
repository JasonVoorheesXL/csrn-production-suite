from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def read(rel): return (ROOT/rel).read_text(encoding="utf-8")

def test_player_spotlight_owns_native_heritage_opening():
    js=read("static/csrn-production-theme-runtime.js")
    assert "function heritageNativePlayerHost(root)" in js
    assert '.hp-player-feature[data-video-mode="player"]' in js
    assert "function populateHeritagePlayerHost" in js
    assert "host.replaceChildren()" in js
    assert 'populateHeritagePlayerHost(scoreTarget, runtime, state, alias, activeVideoMode)' in js

def test_player_image_is_newspaper_grayscale():
    css=read("static/csrn-production-theme-runtime.css")
    assert ".csrn-heritage-player-photo img" in css
    assert "filter:grayscale(1) contrast(1.08) sepia(.06)!important" in css

def test_highlight_video_stays_native_and_grayscale():
    js=read("static/csrn-production-theme-runtime.js")
    css=read("static/csrn-production-theme-runtime.css")
    assert 'csrn-production-heritage-highlight-window' in js
    assert ".hp-highlight-window.csrn-production-heritage-highlight-window" in css
    assert "filter:grayscale(1) contrast(1.06) sepia(.05)!important" in css
    assert "object-fit:contain!important" in css

def test_sponsor_asset_remains_color_in_newspaper_shell():
    js=read("static/csrn-production-theme-runtime.js")
    css=read("static/csrn-production-theme-runtime.css")
    assert 'csrn-production-heritage-sponsor-host' in js
    assert ".hp-sponsor-feature.csrn-production-heritage-sponsor-host" in css
    assert "filter:none!important" in css
    assert "mix-blend-mode:normal!important" in css

def test_legacy_player_is_suppressed_during_theme_player_mode():
    js=read("static/csrn-production-theme-runtime.js")
    css=read("static/csrn-production-theme-runtime.css")
    assert '["playerGraphic", mode === "player"]' in js
    assert '"csrn-production-theme-player-active"' in js
    assert "html.csrn-production-theme-player-active body #playerGraphic" in css

def test_cache_bust():
    overlay=read("templates/overlay.html")
    assert "/static/csrn-production-theme-runtime.css?v=18.5-r11" in overlay
    assert "/static/csrn-production-theme-runtime.js?v=18.5-r11" in overlay





