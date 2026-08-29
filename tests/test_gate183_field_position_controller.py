from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / 'templates' / 'index.html').read_text(encoding='utf-8')
STYLE = (ROOT / 'static' / 'style.css').read_text(encoding='utf-8')
APP = (ROOT / 'app.py').read_text(encoding='utf-8')
OPS = (ROOT / 'game_operations_service.py').read_text(encoding='utf-8')


def test_field_position_controller_exists_on_both_operator_surfaces():
    assert 'id="broadcasterFieldPosition"' in INDEX
    assert 'id="statisticianFieldPosition"' in INDEX
    assert 'type="range" min="1" max="99" step="1"' in INDEX


def test_field_controller_commits_through_authoritative_correction_boundary():
    assert "api('/api/game-correction'" in INDEX
    assert "note:'Field position controller'" in INDEX
    assert "source,down:currentState.down" in INDEX


def test_game_context_box_uses_canonical_yards_to_goal_not_territory_regex():
    # The drive/down box (#rulesContext) must derive yards-to-goal /
    # red-zone from canonical_field_state (measured toward the end zone the
    # offense is driving toward), NOT the old regex that flagged RED ZONE
    # for the ball being near *either* goal line.
    assert "currentState.canonical_field_state" in INDEX
    assert "cfs.yards_to_goal" in INDEX
    assert "${toGoal} to goal" in INDEX
    assert r"/VISITOR ([1-9]|1\d|20)$/" not in INDEX  # dead, wrong-reference regex removed


def test_drive_direction_is_integrated_with_field_controller():
    assert "setFieldDrive('broadcaster','left')" in INDEX
    assert "setFieldDrive('statistician','right')" in INDEX
    assert "GameStateManager.mutate('/api/field-direction'" in INDEX


def test_broadcaster_can_toggle_ball_spot_visibility_without_erasing_spot():
    assert "setState('ball_spot_visible',true)" in INDEX
    assert "setState('ball_spot_visible',false)" in INDEX
    assert '"ball_spot_visible": True' in APP
    assert '"ball_spot_visible",' in OPS


def test_undo_is_promoted_near_primary_scoring_controls():
    assert 'class="button-row primary-undo-row"' in INDEX
    assert INDEX.index('primary-undo-row') < INDEX.index('id="broadcasterStateControls"')


def test_field_controller_has_mobile_touch_friendly_visual_contract():
    assert '.football-field-slider' in STYLE
    assert '.field-ball-marker' in STYLE
    assert '@media(max-width:760px)' in STYLE


