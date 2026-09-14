"""Basketball engine P5 (docs/BASKETBALL_ENGINE_SCOPING_PLAN.md P5 row):
operator UI. Text-assertion style tests matching this repo's existing
convention for templates/static content (see e.g.
test_baseball_engine_p5_operator_ui.py) rather than a browser/DOM harness
-- there is no such harness in this project. Also cross-checks the JS's
action names against hoops_game_operations_service.ACTIONS so a typo'd
action name can never silently 404 in production.
"""

from __future__ import annotations

import re
from pathlib import Path

import hoops_game_operations_service as svc
import hoops_rules_service

ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_sport_dropdown_offers_basketball() -> None:
    index = read("templates/index.html")
    assert "<option>Basketball</option>" in index
    assert "<option disabled>Basketball (future)</option>" not in index


def test_hoops_controls_partial_is_included_and_script_is_loaded() -> None:
    index = read("templates/index.html")
    # A genuine partial-file include (Sec.9.2's own collision-avoidance
    # plan), not a direct inline section the way baseball's own diamond
    # panel was built -- index.html's own diff for this is a single line.
    assert '{% include "_hoops_controls.html" %}' in index
    assert '<script src="/static/csrn-hoops-controls.js?v=hoops-p5-r1"></script>' in index


def test_hoops_controls_partial_has_every_engine_backed_deliverable() -> None:
    partial = read("templates/_hoops_controls.html")
    assert 'id="hoopsControlPanel"' in partial
    assert 'id="hoopsLineupSetup"' in partial          # starting five
    assert 'id="suOut"' in partial and 'id="suIn"' in partial  # substitution
    assert 'id="shShooter"' in partial                  # shot
    assert 'id="ftShooter"' in partial                  # free throw
    assert 'id="rbPlayer"' in partial                   # rebound
    assert 'id="flType"' in partial                     # foul (with type)
    assert 'id="toTeam"' in partial                     # turnover / held ball
    assert 'id="vlType"' in partial                     # violation
    assert 'onclick="hoopsTimeout(' in partial           # timeout
    assert 'id="rlScoreTeam"' in partial                 # ruling
    assert 'id="svField"' in partial                     # manual set-value
    assert 'id="hoopsBoxScoreModal"' in partial


def test_hoops_controls_partial_exposes_undo_redo_and_confirm_end() -> None:
    partial = read("templates/_hoops_controls.html")
    assert 'onclick="hoopsUndo()"' in partial
    assert 'onclick="hoopsRedo()"' in partial
    assert 'onclick="hoopsConfirmGameEnd()"' in partial
    assert 'onclick="openHoopsBoxScore()"' in partial


def test_render_branches_on_hoops_sport_before_football_rendering() -> None:
    index = read("templates/index.html")
    # The branch must appear before football's own homeName/visitorName
    # assignment inside render() -- otherwise a basketball state (missing
    # quarter/down/distance/possession/coin_toss/...) would be run through
    # football-specific rendering code that assumes those fields exist.
    render_start = index.index("function render() {")
    branch_at = index.index("isHoopsSport", render_start)
    football_only_at = index.index("document.getElementById('homePossessionButton')", render_start)
    assert render_start < branch_at < football_only_at
    assert "renderHoopsControlPanel" in index[render_start:football_only_at]


def test_football_only_sections_are_hidden_for_hoops_sport() -> None:
    index = read("templates/index.html")
    render_start = index.index("function render() {")
    render_body = index[render_start:index.index("\nfunction ", render_start + 10)]
    for element_id in (
        "broadcasterStateControls", "broadcasterGameDataControls",
        "broadcasterPossessionStrip", "broadcasterUndoRow",
    ):
        assert f"getElementById('{element_id}')?.classList.toggle('hidden', isHoopsSport)" in render_body


