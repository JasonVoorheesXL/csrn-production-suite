from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def read(rel):
    return (ROOT/rel).read_text(encoding="utf-8")

def clash_block():
    js=read("static/csrn-production-theme-runtime.js")
    return js[js.index("function mountHeritageFootballClash"):js.index("function normalizePlayerDetailSeparator")]

def test_r6_r4_uses_native_broadcast_opening():
    block=clash_block()
    assert '.hp-opening > .hp-live-opening[data-video-mode="broadcast"]' in block
    assert "csrn-heritage-clash-highlight-host" in block

def test_r6_r4_clash_reuses_exact_highlight_media_frame_classes():
    block=clash_block()
    assert 'frame.className = "hp-highlight-window csrn-production-native-video-mode csrn-production-heritage-highlight-window csrn-heritage-clash-artwork"' in block
    assert 'frame.dataset.module = "video.board"' in block
    assert 'image.className = "csrn-production-highlight-video csrn-heritage-clash-image"' in block

def test_r6_r4_has_no_team_identity_inside_clash():
    block=clash_block()
    for forbidden in (
        "team.logo",
        "textValue(team.name",
        "textValue(team.mascot",
        "recordText",
        "venue.toUpperCase",
        "csrn-heritage-clash-heading",
        "csrn-heritage-clash-identities",
    ):
        assert forbidden not in block

def test_r6_r4_standard_asset_exists():
    asset=ROOT/"static/assets/heritage_press/heritage-neutral-football-clash.png"
    assert asset.is_file()
    assert asset.stat().st_size > 10000

def test_r6_r4_clash_image_covers_highlight_frame():
    css=read("static/csrn-production-theme-runtime.css")
    assert ".hp-live-opening.csrn-heritage-clash-highlight-host" in css
    assert ".hp-highlight-window.csrn-production-heritage-highlight-window.csrn-heritage-clash-artwork" in css
    assert ".csrn-heritage-clash-image.csrn-production-highlight-video" in css
    assert "object-fit:cover!important" in css
    assert "max-width:none!important" in css
    assert "max-height:none!important" in css

def test_r6_r4_preserves_accepted_heritage_media_paths():
    js=read("static/csrn-production-theme-runtime.js")
    assert "function populateHeritagePlayerHost" in js
    assert "csrn-production-heritage-highlight-window" in js
    assert "csrn-production-heritage-sponsor-host" in js

def test_r6_r4_cache_bust():
    overlay=read("templates/overlay.html")
    assert "/static/csrn-production-theme-runtime.css?v=18.5-r11" in overlay
    assert "/static/csrn-production-theme-runtime.js?v=18.5-r11" in overlay





