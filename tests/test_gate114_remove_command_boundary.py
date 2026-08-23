from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENGINE = ROOT / "static" / "csrn-broadcast-layout-engine.js"
CSS = ROOT / "static" / "csrn-broadcast-layout-engine.css"


def neon_core_source() -> str:
    source = ENGINE.read_text(encoding="utf-8")
    return source[source.index("function neonCorePanel") : source.index("function normalizePossession")]


def test_gate114_command_core_is_not_an_editable_module_boundary() -> None:
    source = neon_core_source()
    assert 'class="bl-neon-command-core bl-neon-command-diamond" data-module=' not in source
    assert 'class="bl-neon-command-core" data-module=' not in source
    assert ".replace(' data-module=\"game.state\"','')" in source


def test_gate114_live_game_bindings_remain_available() -> None:
    source = ENGINE.read_text(encoding="utf-8")
    for binding in (
        'data-bind="game.period"',
        'data-bind="game.clock"',
        'data-bind="game.downDistance"',
        'data-bind="game.possession"',
        'data-bind="game.inningHalf"',
        'data-bind="game.inning"',
    ):
        assert binding in source


def test_gate114_defensively_suppresses_descendant_outlines() -> None:
    css = CSS.read_text(encoding="utf-8")
    closeout = css[css.index("/* Gate 11.4 — Command core is display-only, never an editable boundary. */") :]
    assert ".bl-neon-command-core *{" in closeout
    assert "outline:none!important" in closeout
    assert "outline-width:0!important" in closeout
    assert "outline-color:transparent!important" in closeout


