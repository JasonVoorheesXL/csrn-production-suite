"""Phase C R3: applyDiamondBoardOverrides keeps the baseball/softball board live.

The render signature carries no game-state fields, so -- exactly like the
football board -- the diamond board must be patched on the fast path.
End-to-end behaviour is exercised by static/csrn-phasec-dispatch-lab.html
(headless-verifiable); this locks the structure.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "static" / "csrn-production-theme-runtime.js").read_text(encoding="utf-8")


def _body() -> str:
    start = JS.index("function applyDiamondBoardOverrides(root, alias, runtime)")
    return JS[start:JS.index("\nfunction ", start + 1)]


def test_diamond_patcher_reads_every_diamond_field() -> None:
    body = _body()
    for token in ("inning_half", "inningHalf", "runtime.inning", "runtime.balls",
                  "runtime.strikes", "runtime.outs", "runtime.bases"):
        assert token in body
    # base pips are painted in baseDiamond()'s visual order [2nd, 3rd, 1st]
    assert "const order = [bases[1], bases[2], bases[0]];" in body


def test_diamond_patcher_covers_the_four_package_themes() -> None:
    body = _body()
    assert '.bl-8bit-diamond-control-bank' in body
    assert '.bl-fns-diamond-center' in body and '.bl-fns-diamond-bottom' in body
    assert 'labeledCell(root, "INNING")' in body and 'labeledCell(root, "COUNT")' in body
    # T1 (docs/PHASE_C_THEME_SPORT_DISPATCH_PLAN.md): Collegiate's baseball
    # board is no longer the compact .bl-baseball-state board -- it's the
    # football-weight structure, patched via patchCollegiateBaseballDiamond/
    # patchCollegiateBaseballLineScore instead.
    assert 'patchCollegiateBaseballDiamond(root, {half, inning, balls, strikes, outs, bases}, runtime);' in body
    assert 'patchCollegiateBaseballLineScore(root, runtime);' in body
    assert '[data-bind="game.inning"]' in body


def test_dispatcher_no_longer_treats_diamond_as_a_noop() -> None:
    body = _body()
    assert "void root; void alias; void runtime;" not in body
    assert "host.querySelectorAll(\"i\").forEach" in body


def test_dispatch_lab_exists_and_wires_the_real_engines() -> None:
    lab = (ROOT / "static" / "csrn-phasec-dispatch-lab.html").read_text(encoding="utf-8")
    for src in ("csrn-broadcast-layout-engine.js", "csrn-friday-night-stadium-engine.js",
                "csrn-eight-bit-gameday-engine.js", "csrn-production-theme-runtime.js"):
        assert f'src="./{src}"' in lab
    assert "__phaseC" in lab
    for fn in ("productionSportFamily", "mergeRuntimeState",
               "applyDiamondBoardOverrides", "applyBasketballBoardOverrides"):
        assert fn in lab


def test_runtime_exposes_phasec_helpers_for_isolated_dom_tests() -> None:
    assert "__phaseC: Object.freeze({" in JS
    for fn in ("productionSportFamily", "mergeRuntimeState", "applyBoardOverrides",
               "applyBasketballBoardOverrides", "applyDiamondBoardOverrides"):
        block = JS[JS.index("__phaseC: Object.freeze({"):]
        assert fn in block[:block.index("})")]
