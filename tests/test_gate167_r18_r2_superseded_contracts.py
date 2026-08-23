from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")

def test_r18_r2_runtime_uses_multi_mode_video_board_contract():
    js = read("static/csrn-production-theme-runtime.js")
    assert "function themeVideoModeFor(alias, runtime)" in js
    assert "videoMode:activeVideoMode" in js
    assert "runtime.player_highlight" in js
    assert "runtime.sponsor_spotlight" in js

def test_r18_r2_old_player_only_render_assertion_is_gone_from_superseded_tests():
    names = [
        "test_gate167_r17_manual_spotlight_show_update_bridge.py",
        "test_gate167_r15_player_text_final_tuning.py",
        "test_gate167_r14_player_text_selector_correction.py",
        "test_gate167_r12_player_text_scale.py",
        "test_gate167_r11_player_presentation_legibility.py",
        "test_gate167_r10_player_transition_continuity.py",
        "test_gate167_r9_player_event_reliability.py",
        "test_gate167_r8_deterministic_state_binding.py",
    ]
    for name in names:
        text = read(f"tests/{name}")
        assert 'videoMode:playerModeFor(alias, runtime)' not in text


