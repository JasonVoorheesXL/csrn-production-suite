"""The Collegiate Tech field and direction arrow: their own stylesheet, loaded by Collegiate Tech and not Neon."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = (ROOT / "static/csrn-production-theme-runtime.js").read_text(encoding="utf-8")
FIELD = (ROOT / "static/csrn-collegiate-field.css").read_text(encoding="utf-8")


def test_only_collegiate_tech_loads_the_field_styles():
    assert RUNTIME.count("/static/csrn-collegiate-field.css?v=1") == 1
    neon = RUNTIME[RUNTIME.index("csrn-collegiate-neon.css"):RUNTIME.index("collegiate_traditional: Object.freeze")]
    assert "collegiate-field" not in neon


def test_every_rule_is_scoped_to_collegiate_tech():
    rules = [line for line in FIELD.splitlines() if "{" in line]
    assert rules and all(line.startswith(".package-collegiate .bl-college-") for line in rules)


def test_yard_numbers_are_centered_on_their_lines():
    assert "left:calc(var(--csrn-ez,5%) + (100% - 2 * var(--csrn-ez,5%)) * .05)" in FIELD


def test_driving_left_mirrors_the_arrow_to_the_other_side_of_the_ball():
    assert "scaleX(-1)" in FIELD and "left:calc(var(--ball-x) - 20px)" in FIELD
