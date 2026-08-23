from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / "static" / "csrn-broadcast-layout-engine.css"


def gate113_css() -> str:
    css = CSS.read_text(encoding="utf-8")
    return css[css.index("/* Gate 11.3 — Final center-boundary and support-copy legibility pass. */") :]


def test_gate113_removes_every_command_core_rectangle_path() -> None:
    css = gate113_css()
    assert ".csrn-broadcast-layout.package-neon-approved .bl-neon-command-core," in css
    assert ".package-neon-approved.diagnostics .bl-neon-command-core" in css
    for rule in (
        "border:0!important",
        "outline:0!important",
        "box-shadow:none!important",
        "filter:none!important",
        "border-color:transparent!important",
    ):
        assert rule in css


def test_gate113_larger_circled_support_copy_is_fifty_percent_larger() -> None:
    css = gate113_css()
    assert ".bl-neon-player-copy span{" in css and "font-size:21px" in css
    assert ".bl-neon-highlight-copy span{" in css and "font-size:22.5px" in css


def test_gate113_smaller_stat_copy_is_seventy_five_percent_larger() -> None:
    css = gate113_css()
    assert ".bl-neon-stat-grid small{" in css and "font-size:15.75px" in css
    assert ".bl-neon-stat-grid b{" in css and "font-size:36.75px" in css
    assert "grid-template-columns:repeat(4,1fr)" in CSS.read_text(encoding="utf-8")


