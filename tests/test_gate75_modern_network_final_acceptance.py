from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
JS=(ROOT/"static/csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
CSS=(ROOT/"static/csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
LAB=(ROOT/"static/csrn-layout-lab.html").read_text(encoding="utf-8")

def test_modern_baseball_matches_approved_row_order():
    block=JS[JS.index("function modernBaseballTeam"):JS.index("function modernBaseballScore")]
    assert block.index("bl-modern-run-cell") < block.index("logoMarkup(team,side)")
    assert block.index("logoMarkup(team,side)") < block.index("bl-team-copy")
    assert block.index("bl-team-copy") < block.index("bl-modern-baseball-role")
    assert 'data-module="${side}.role"' in block

def test_modern_baseball_uses_dedicated_nonoverlapping_columns():
    assert "grid-template-columns:112px 72px minmax(220px,1fr) minmax(210px,270px)" in CSS
    assert ".bl-modern-baseball .bl-modern-baseball-role{" in CSS
    assert "text-overflow:ellipsis" in CSS

def test_lab_has_live_sport_state_controls():
    for marker in ('id="possession"','id="inningHalf"','id="inningNumber"','id="loadSuiteTeams"','id="homeLogo"','id="visitorLogo"'):
        assert marker in LAB
    assert "normalizeSuiteState" in LAB
    assert "applyLabState" in LAB
    assert "syncSportControls" in LAB

def test_lab_asset_contract_is_v8():
    assert LAB.count("csrn-broadcast-layout-engine.js?v=11")==1
    assert LAB.count("csrn-broadcast-layout-engine.css?v=11")==1

def test_football_possession_visual_contract_remains():
    assert 'data-possession="${possession}"' in JS
    assert 'data-possession="home"' in CSS
    assert 'data-possession="visitor"' in CSS
    assert '::after' in CSS and '::before' in CSS


