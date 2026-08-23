from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "static" / "csrn-broadcast-layout-engine.js"
CSS = ROOT / "static" / "csrn-broadcast-layout-engine.css"


def source() -> str:
    return ENGINE.read_text(encoding="utf-8")


def closeout_css() -> str:
    css = CSS.read_text(encoding="utf-8")
    return css[css.index("/* Gate 11.2 — Closeout cockpit cleanup and legibility. */") :]


def test_gate112_approved_cockpit_has_one_shell_without_overlay_asset() -> None:
    approved = source()[source().index("function neonCorePanel") : source().index("function normalizePossession")]
    assert approved.count('class="bl-neon-core-shell"') == 2
    assert "bl-neon-asset-cockpit" not in approved
    assert ".bl-neon-command-core>.bl-neon-asset-cockpit" in closeout_css()
    assert "display:none!important" in closeout_css()


def test_gate112_approved_renderer_omits_play_and_shot_clock_nodes() -> None:
    approved = source()[source().index("function neonCorePanel") : source().index("function normalizePossession")]
    assert 'sportState(state,sport,"bl-neon-state",false)' in approved
    assert 'includeAuxClock ? `<div class="bl-play-clock"' in source()
    assert 'includeAuxClock ? `<div class="bl-shot-clock"' in source()


def test_gate112_marked_text_is_enlarged_by_seventy_five_percent() -> None:
    css = closeout_css()
    assert ".bl-neon-record{" in css and "font-size:24.5px" in css
    assert ".bl-possession{" in css and "font-size:15.75px" in css
    assert ".bl-inning{" in css and "font-size:36.75px" in css
    assert ".bl-count{" in css and "font-size:24.5px" in css
    assert "grid-template-columns:180px 1fr" in css


def test_gate112_clock_layout_reclaims_removed_clock_cells() -> None:
    css = closeout_css()
    assert 'grid-template-areas:"period clock" "down down" "pos pos"' in css
    assert 'grid-template-areas:"period clock"' in css
    assert ".bl-play-clock," in css and ".bl-shot-clock{" in css


