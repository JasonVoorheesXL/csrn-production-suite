from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "static" / "csrn-broadcast-layout-engine.js"
CSS = ROOT / "static" / "csrn-broadcast-layout-engine.css"


def source() -> str:
    return ENGINE.read_text(encoding="utf-8")


def refinement_css() -> str:
    css = CSS.read_text(encoding="utf-8")
    return css[css.index("/* Gate 11.1 — Approved Concept Clarity and Team-Energy Refinement. */") :]


def test_gate111_support_modules_receive_the_live_team_palette() -> None:
    assert source().count(
        'data-neon-surface="dark-system" ${neonPackageStyle(state)}'
    ) == 5


def test_gate111_removes_the_continuous_scorebug_bars_without_changing_geometry() -> None:
    css = refinement_css()
    assert ".bl-neon-true-chassis::before" in css
    assert ".bl-neon-true-chassis::after" in css
    assert ".bl-neon-chassis-rail" in css
    assert "display:none!important" in css

    full_css = CSS.read_text(encoding="utf-8")
    assert "grid-template-columns:200px 350px 190px 360px 190px 350px 200px" in full_css
    assert "width:1840px" in full_css
    assert "height:250px" in full_css


def test_gate111_primary_scorebug_type_uses_crisp_restrained_glow() -> None:
    css = refinement_css()
    assert "-webkit-font-smoothing:antialiased" in css
    assert "text-rendering:geometricPrecision" in css
    assert (
        "text-shadow:0 3px 2px rgba(0,0,0,.96),0 0 5px "
        "rgba(var(--neon-team-rgb),.34)"
    ) in css
    assert (
        "text-shadow:0 2px 2px rgba(0,0,0,.96),0 0 4px "
        "rgba(235,250,255,.30)"
    ) in css
    assert "0 0 12px #fff" not in css
    assert "0 0 28px var(--neon-team)" not in css


def test_gate111_support_edges_use_home_and_visitor_energy() -> None:
    css = refinement_css()
    for token in (
        "--neon-module-left:var(--neon-home,#24d8ff)",
        "--neon-module-right:var(--neon-visitor,#39ff14)",
        "linear-gradient(90deg,var(--neon-module-left)",
        "rgba(var(--neon-module-right-rgb),.40)",
        "border-color:var(--neon-module-left)!important",
        "background:var(--neon-module-right)",
    ):
        assert token in css


def test_gate111_right_side_modules_use_the_visitor_accent() -> None:
    css = refinement_css()
    assert ".bl-neon-native-highlight," in css
    assert ".bl-neon-native-sponsor{" in css
    assert "--neon-module-accent:var(--neon-module-right)" in css
    assert ".bl-neon-highlight-copy small{color:var(--neon-module-right)}" in css


