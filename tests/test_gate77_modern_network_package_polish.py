from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def test_modern_all_sport_logo_treatment_is_rounded_glass():
    css=(ROOT/"static"/"csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    assert ".bl-modern .bl-logo{" in css
    assert "border-radius:15px" in css
    assert "backdrop-filter:blur(8px)" in css
    assert ".bl-modern-baseball .bl-logo{width:54px" in css

def test_modern_diamond_state_keeps_approved_width_and_alignment():
    css=(ROOT/"static"/"csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    assert ".bl-modern-baseball{" in css
    assert "grid-template-columns:minmax(0,1fr) 330px" in css
    assert "grid-template-columns:minmax(0,1fr) 88px" in css
    assert ".bl-modern-baseball .bl-inning{grid-column:1;grid-row:1" in css
    assert ".bl-modern-baseball .bl-count{grid-column:1;grid-row:2" in css
    assert ".bl-modern-baseball .bl-diamond{grid-column:2;grid-row:1/3" in css

def test_modern_football_and_basketball_state_panel_is_narrower():
    css=(ROOT/"static"/"csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    assert ".bl-modern:not(.bl-modern-baseball){grid-template-columns:minmax(0,1fr) 188px minmax(0,1fr)}" in css

def test_modern_possession_uses_team_color_with_scarlet_fallback():
    source=(ROOT/"static"/"csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    css=(ROOT/"static"/"csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    assert "function modernPossessionAccent(" in source
    assert 'return "#B5121B"' in source
    assert "--possession-accent:" in source
    assert "var(--possession-accent,#B5121B)" in css

def test_gate77_asset_contract_is_atomic():
    lab=(ROOT/"static"/"csrn-layout-lab.html").read_text(encoding="utf-8")
    source=(ROOT/"static"/"csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    assert lab.count("csrn-broadcast-layout-engine.js?v=11")==1
    assert lab.count("csrn-broadcast-layout-engine.css?v=11")==1
    assert 'const VERSION = "1.7.0"' in source


