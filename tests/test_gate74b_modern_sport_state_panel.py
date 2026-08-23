from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / 'static' / 'csrn-broadcast-layout-engine.js').read_text(encoding='utf-8')
CSS = (ROOT / 'static' / 'csrn-broadcast-layout-engine.css').read_text(encoding='utf-8')
LAB = (ROOT / 'static' / 'csrn-layout-lab.html').read_text(encoding='utf-8')


def test_layout_lab_uses_gate74b_assets() -> None:
    assert LAB.count('csrn-broadcast-layout-engine.js?v=11') == 1
    assert LAB.count('csrn-broadcast-layout-engine.css?v=11') == 1


def test_modern_baseball_uses_dedicated_renderer() -> None:
    assert 'function modernBaseballScore(state)' in JS
    assert 'return modernBaseballScore(state);' in JS
    assert 'bl-modern-baseball' in JS


def test_home_and_visitor_labels_live_in_run_cells() -> None:
    assert 'const label = side === "home" ? "HOME" : "VISITOR";' in JS
    assert 'class="bl-run-label"' in JS
    assert 'class="bl-modern-run-cell"' in JS
    assert 'bl-modern-run-cell{display:grid;grid-template-rows:23px minmax(0,1fr)' in CSS


def test_baseball_roles_follow_inning_half() -> None:
    assert 'const battingSide = half === "TOP" ? "visitor" : "home";' in JS
    assert 'const fieldingSide = battingSide === "home" ? "visitor" : "home";' in JS
    assert 'data-role="at-bat"' in JS
    assert 'data-role="pitcher"' in JS
    assert '<b>AB:</b>' in JS
    assert '<b>P:</b>' in JS


def test_baseball_future_identity_fields_are_present() -> None:
    for field in ('pitcherName', 'batterName', 'batterPosition'):
        assert field in JS
    assert 'pitcherName: "RYAN LITHERS"' in JS
    assert 'batterName: "TOMMY GUNNS"' in JS
    assert 'batterPosition: "2B"' in JS


def test_modern_baseball_height_and_score_containment() -> None:
    assert '.bl-modern-baseball{height:176px;' in CSS
    assert 'font-size:clamp(36px,2.8vw,50px)' in CSS
    assert 'grid-template-columns:112px 72px minmax(220px,1fr) minmax(210px,270px)' in CSS


def test_state_panel_is_lowered_without_leaving_frame() -> None:
    assert 'padding:30px 10px 10px' in CSS
    assert 'grid-template-columns:1fr 1.25fr 86px' in CSS


def test_modern_football_restores_corner_football_and_highlight() -> None:
    assert 'data-possession="${possession}"' in JS
    assert '.bl-modern.bl-sport-football[data-possession="home"] .bl-home' in CSS
    assert '.bl-modern.bl-sport-football[data-possession="visitor"] .bl-visitor' in CSS
    assert 'border-radius:52%' in CSS
    assert 'box-shadow:0 0 0 3px rgba(255,255,255,.92)' in CSS


def test_old_bottom_possession_bar_is_visually_hidden_for_modern_football() -> None:
    assert '.bl-modern.bl-sport-football .bl-possession{' in CSS
    assert 'clip-path:inset(50%)' in CSS


