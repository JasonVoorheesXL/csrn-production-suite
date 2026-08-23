from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")

def test_gate167_r4_uses_real_event_feed_for_theme_ticker():
    js = read("static/csrn-production-theme-runtime.js")
    assert "runtime.events" in js
    assert "event.undone" in js
    assert "event.description" in js
    assert "event.team_name" in js
    assert "event.quarter" in js
    assert "event.after" in js
    assert "ticker_speed" in js
    assert "ticker_pause" in js
    assert "base.ticker.text = eventPlainText(source)" in js

def test_gate167_r4_theme_ticker_actually_scrolls():
    js = read("static/csrn-production-theme-runtime.js")
    css = read("static/csrn-production-theme-runtime.css")
    assert "track.animate(" in js
    assert "translateX(-50%)" in js
    assert "csrn-theme-ticker-track" in css
    assert ".bl-8bit-ticker-led" in js
    assert ".bl-fns-ticker-led" in js
    assert ".hp-wire-copy" in js
    assert ".n2-ticker span" in js

def test_gate167_r4_player_graphic_maps_to_theme_player_state():
    js = read("static/csrn-production-theme-runtime.js")
    assert "runtime.player_graphic" in js
    assert "activeComponents:[\"player\"]" in js
    for field in ("full_name", "display_name", "number", "position", "play_detail", "team_color"):
        assert field in js

def test_gate167_r4_supported_theme_players_replace_legacy_only_after_success():
    js = read("static/csrn-production-theme-runtime.js")
    css = read("static/csrn-production-theme-runtime.css")
    assert "playerSupported: true" in js
    assert "playerSupported: false" in js
    assert 'PLAYER_ACTIVE_CLASS = "csrn-production-theme-player-active"' in js
    assert "result.components.includes(\"player\")" in js
    assert "html.csrn-production-theme-player-active #playerGraphic" in css

def test_gate167_r4_neon_keeps_player_fallback():
    js = read("static/csrn-production-theme-runtime.js")
    neon = js.split("digital_neon:", 1)[1].split("})", 1)[0]
    assert "playerSupported: false" in neon

def test_gate167_r4_overlay_has_player_host_and_updated_runtime_version():
    overlay = read("templates/overlay.html")
    assert 'id="csrnProductionThemePlayerHost"' in overlay
    assert 'id="csrnProductionThemePlayerLayout"' in overlay
    assert "/static/csrn-production-theme-runtime.css?v=18.5-r11" in overlay
    assert "/static/csrn-production-theme-runtime.js?v=18.5-r11" in overlay






