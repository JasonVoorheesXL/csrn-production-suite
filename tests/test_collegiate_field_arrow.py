"""The Collegiate Tech direction arrow: its own stylesheet, loaded by Collegiate Tech and not Neon."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = (ROOT / "static/csrn-production-theme-runtime.js").read_text(encoding="utf-8")
ARROW = (ROOT / "static/csrn-collegiate-field-arrow.css").read_text(encoding="utf-8")


def test_only_collegiate_tech_loads_the_arrow():
    assert RUNTIME.count("/static/csrn-collegiate-field-arrow.css?v=1") == 1
    neon = RUNTIME[RUNTIME.index("csrn-collegiate-neon.css"):RUNTIME.index("collegiate_traditional: Object.freeze")]
    assert "field-arrow" not in neon


def test_every_rule_is_scoped_to_collegiate_tech():
    rules = [line for line in ARROW.splitlines() if "{" in line]
    assert rules and all(line.startswith(".package-collegiate .bl-college-") for line in rules)


def test_driving_left_mirrors_the_arrow_to_the_other_side_of_the_ball():
    assert 'data-direction="left"] .bl-college-direction-arrow{left:calc(var(--ball-x) - 21px);width:min(112px,calc(var(--ball-x) - 25px));transform:translate(-100%,-50%) scaleX(-1)}' in ARROW
