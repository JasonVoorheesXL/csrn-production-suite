from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_modern_baseball_uses_explicit_team_owned_rows() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    assert "function modernBaseballTeam(" in source
    assert "function modernBaseballScore(" in source
    assert 'modernBaseballTeam(state,state.home,"home")' in source
    assert 'modernBaseballTeam(state,state.visitor,"visitor")' in source
    assert 'return modernBaseballScore(state)' in source
    assert 'class="bl-modern-run-cell"' in source
    assert 'const label = side === "home" ? "HOME" : "VISITOR";' in source
    assert 'class="bl-run-label">${label}</span>' in source


def test_modern_baseball_has_fixed_score_and_state_columns() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    assert ".bl-modern-baseball{" in css
    assert "grid-template-columns:minmax(0,1fr) 330px" in css
    assert ".bl-modern-baseball .bl-baseball-team{" in css
    assert "grid-template-columns:112px 72px minmax(220px,1fr) minmax(210px,270px)" in css
    assert ".bl-modern-baseball .bl-modern-run-cell{" in css
    assert ".bl-modern-baseball .bl-baseball-state{" in css


def test_modern_football_and_basketball_contract_is_preserved() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    assert 'return `<div class="bl-scorebug bl-modern bl-sport-${sport}" data-possession="${possession}">' in source
    assert "${sportState(state,sport)}" in source
    assert "modern_network:" in source


def test_layout_lab_advances_modern_visual_asset_contract() -> None:
    lab = (ROOT / "static" / "csrn-layout-lab.html").read_text(encoding="utf-8")
    assert lab.count("csrn-broadcast-layout-engine.js?v=11") == 1
    assert lab.count("csrn-broadcast-layout-engine.css?v=11") == 1


