from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")

def test_gate164_menu_assets_exist():
    assert (ROOT / "static/csrn-production-template-menu.css").is_file()
    assert (ROOT / "static/csrn-production-template-menu.js").is_file()

def test_gate164_theme_manager_loads_menu_assets():
    page = read("templates/theme_manager.html")
    assert "/static/csrn-production-template-menu.css?v=16.4-r1" in page
    assert "/static/csrn-production-template-menu.js?v=16.4-r1" in page

def test_gate164_menu_contains_approved_choices_and_legacy():
    js = read("static/csrn-production-template-menu.js")
    for package_id in (
        "legacy",
        "friday_night_stadium",
        "eight_bit_gameday",
        "heritage_press",
        "digital_neon",
        "collegiate_traditional",
    ):
        assert package_id in js

def test_gate164_selection_is_server_authoritative():
    js = read("static/csrn-production-template-menu.js")
    assert 'API = "/api/production-template"' in js
    assert "localStorage" not in js
    assert 'method:"POST"' in js
    assert "authoritative" in js
    assert "renderBindingEnabled" in js

def test_gate164_does_not_directly_load_frozen_engines_in_overlay_template():
    overlay = read("templates/overlay.html")
    assert "csrn-production-template-menu" not in overlay
    for engine in (
        "csrn-broadcast-layout-engine.js",
        "csrn-friday-night-stadium-engine.js",
        "csrn-eight-bit-gameday-engine.js",
        "csrn-heritage-press-engine.js",
        "csrn-neon-r2-engine.js",
    ):
        assert engine not in overlay


