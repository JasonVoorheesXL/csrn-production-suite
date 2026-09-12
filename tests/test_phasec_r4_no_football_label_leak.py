"""Phase C R4: no football-specific label leaks onto a non-football board.

patchThemeScoresAndPossession() runs for every sport (scores are
universal). A possession indicator is football/basketball only, and the
football period/down cells must not overwrite a diamond/basketball board.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "static" / "csrn-production-theme-runtime.js").read_text(encoding="utf-8")


def _body() -> str:
    start = JS.index("function patchThemeScoresAndPossession(root, alias, runtime)")
    return JS[start:JS.index("\nfunction ", start + 1)]


def test_possession_is_gated_to_football_and_basketball() -> None:
    body = _body()
    assert "const family = productionSportFamily(runtime.sport);" in body
    assert 'const hasPossession = family === "football" || family === "basketball";' in body


def test_fns_football_score_marker_is_football_only() -> None:
    body = _body()
    # the football score decoration is wrapped so baseball/basketball scores
    # never get a football stamped on them
    assert 'if (family === "football") {\n      for (const [node, active] of [' in body


def test_eight_bit_and_heritage_possession_are_conditional() -> None:
    body = _body()
    assert "if (hasPossession) {\n      setLedText(\n        labeledCell(root, \"POSSESSION\")" in body
    assert "if (possessionValue && hasPossession) {" in body


def test_heritage_football_period_and_down_cells_are_football_only() -> None:
    body = _body()
    # QUARTER / DOWN / productionFootballPeriod only run inside a football guard
    seg = body[body.index("Heritage's state grid uses newspaper cells"):]
    assert 'if (family === "football") {' in seg
    assert "productionFootballPeriod(runtime)" in seg
    assert "productionDownDistance(runtime).combined" in seg


def test_collegiate_possession_dataset_is_cleared_for_non_football() -> None:
    body = _body()
    assert "if (hasPossession) node.dataset.possession = possession;" in body
    assert "else delete node.dataset.possession;" in body
