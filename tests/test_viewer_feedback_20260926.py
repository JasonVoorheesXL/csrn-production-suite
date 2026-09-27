"""Viewer/operator feedback after the Caledonia vs. East Webster broadcast (2026-09-26), Collegiate
Traditional live. Same investigate-then-fix discipline as docs/FOOTBALL_INCIDENT_20260918.md: each item
below was reproduced by execution (a real seeded broadcast, headless-Chrome captures at 1920x1080, then
downscaled to a real phone width) before being fixed, not diagnosed from source alone.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENGINE_CSS = "static/csrn-broadcast-layout-engine.css"
NEON_CSS = "static/csrn-collegiate-neon.css"


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _rule(css: str, selector: str) -> str:
    start = css.index(selector) + len(selector)
    return css[start:css.index("}", start)]


# --- Item 1: Down & Distance too small on a phone-scaled OBS feed ------------------------------------


def test_item1_the_bl_down_class_the_report_named_is_dead_code_not_what_collegiate_renders() -> None:
    """The feedback framed this as 'Collegiate Traditional's .bl-down element ... per-package font-size
    overrides'. Verified live (headless capture, DOM inspection): Collegiate's football board has no
    .bl-down anywhere -- that class belongs to the RETIRED standalone Neon engine (.package-neon /
    .package-neon-approved, archived per docs/NEON_REDESIGN.md), which no live manifest selects any more.
    Collegiate's real Down & Distance is <b data-bind="game.downDistance"> inside .bl-college-field-meta
    (collegiateField() in the engine), confirmed live at a computed 19px before this fix."""
    js = read("static/csrn-broadcast-layout-engine.js")
    assert ".bl-down" not in js.split("function collegiateField(state) {")[1].split("\n  }\n")[0]
    assert 'data-bind="game.downDistance"' in js.split("function collegiateField(state) {")[1].split("\n  }\n")[0]
    css = read(ENGINE_CSS)
    down_rules = [m.start() for m in re.finditer(r"\.bl-down\b", css)]
    for pos in down_rules:
        # every remaining .bl-down selector in the shared engine CSS is scoped under the retired
        # standalone-Neon classes (or the unscoped base rule with no font-size) -- none under Collegiate
        line = css[max(0, pos - 80):pos]
        assert ".bl-collegiate" not in line, css[max(0, pos - 80):pos + 40]
    manifests = read("static/csrn-broadcast-layout-engine.js")
    assert '"package-neon"' not in manifests and "package-neon-approved" not in manifests


def test_item1_collegiates_readout_bar_value_text_was_increased_for_phone_legibility() -> None:
    """19px -> 26px, matching the same board's own Team Snapshot numbers (.bl-college-stat-grid strong,
    also 26px) so the bump lands on an already-established size in Collegiate's own UI rather than an
    arbitrary one. This is the fixed-canvas fix the report called for: the overlay renders into a literal
    1920x1080 canvas with no responsive breakpoint, so legibility at a scaled-down (phone) size can only
    come from a real font-size increase here."""
    css = read(ENGINE_CSS)
    meta = _rule(css, ".bl-college-field-meta b{")
    assert "font-size:26px" in meta
    label = _rule(css, ".bl-college-field-meta small{")
    assert "font-size:15px" in label
    stat_grid = _rule(css, ".bl-college-stat-grid strong{")
    assert "font-size:26px" in stat_grid  # the reference point this size was matched to
    # all four readout cells (Possession, Down, Ball, Line to gain) share one rule, so the bump is
    # uniform across the bar -- Down does not become visually inconsistent with its own siblings.


def test_item1_neons_callout_pill_grew_with_the_base_so_it_stays_the_largest_cell() -> None:
    """Neon overrides only the 2nd cell (Down & Distance, its callout pill) to a larger size than its
    siblings. With the base bumped to 26px the pill's old 25px override would have gone the wrong way --
    the callout would render SMALLER than the cells around it. Re-pinned to 32px, keeping it clearly the
    largest cell in the bar. Verified live under Neon: fits the same fixed 50px-tall row with no clipping."""
    css = read(NEON_CSS)
    pill_value = _rule(css, ".package-collegiate-neon .bl-college-field-meta span:nth-child(2) b {")
    assert "font-size: 32px;" in pill_value
    base_value = _rule(css, ".package-collegiate-neon .bl-college-field-meta b {")
    assert "font-size" not in base_value  # Neon only recolours the other three cells; size still comes from the engine CSS
