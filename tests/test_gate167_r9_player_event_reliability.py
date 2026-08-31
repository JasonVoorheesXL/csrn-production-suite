from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")

def test_gate167_r9_preflights_player_media_and_falls_back_cleanly():
    js = read("static/csrn-production-theme-runtime.js")
    assert "async function preparePlayerMedia" in js
    assert "await imageLoads(candidate)" in js
    assert 'kind:"team-logo"' in js
    assert 'kind:"number-placeholder"' in js
    assert 'state.player.headshot = ""' in js
    assert "repairRenderedPlayerMedia" in js

def test_gate167_r9_hides_legacy_player_during_pending_theme_render():
    js = read("static/csrn-production-theme-runtime.js")
    css = read("static/csrn-production-theme-runtime.css")
    assert 'PLAYER_PENDING_CLASS = "csrn-production-theme-player-pending"' in js
    assert "setPlayerPending(playerPending)" in js
    assert "html.csrn-production-theme-player-pending #playerGraphic" in css

def test_gate167_r9_rearms_player_mode_after_undo_or_new_event():
    js = read("static/csrn-production-theme-runtime.js")
    assert "function playerActivationKey" in js
    assert "latest.id" in js
    assert "graphic.updated_at" in js
    assert "graphic.expires_at" in js
    assert "activationKey" in js
    assert 'lastPlayerActivationKey = ""' in js

def test_gate167_r9_preserves_integrated_player_video_mode():
    js = read("static/csrn-production-theme-runtime.js")
    assert "themedIntegratedPlayerSupported" in js
    assert "videoMode:activeVideoMode" in js
    assert "themeVideoModeFor(alias, runtime)" in js
    assert 'return themedIntegratedPlayerSupported(alias) ? "player" : "clash"' in js

def test_gate167_r9_player_reliability_survives_r18_highlight_binding():
    js = read("static/csrn-production-theme-runtime.js")
    assert "runtime.player_highlight" in js
    assert "preparePlayerMedia" in js
