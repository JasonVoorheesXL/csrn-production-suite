from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(path: str) -> str:
    return (ROOT/path).read_text(encoding="utf-8")

def test_gate163_r2_probe_files_exist():
    assert (ROOT/"static/csrn-production-theme-readiness.html").is_file()
    assert (ROOT/"static/csrn-production-theme-readiness-probe.js").is_file()

def test_gate163_r2_live_overlay_remains_gate6_only():
    overlay=read("templates/overlay.html")
    forbidden=(
        "csrn-broadcast-layout-engine.js",
        "csrn-friday-night-stadium-engine.js",
        "csrn-eight-bit-gameday-engine.js",
        "csrn-heritage-press-engine.js",
        "csrn-neon-r2-engine.js",
        "csrn-production-theme-readiness-probe.js",
    )
    for item in forbidden:
        assert item not in overlay

def test_gate163_r2_isolated_page_loads_engines_by_reference():
    page=read("static/csrn-production-theme-readiness.html")
    required=(
        "csrn-broadcast-layout-engine.css?v=16.3-r2",
        "csrn-friday-night-stadium-engine.css?v=16.3-r2",
        "csrn-eight-bit-gameday-engine.css?v=16.3-r2",
        "csrn-heritage-press-engine.css?v=16.3-r2",
        "csrn-neon-r2-engine.css?v=16.3-r2",
        "csrn-neon-softball-r42-driver.css?v=16.3-r2",
        "csrn-neon-baseball-r43-driver.css?v=16.3-r2",
        "csrn-broadcast-layout-engine.js?v=16.3-r2",
        "csrn-friday-night-stadium-engine.js?v=16.3-r2",
        "csrn-eight-bit-gameday-engine.js?v=16.3-r2",
        "csrn-heritage-press-engine.js?v=16.3-r2",
        "csrn-neon-r2-engine.js?v=16.3-r2",
        "csrn-neon-softball-r42-driver.js?v=16.3-r2",
        "csrn-neon-baseball-r43-driver.js?v=16.3-r2",
        "csrn-production-theme-readiness-probe.js?v=16.3-r2",
    )
    for item in required:
        assert item in page

def test_gate163_r2_probe_is_read_only_and_isolated():
    js=read("static/csrn-production-theme-readiness-probe.js")
    assert "isolated: true" in js
    assert "liveOverlayUntouched: true" in js
    assert "fetch(" not in js
    assert ".apply(" not in js
    assert "renderPackage(" not in js
    assert "templates/overlay.html" not in js

def test_gate163_r2_probe_covers_approved_packages():
    js=read("static/csrn-production-theme-readiness-probe.js")
    for package in ("friday_night_stadium","eight_bit_gameday","digital_neon","heritage_press"):
        assert package in js


