from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_engine_uses_explicit_home_and_visitor_semantics() -> None:
    source = read("static/csrn-broadcast-layout-engine.js")
    assert "function explicitTeam(" in source
    assert 'data-module="${side}.identity"' in source
    assert '["logo","copy","score"]' in source
    assert '["score","copy","logo"]' in source


def test_scorebugs_have_sport_owned_structures() -> None:
    source = read("static/csrn-broadcast-layout-engine.js")
    css = read("static/csrn-broadcast-layout-engine.css")
    assert "function baseballLineScore(" in source
    assert "bl-press-boxscore" in source
    assert "bl-stadium-baseball" in source
    assert "bl-pixel-sport-rail" in source
    for sport in ("football", "basketball", "baseball", "softball"):
        assert f"bl-sport-${{sport}}" in source
    assert ".bl-pixel.bl-sport-football" in css
    assert ".bl-pixel.bl-sport-basketball" in css
    assert ".bl-pixel.bl-sport-baseball" in css


def test_layout_lab_contains_isolated_scorebug_composer() -> None:
    lab = read("static/csrn-layout-lab.html")
    for marker in (
        'id="editMode"',
        'id="inspector"',
        'id="moduleX"',
        'id="moduleY"',
        'id="moduleW"',
        'id="moduleH"',
        'id="stressCase"',
        'id="exportDraft"',
        "csrn.scorebug-layout-profile.v1",
        "localStorage",
    ):
        assert marker in lab


def test_production_overlay_remains_on_gate6_renderer() -> None:
    overlay = read("templates/overlay.html")
    assert "csrn-broadcast-layout-engine.js" not in overlay
    assert "csrn-scorebug-engine.js" in overlay


def test_gate72_scorebug_stabilization_contracts() -> None:
    source = read("static/csrn-broadcast-layout-engine.js")
    css = read("static/csrn-broadcast-layout-engine.css")
    lab = read("static/csrn-layout-lab.html")
    assert "function auditRenderedScorebug(" in source
    assert 'data-module="${side}.score"' in source
    assert "bl-neon-five-zone-diamond" in source
    assert ".bl-baseball-board.bl-modern .bl-baseball-state" in css
    assert ".bl-minimal-teams>div:first-child" in css
    assert ".bl-press-boxscore .bl-baseball-state" in css
    assert ".bl-baseball-board.bl-collegiate" in css
    assert ".bl-baseball-board.bl-classic" in css
    assert 'id="moduleSelect"' in lab
    assert "auditRenderedScorebug" in lab
    assert "csrn-broadcast-layout-engine.js?v=11" in lab
    assert "csrn-broadcast-layout-engine.css?v=11" in lab


def test_scorebug_audit_uses_structural_module_boundaries() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    assert "const parentModule = node.parentElement?.closest?.('[data-module]')" in source
    assert 'if (parentModule && scorebug.contains(parentModule)) continue;' in source
    assert 'const tolerance = 4;' in source
    assert 'delete node.dataset.textOverflow;' in source


def test_layout_lab_uses_ascii_runtime_status_separators() -> None:
    lab = (ROOT / "static" / "csrn-layout-lab.html").read_text(encoding="utf-8")
    assert "Choose module..." in lab
    assert " · " not in lab
    assert "…" not in lab


