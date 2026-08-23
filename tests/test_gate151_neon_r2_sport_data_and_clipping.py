from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_football_field_numbers_are_large_upright_and_inside_canvas() -> None:
    css = (ROOT / "static" / "csrn-neon-r2-engine.css").read_text(encoding="utf-8")
    assert ".n2-lower-assembly" in css
    assert ".n2-yard-numbers span" in css
    assert "rotate(180deg)" not in css
    assert ".n2-lower-assembly" in css

def test_basketball_exposes_fouls_and_bonus_without_possession_or_shot_clock() -> None:
    js = (ROOT / "static" / "csrn-neon-r2-engine.js").read_text(encoding="utf-8")
    for required in ("homeFouls", "visitorFouls", "homeBonus", "visitorBonus"):
        assert required in js
    basketball = js[js.index("function basketballState"):js.index("function diamondState")]
    assert "HOME BALL" not in basketball
    assert "VISITOR BALL" not in basketball
    assert "SHOT" not in basketball
    css = (ROOT / "static" / "csrn-neon-r2-engine.css").read_text(encoding="utf-8")
    assert ".n2-basket-court" in css


def test_diamond_scoreboard_has_no_redundant_title_and_fits_canvas() -> None:
    js = (ROOT / "static" / "csrn-neon-r2-engine.js").read_text(encoding="utf-8")
    assert "INNING SCOREBOARD" not in js
    css = (ROOT / "static" / "csrn-neon-r2-engine.css").read_text(encoding="utf-8")
    assert ".n2-lower-assembly" in css
    assert "table-layout:fixed" in css

def test_nonfootball_clashes_receive_stronger_color_pass() -> None:
    css = (ROOT / "static" / "csrn-neon-r2-engine.css").read_text(encoding="utf-8")
    assert "mix-blend-mode:color" in css
    assert "opacity:.38" in css


