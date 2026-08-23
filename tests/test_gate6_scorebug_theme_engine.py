from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_each_theme_has_a_distinct_render_tree() -> None:
    source=(ROOT/"static"/"csrn-scorebug-engine.js").read_text(encoding="utf-8")
    for name in ("modern","classic","pixel","minimal","press","stadium","neon","collegiate"):
        assert f"function {name}(" in source
    for marker in ("classic-team","pixel-team","minimal-row","press-team","stadium-board","neon-wing","college-crest"):
        assert marker in source

def test_engine_preserves_runtime_ids() -> None:
    source=(ROOT/"static"/"csrn-scorebug-engine.js").read_text(encoding="utf-8")
    for element_id in ("homeLogo","visitorLogo","homeName","visitorName","homeMascot","visitorMascot","homeRecord","visitorRecord","homeScore","visitorScore","quarter","clock","down","homePos","visitorPos"):
        assert element_id in source


def test_preview_css_targets_generic_renderer_root() -> None:
    css=(ROOT/"static"/"csrn-scorebug-engine.css").read_text(encoding="utf-8")
    assert ".csrn-scorebug{" in css
    assert "#scorebug.csrn-scorebug{" not in css
    assert ".scorebug-preview-error.visible" in css


def test_pixel_and_press_packages_are_structurally_distinct() -> None:
    js=(ROOT/"static"/"csrn-scorebug-engine.js").read_text(encoding="utf-8")
    assert "function pixel(" in js
    assert "pixel-board" in js
    assert "function press(" in js
    assert "press-sheet" in js
    assert "stadium-board" in js
    assert "minimal-stack" in js


def test_renderer_css_loads_after_theme_skin_in_preview_and_live() -> None:
    overlay = (ROOT / "templates" / "overlay.html").read_text(encoding="utf-8")
    manager = (ROOT / "templates" / "theme_manager.html").read_text(encoding="utf-8")
    assert overlay.index('/themes/current.css') < overlay.index('/static/csrn-scorebug-engine.css?v=3')
    assert manager.index('id="previewThemeCss"') < manager.index('/static/csrn-scorebug-engine.css?v=3')
    authoritative_link = '<link rel="stylesheet" href="/static/csrn-scorebug-engine.css?v=3">'
    assert overlay.count(authoritative_link) == 1
    assert manager.count(authoritative_link) == 1


def test_minimal_stadium_and_neon_have_refined_contracts() -> None:
    engine = (ROOT / "static" / "csrn-scorebug-engine.js").read_text(encoding="utf-8")
    css = (ROOT / "static" / "csrn-scorebug-engine.css").read_text(encoding="utf-8")
    assert "function minimalIdentity(" in engine
    assert "stadium-brand" in engine
    assert "FRIDAY NIGHT SCOREBOARD" in engine
    assert "GUEST" in engine
    assert ".layout-minimal .mascot,.layout-minimal .team-record" in css
    assert "display:none!important" in css
    assert ".layout-stadium .stadium-board" in css
    assert "Friday Night Stadium authoritative physical-scoreboard override" in css
    assert ".layout-neon .neon-center" in css
    assert 'background:linear-gradient(180deg,#07111d,#02050b)!important' in css


def test_engine_has_preview_live_parity_guards() -> None:
    css = (ROOT / "static" / "csrn-scorebug-engine.css").read_text(encoding="utf-8")
    assert 'Engine parity guard' in css
    assert '.csrn-scorebug[data-rendered="true"]' in css
    assert '.csrn-scorebug.layout-press .press-center' in css
    assert '.csrn-scorebug.layout-pixel .pixel-center' in css


