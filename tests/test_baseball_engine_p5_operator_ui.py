"""Baseball engine P5 (docs/BASEBALL_SOFTBALL_ENGINE_SCOPING_PLAN.md P5 row):
operator UI. Text-assertion style tests matching this repo's existing
convention for templates/static content (test_gate5_frozen_football_scope.py,
test_gate6_visual_regression.py, ...) rather than a browser/DOM harness --
there is no such harness in this project. Also cross-checks the JS's action
names against diamond_game_operations_service.ACTIONS so a typo'd action
name in the wizard can never silently 404 in production.
"""

from __future__ import annotations

import re
from pathlib import Path

import diamond_game_operations_service as svc

ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_sport_dropdown_offers_baseball_and_softball() -> None:
    index = read("templates/index.html")
    assert '<select id="sport" onchange="syncCreateBroadcastRulesetOptions()">' in index
    assert "<option>Baseball</option>" in index
    assert "<option>Softball</option>" in index
    # Basketball stays a real, disabled "(future)" placeholder -- only
    # baseball/softball graduated out of that state this round.
    assert "<option disabled>Basketball (future)</option>" in index
    assert "<option disabled>Baseball (future)</option>" not in index
    assert "<option disabled>Softball (future)</option>" not in index


def test_diamond_script_is_loaded() -> None:
    index = read("templates/index.html")
    assert '<script src="/static/csrn-diamond-controls.js?v=diamond-p5-r1"></script>' in index


def test_diamond_control_panel_has_every_p5_scoping_row_deliverable() -> None:
    # P5 row: "PA outcome entry, between-PA events, ruling workflow,
    # substitution wizard ... lineup editor, manual set-value."
    index = read("templates/index.html")
    assert 'id="diamondControlPanel"' in index
    assert 'id="diamondLineupSetup"' in index  # lineup editor
    assert 'id="paBatter"' in index and 'id="paResultCode"' in index  # PA entry
    assert 'id="lwAction"' in index  # substitution/lineup-change wizard
    assert 'id="rulingBaseAwards"' in index  # ruling workflow
    assert 'id="diamondBattingOrderAlerts"' in index  # BOO detection/appeal (P2)
    assert 'id="diamondBoxScoreModal"' in index


def test_diamond_control_panel_exposes_undo_redo_suspend_resume_confirm_end() -> None:
    index = read("templates/index.html")
    assert 'onclick="diamondUndo()"' in index
    assert 'onclick="diamondRedo()"' in index
    assert 'onclick="diamondSuspend()"' in index
    assert 'onclick="diamondResume()"' in index
    assert 'onclick="diamondConfirmGameEnd()"' in index
    assert 'onclick="openDiamondBoxScore()"' in index


def test_render_branches_on_diamond_sport_before_football_rendering() -> None:
    index = read("templates/index.html")
    # The branch must appear before football's own homeName/visitorName
    # assignment inside render() -- otherwise a baseball state (missing
    # quarter/down/distance/possession/coin_toss/...) would be run through
    # football-specific rendering code that assumes those fields exist.
    render_start = index.index("function render() {")
    branch_at = index.index("isDiamondSport", render_start)
    football_only_at = index.index("document.getElementById('homePossessionButton')", render_start)
    assert render_start < branch_at < football_only_at
    assert "renderDiamondControlPanel" in index[render_start:football_only_at]


def test_football_only_sections_are_hidden_for_diamond_sport() -> None:
    index = read("templates/index.html")
    render_start = index.index("function render() {")
    render_body = index[render_start:index.index("\nfunction ", render_start + 10)]
    for element_id in (
        "broadcasterStateControls", "broadcasterGameDataControls",
        "broadcasterPossessionStrip", "broadcasterUndoRow",
    ):
        assert f"getElementById('{element_id}')?.classList.toggle('hidden', isDiamondSport)" in render_body


DIAMOND_JS_FUNCTIONS = (
    "renderDiamondControlPanel",
    "diamondRenderLineupBuilder", "diamondStartLineup",
    "diamondRenderSlotInfo", "diamondSubmitLineupAction",
    "diamondRecordPlateAppearance",
    "diamondRecordRuling",
    "diamondRecordBatter", "diamondApplyAppealRuling", "diamondDismissAlert",
    "diamondUndo", "diamondRedo", "diamondSuspend", "diamondResume", "diamondConfirmGameEnd",
    "openDiamondBoxScore", "closeDiamondBoxScore",
    "syncCreateBroadcastRulesetOptions",
)


def test_diamond_controls_js_defines_every_control_function() -> None:
    js = read("static/csrn-diamond-controls.js")
    for name in DIAMOND_JS_FUNCTIONS:
        assert f"function {name}(" in js, name


def test_diamond_controls_js_never_touches_football_broadcasts() -> None:
    js = read("static/csrn-diamond-controls.js")
    assert "function diamondIsActive()" in js
    assert "['baseball', 'softball'].includes" in js
    # Every render entry point bails out immediately for a non-diamond sport.
    assert "if (!diamondIsActive()) return;" in js


def _ui_action_names() -> set[str]:
    js = read("static/csrn-diamond-controls.js")
    literal = set(re.findall(r"diamondAction\('([a-z_]+)'", js))
    index = read("templates/index.html")
    lw_action_block = index[index.index('id="lwAction"'):index.index("</select>", index.index('id="lwAction"'))]
    dynamic = set(re.findall(r'value="([a-z_]+)"', lw_action_block))
    return literal | dynamic


def test_every_ui_action_name_is_a_real_registered_action() -> None:
    # Cross-file consistency: a typo'd action name in the wizard's <option>
    # values or a diamondAction('...') call would otherwise fail silently
    # in the browser (a 404 the operator sees only at the worst moment) --
    # this pins the two files' action vocabularies together.
    ui_actions = _ui_action_names()
    assert len(ui_actions) >= 26
    unknown = ui_actions - set(svc.ACTIONS.keys())
    assert not unknown, f"UI references unknown diamond actions: {unknown}"


def test_lineup_wizard_covers_every_lineup_service_transition() -> None:
    # Spec's own guided-wizard requirement (P5 row): substitution vs
    # re-entry vs position-change vs DH vs DP-FLEX vs courtesy runner vs
    # team-level actions must all be reachable, not just a subset.
    ui_actions = _ui_action_names()
    expected = {
        "substitute", "reenter", "position_change", "replace_on_defense_only",
        "terminate_player_dh_role", "start_dp_flex", "dp_plays_defense_for_flex",
        "flex_bats_for_dp", "dp_reenters", "substitute_for_dp", "substitute_for_flex",
        "enter_courtesy_runner", "return_courtesy_runner",
        "record_defensive_meeting", "record_charged_conference",
    }
    assert expected.issubset(ui_actions)


def test_umpire_ruling_form_matches_apply_ruling_payload_shape() -> None:
    # diamond_state_service.apply_ruling() reads baseAwards/outsAwarded/
    # ballStatus -- not the free-text "ruling type" shape an earlier draft
    # of this form used, which apply_ruling() would have silently ignored.
    js = read("static/csrn-diamond-controls.js")
    assert "baseAwards" in js
    assert "outsAwarded" in js
    assert "ballStatus" in js
    assert "fromBase" in js and "toBase" in js
