"""Phase C R6 (commissioned): Heritage Press live line-score box.

The .hp-current-line LINE SCORE table + at-bat/pitcher roles are built and
styled by the engine; this keeps them live on the fast path (R/H/E totals,
current batter/pitcher name) in the same press typeface as the commentary.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "static" / "csrn-production-theme-runtime.js").read_text(encoding="utf-8")
ENGINE_JS = (ROOT / "static" / "csrn-heritage-press-engine.js").read_text(encoding="utf-8")


def _body() -> str:
    start = JS.index("function patchHeritageBoxscore(root, runtime)")
    return JS[start:JS.index("\nfunction ", start + 1)]


def test_heritage_boxscore_patch_is_called_from_the_diamond_branch() -> None:
    diamond = JS[JS.index("function applyDiamondBoardOverrides"):]
    diamond = diamond[: diamond.index("\nfunction ", 1)]
    assert "patchHeritageBoxscore(root, runtime);" in diamond


def test_patch_targets_the_engine_built_line_score_box() -> None:
    body = _body()
    assert '.hp-current-line[data-module="game.lineScore"]' in body
    assert '.hp-line-row:not(.head)' in body
    assert 'row.querySelectorAll(":scope > b")' in body and "slice(-3)" in body
    # the engine still owns the markup -- the runtime only patches values
    assert "hp-current-line" in ENGINE_JS
    assert "function patchHeritageBoxscore" not in ENGINE_JS


def test_patch_updates_at_bat_and_pitcher_names() -> None:
    body = _body()
    assert ".hp-role-stack .hp-role" in body
    assert "/AT BAT/i" in body
    assert "/(MOUND|CIRCLE)/i" in body
    assert "runtime.batter_name" in body and "runtime.pitcher_name" in body


def test_diamond_state_carries_line_score_through_merge() -> None:
    diamond_state = JS[JS.index("function productionDiamondState"):]
    diamond_state = diamond_state[: diamond_state.index("\nfunction ", 1)]
    assert "lineScore: objectValue(source.line_score, source.lineScore" in diamond_state
