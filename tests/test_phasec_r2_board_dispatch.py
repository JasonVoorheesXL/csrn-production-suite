"""Phase C R2: applyBoardOverrides dispatches the live board patch by family."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "static" / "csrn-production-theme-runtime.js").read_text(encoding="utf-8")


def test_dispatcher_and_per_family_patchers_exist() -> None:
    assert "function applyBoardOverrides(root, alias, runtime)" in JS
    assert "function applyBasketballBoardOverrides(root, alias, runtime)" in JS
    assert "function applyDiamondBoardOverrides(root, alias, runtime)" in JS
    # The football patcher keeps its name (a gate-167 test pins the string).
    assert "function applyFootballBoardOverrides(root, alias, runtime)" in JS


def test_dispatcher_routes_by_sport_family() -> None:
    start = JS.index("function applyBoardOverrides(root, alias, runtime)")
    body = JS[start:JS.index("\nfunction ", start + 1)]
    assert "productionSportFamily(runtime && runtime.sport)" in body
    assert 'if (family === "basketball") return applyBasketballBoardOverrides(root, alias, runtime);' in body
    assert 'if (family === "baseball" || family === "softball") return applyDiamondBoardOverrides(root, alias, runtime);' in body
    assert "return applyFootballBoardOverrides(root, alias, runtime);" in body


def test_football_patcher_guard_uses_sport_family() -> None:
    start = JS.index("function applyFootballBoardOverrides(root, alias, runtime)")
    first_line = JS[start:JS.index("\n\n", start)].splitlines()[1]
    assert 'productionSportFamily(runtime && runtime.sport) !== "football"' in first_line


def test_call_sites_use_the_dispatcher() -> None:
    assert "applyFootballBoardOverrides(root, currentAlias, runtime);" not in JS
    assert "applyFootballBoardOverrides(scoreTarget, alias, runtime);" not in JS
    assert "applyBoardOverrides(root, currentAlias, runtime);" in JS
    assert "applyBoardOverrides(scoreTarget, alias, runtime);" in JS


def test_basketball_patcher_targets_each_theme_clock() -> None:
    start = JS.index("function applyBasketballBoardOverrides(root, alias, runtime)")
    body = JS[start:JS.index("\nfunction applyDiamondBoardOverrides", start)]
    assert ".bl-8bit-basketball-control-bank .bl-8bit-clock-led" in body
    assert ".bl-fns-basketball-clock" in body
    assert 'labeledCell(root, "CLOCK")' in body
    assert '[data-bind="game.clock"]' in body
    # Collegiate no longer patches (or renders) a shot clock: product decision 2026-09-14, see
    # docs/BASKETBALL_PANEL_PARITY.md. The other themes' clock patchers are unchanged.
    assert '[data-bind="game.shotClock"]' not in body
