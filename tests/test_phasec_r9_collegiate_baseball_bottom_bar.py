"""Phase C R9 -- THROWAWAY PROTOTYPE of the Collegiate baseball bottom bar.

Commits 7-8 (injected .bl-college-stage video strip + ballpark backdrop)
were reverted: the refined T1 concept re-casts the football yard-line
strip's slot as an inning-by-inning line score with the base diamond
pinned right, and that needs the pinned engine (Round 26 is holding the
re-pin). This prototype proves the visual target from the runtime only --
`data-prototype="baseball-bottom-bar"` -- injected into the compact
baseballLineScore board. Not a shippable structure; T1 does the real work.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "static" / "csrn-production-theme-runtime.js").read_text(encoding="utf-8")
CSS = (ROOT / "static" / "csrn-production-theme-runtime.css").read_text(encoding="utf-8")
ENGINE_JS = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
ENGINE_CSS = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")


def test_commits_7_and_8_scaffolding_is_gone() -> None:
    for gone in ("ensureCollegiateVideoStage", "bl-college-stage-reserved",
                 "bl-college-stage-diamond", "bl-college-stage-live-feed"):
        assert gone not in JS, gone
        assert gone not in CSS, gone


def test_prototype_is_runtime_only_no_frozen_engine_edit() -> None:
    assert "function ensureCollegiateBaseballBottomBar(root, runtime)" in JS
    for name in ("bl-college-baseball-bar", "bl-college-line-score", "bl-cls-table"):
        assert name not in ENGINE_JS
        assert name not in ENGINE_CSS


def test_prototype_is_flagged_as_throwaway() -> None:
    body = JS[JS.index("function ensureCollegiateBaseballBottomBar"):]
    body = body[: body.index("\nfunction ", 1)]
    assert 'bar.setAttribute("data-prototype", "baseball-bottom-bar")' in body
    # header comment names T1 as the real path
    header = JS[JS.index("// Phase C R9"):JS.index("function ensureCollegiateBaseballBottomBar")]
    assert "THROWAWAY PROTOTYPE" in header and "T1" in header


def test_bottom_bar_is_wired_into_the_collegiate_diamond_branch() -> None:
    diamond = JS[JS.index("function applyDiamondBoardOverrides"):]
    diamond = diamond[: diamond.index("\nfunction ", 1)]
    assert "ensureCollegiateBaseballBottomBar(root, runtime);" in diamond
    # basketball branch no longer calls the removed video-stage helper
    basketball = JS[JS.index("function applyBasketballBoardOverrides"):]
    basketball = basketball[: basketball.index("\nfunction ", 1)]
    assert "ensureCollegiate" not in basketball


def test_line_score_has_innings_and_rhe_columns() -> None:
    body = JS[JS.index("function patchCollegiateLineScore"):]
    body = body[: body.index("\nfunction ", 1)]
    assert 'const cols = Math.max(9, inning);' in body
    assert '<th class="bl-cls-rhe">R</th><th class="bl-cls-rhe">H</th><th class="bl-cls-rhe">E</th>' in body
    assert 'bodyRow("visitor")' in body and 'bodyRow("home")' in body
    assert 'runtime.line_score' in body           # per-inning runs when present
    assert '"is-current"' in body                 # current inning highlighted


def test_diamond_now_mounts_into_the_bar_slot() -> None:
    body = JS[JS.index("function ensureCollegiateDiamond"):]
    body = body[: body.index("\nfunction ", 1)]
    assert '.bl-college-baseball-bar .bl-college-bar-diamond' in body
    # still falls back to the board so the graphic stands alone
    assert '.bl-scorebug.bl-collegiate, .bl-baseball-board.bl-collegiate' in body


def test_bottom_bar_css_mirrors_the_football_control_bank_split() -> None:
    assert ".bl-college-baseball-bar{" in CSS
    block = CSS[CSS.index(".bl-college-baseball-bar{"):]
    block = block[: block.index("}")]
    assert "grid-template-columns:minmax(0,1fr) 320px" in block   # line score | diamond
    assert "grid-column:1 / -1" in block                          # full width, like the football strip
    assert ".bl-cls-table{" in CSS
