from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")

def test_r4_r4_overlay_is_expected_at_target_cache_version():
    overlay = read("templates/overlay.html")
    assert "/static/csrn-production-theme-runtime.css?v=18.5-r11" in overlay
    assert "/static/csrn-production-theme-runtime.js?v=18.5-r11" in overlay
    assert "/static/csrn-production-theme-runtime.css?v=16.9-r3" not in overlay
    assert "/static/csrn-production-theme-runtime.js?v=16.9-r3" not in overlay






