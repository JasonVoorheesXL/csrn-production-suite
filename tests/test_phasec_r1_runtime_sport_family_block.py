"""Phase C R1: mergeRuntimeState dispatches the game-state block by sport family.

Ships dark -- there is no non-football canonical state yet -- so the football
path must stay byte-for-byte what it was, and the non-football branches must
strip the football-only game keys.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "static" / "csrn-production-theme-runtime.js").read_text(encoding="utf-8")


def _merge_body() -> str:
    start = JS.index("function mergeRuntimeState(")
    end = JS.index("\nfunction ", start + 1)
    return JS[start:end]


def test_sport_family_helper_collapses_canadian_football() -> None:
    assert "function productionSportFamily(sport)" in JS
    helper = JS[JS.index("function productionSportFamily(sport)"):]
    helper = helper[: helper.index("\nfunction ")]
    assert '"canadian_football"' in helper and '"cfl"' in helper
    assert 'return "football"' in helper  # unknown -> football, byte-identical today
    for fam in ("basketball", "baseball", "softball"):
        assert f'"{fam}"' in helper


def test_per_family_state_builders_exist() -> None:
    assert "function productionBasketballState(source, gameSource)" in JS
    assert "function productionDiamondState(source, gameSource)" in JS
    for field in ("shotClock", "homeFouls", "visitorFouls", "homeBonus"):
        assert field in JS
    for field in ("inning", "inningHalf", "balls", "strikes", "outs", "bases",
                  "pitcherName", "batterName", "batterPosition"):
        assert field in JS


def test_merge_body_dispatches_and_keeps_the_football_branch_verbatim() -> None:
    body = _merge_body()
    assert "const sportFamily = productionSportFamily(base.sport);" in body
    assert 'base.game.sportFamily = sportFamily;' in body
    assert 'if (sportFamily === "football") {' in body
    # football branch still does exactly what it did before
    for line in (
        "const productionDown = productionDownDistance(source);",
        "base.game.downDistance = productionDown.combined;",
        "const field = productionFieldState(source, gameSource, source.canonical_field_state);",
        "base.game.field = field;",
        "base.game.field_direction = field.direction;",
        "base.game.possession = textValue(source.possession, gameSource.possession, base.game.possession).toLowerCase();",
    ):
        assert line in body


def test_non_football_branches_strip_football_keys() -> None:
    body = _merge_body()
    assert "FOOTBALL_GAME_KEYS" in body
    assert "FOOTBALL_GAME_KEYS.forEach(key => { delete base.game[key]; });" in body
    assert 'if (sportFamily === "basketball") {' in body
    assert "Object.assign(base.game, productionBasketballState(source, gameSource));" in body
    assert "Object.assign(base.game, productionDiamondState(source, gameSource));" in body
    # baseball/softball drop possession entirely
    assert "delete base.game.possession;" in body
