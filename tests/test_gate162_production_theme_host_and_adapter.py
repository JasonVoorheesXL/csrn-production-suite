from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")

def test_gate162_adapter_files_exist():
    assert (ROOT/"static/csrn-production-theme-adapter.js").is_file()
    assert (ROOT/"static/csrn-production-theme-adapter.css").is_file()

def test_gate162_overlay_loads_adapter_and_host():
    overlay=read("templates/overlay.html")
    assert '/static/csrn-production-theme-adapter.css?v=16.2-r1' in overlay
    assert 'id="csrnProductionThemeHost"' in overlay
    assert '/static/csrn-production-theme-adapter.js?v=16.2-r1' in overlay

def test_gate162_explicit_package_activation_and_fallback():
    js=read("static/csrn-production-theme-adapter.js")
    assert 'APPROVED_PACKAGES' in js
    assert '"friday_night_stadium"' in js
    assert '"eight_bit_gameday"' in js
    assert '"digital_neon"' in js
    assert '"heritage_press"' in js
    assert 'missing-or-unapproved-package' in js
    assert 'setLegacyVisible(true)' in js

def test_gate162_maps_four_sports_without_layout_lab_dependency():
    js=read("static/csrn-production-theme-adapter.js")
    for sport in ("football","basketball","baseball","softball"):
        assert f'"{sport}"' in js
    assert "csrn-layout-lab" not in js.lower()
    assert "/api/current-game" not in js
    assert "/api/game-state" not in js

def test_gate162_frozen_theme_engines_are_not_modified_by_payload():
    payload_root=ROOT
    forbidden=(
        "static/csrn-broadcast-layout-engine.js",
        "static/csrn-broadcast-layout-engine.css",
        "static/csrn-eight-bit-gameday-engine.js",
        "static/csrn-eight-bit-gameday-engine.css",
        "static/csrn-friday-night-stadium-engine.js",
        "static/csrn-friday-night-stadium-engine.css",
        "static/csrn-neon-r2-engine.js",
        "static/csrn-neon-r2-engine.css",
    )
    # This contract is enforced by the installer payload manifest marker.
    manifest=read("CSRN_GATE162_PAYLOAD_SCOPE.txt")
    for item in forbidden:
        assert item not in manifest