HOOPS_JS_FUNCTIONS = (
    "renderHoopsControlPanel",
    "hoopsRenderLineupBuilder", "hoopsSetStartingFive",
    "hoopsPopulateOnFloorSelects", "hoopsPopulateSubstituteSelects", "hoopsSubstitute",
    "hoopsRecordShot", "hoopsRecordFreeThrow", "hoopsRecordRebound", "hoopsRecordFoul",
    "hoopsRecordTurnover", "hoopsRecordHeldBall", "hoopsRecordViolation",
    "hoopsTimeout", "hoopsRecordRuling", "hoopsSetValue",
    "hoopsUndo", "hoopsRedo", "hoopsConfirmGameEnd",
    "openHoopsBoxScore", "closeHoopsBoxScore",
)


def test_hoops_controls_js_defines_every_control_function() -> None:
    js = read("static/csrn-hoops-controls.js")
    for name in HOOPS_JS_FUNCTIONS:
        assert f"function {name}(" in js, name


def test_hoops_controls_js_never_touches_non_basketball_broadcasts() -> None:
    js = read("static/csrn-hoops-controls.js")
    assert "function hoopsIsActive()" in js
    assert "'basketball'" in js
    # Every render entry point bails out immediately for a non-basketball sport.
    assert "if (!hoopsIsActive()) return;" in js


def _ui_action_names() -> set[str]:
    js = read("static/csrn-hoops-controls.js")
    return set(re.findall(r"hoopsAction\('([a-z_]+)'", js)) | set(
        re.findall(r"api\('/api/hoops/action/([a-z_]+)'", js)
    )


def test_every_ui_action_name_is_a_real_registered_action() -> None:
    # Cross-file consistency: a typo'd action name would otherwise fail
    # silently in the browser (a 404 the operator sees only at the worst
    # moment) -- this pins the two files' action vocabularies together.
    ui_actions = _ui_action_names()
    assert len(ui_actions) >= 12
    unknown = ui_actions - set(svc.ACTIONS.keys())
    assert not unknown, f"UI references unknown hoops actions: {unknown}"


def test_ui_covers_every_engine_backed_action_except_the_deliberately_deferred_ones() -> None:
    # correct_foul/void_event/correct_event have no dedicated UI in P5,
    # same deliberate scope cut baseball's own P5 made for its own
    # void_event/correct_event -- undo/redo covers the "runs a full game"
    # bar; targeted correction is a power-user feature for later.
    ui_actions = _ui_action_names()
    deferred = {"correct_foul", "void_event", "correct_event"}
    assert set(svc.ACTIONS.keys()) - ui_actions == deferred


def test_shot_form_matches_apply_shot_payload_shape() -> None:
    # hoops_state_service.apply_shot() reads team/made/points/shooterId/
    # assistId/andOne (plus the box score's own additive blockPlayerId) --
    # not a differently-shaped payload an earlier draft might invent.
    js = read("static/csrn-hoops-controls.js")
    assert "shooterId" in js and "assistId" in js and "blockPlayerId" in js and "andOne" in js


def test_foul_form_matches_foul_payload_shape() -> None:
    js = read("static/csrn-hoops-controls.js")
    assert "foulType" in js
    assert "isShootingFoul" in js
    assert "shotPoints" in js


def test_violation_form_matches_apply_violation_payload_shape() -> None:
    js = read("static/csrn-hoops-controls.js")
    assert "violationType" in js
    assert "possessionTo" in js


def test_ruling_form_matches_apply_ruling_payload_shape() -> None:
    # hoops_state_service.apply_ruling() reads scoreAdjustment/possessionTo/
    # clockSecondsAdjustment -- basketball's own general ruling shape
    # (documented as such, not a transcription of an existing spec section).
    js = read("static/csrn-hoops-controls.js")
    assert "scoreAdjustment" in js
    assert "clockSecondsAdjustment" in js


def test_set_value_form_only_offers_fields_the_engine_actually_accepts() -> None:
    partial = read("templates/_hoops_controls.html")
    field_block = partial[partial.index('id="svField"'):partial.index("</select>", partial.index('id="svField"'))]
    ui_fields = set(re.findall(r'value="([a-z_]+)"', field_block))
    assert ui_fields == set(hoops_rules_service._SETTABLE_FIELDS.keys())
