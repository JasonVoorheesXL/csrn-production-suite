from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")

def test_gate167_r11_cancels_legacy_player_motion_before_theme_handoff():
    js = read("static/csrn-production-theme-runtime.js")
    assert "function cancelLegacyPlayerMotion()" in js
    assert "node.getAnimations().forEach(animation => animation.cancel())" in js
    assert 'node.style.setProperty("transition", "none", "important")' in js
    assert 'node.style.setProperty("animation", "none", "important")' in js
    assert "cancelLegacyPlayerMotion();" in js

def test_gate167_r11_restores_legacy_card_to_neutral_hidden_endpoint():
    js = read("static/csrn-production-theme-runtime.js")
    assert "function restoreLegacyPlayerNeutral()" in js
    assert 'node.classList.add("hidden")' in js
    assert "void node.offsetWidth" in js
    assert 'node.style.removeProperty("transition")' in js
    assert 'node.style.removeProperty("animation")' in js

def test_gate167_r11_pending_and_active_states_have_no_css_motion():
    css = read("static/csrn-production-theme-runtime.css")
    assert "html.csrn-production-theme-player-pending #playerGraphic" in css
    assert "html.csrn-production-theme-player-active #playerGraphic" in css
    assert "transition:none!important" in css
    assert "animation:none!important" in css
    assert "transform:none!important" in css

def test_gate167_r11_keeps_integrated_theme_player_mode():
    js = read("static/csrn-production-theme-runtime.js")
    assert "videoMode:activeVideoMode" in js
    assert "themeVideoModeFor(alias, runtime)" in js
    assert "themedIntegratedPlayerSupported(alias)" in js
    assert "preparePlayerMedia(state, runtime)" in js

def test_gate167_r11_player_transition_contract_survives_r18_highlight_binding():
    js = read("static/csrn-production-theme-runtime.js")
    assert "runtime.player_highlight" in js
    assert "cancelLegacyPlayerMotion()" in js
