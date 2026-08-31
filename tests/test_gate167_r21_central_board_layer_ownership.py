from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")

def test_r21_layer_ownership_is_superseded_by_native_mode_ownership():
    js = read("static/csrn-production-theme-runtime.js")
    css = read("static/csrn-production-theme-runtime.css")
    assert "function nativeVideoBoardHost(root, alias, mode)" in js
    assert "csrn-production-native-video-mode" in js
    assert "#csrnProductionThemeLayout .package-8bit-approved .bl-8bit-video-board" in css

def test_r21_external_overlay_is_disabled_after_r23():
    css = read("static/csrn-production-theme-runtime.css")
    assert "#csrnProductionThemeLayout > .csrn-production-video-board-overlay" in css
    assert "display:none!important" in css
    assert "visibility:hidden!important" in css

def test_r21_sponsor_scale_survives_native_r23_host():
    css = read("static/csrn-production-theme-runtime.css")
    assert 'font:900 44px/1 "Courier New",monospace!important' in css
    assert 'font:900 84px/.98 "Courier New",monospace!important' in css
    assert 'font:700 44px/1.08 "Courier New",monospace!important' in css
