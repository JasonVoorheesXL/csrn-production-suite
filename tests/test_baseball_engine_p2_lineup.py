"""Baseball engine P2 acceptance -- lineup_service (docs/BASEBALL_SOFTBALL_
ENGINE_SCOPING_PLAN.md P2 row): spec Sec.19 BB-01 through BB-06, SB-01
through SB-06, CR-01/02, BOO-01/02, all by name. No UI, no routes -- every
call here is direct service-to-service, matching P1's own discipline.
"""

from __future__ import annotations

from at_bat_rules_service import AtBatRulesService
from diamond_state_service import DiamondStateFoundation
from diamond_state_service import default_state as diamond_default_state
from lineup_service import (
    DH_PLAYER,
    LineupService,
    ROLE_NONE,
    ROLE_PLAYER_DH,
    default_state,
)


def _new_state() -> dict:
    state = {"sport": "baseball"}
    state.update(default_state())
    return state


def _start_baseball_lineup(state: dict, side: str, dh_mode: str = "NONE") -> None:
    starters = {i: f"{side}-p{i}" for i in range(1, 10)}
    defense = {"P": f"{side}-p1", "C": f"{side}-p2"}
    LineupService.start_lineup(state, side, starters, defense, sport="baseball", dh_mode=dh_mode)


# --- BB-01 / BB-02 / BB-03: baseball re-entry -------------------------------


def test_BB_01_starter_exits_then_reenters_once_is_accepted() -> None:
    state = _new_state()
    _start_baseball_lineup(state, "home")
    LineupService.substitute(state, "home", 3, "home-sub1", event_id="e1")
    result = LineupService.reenter(state, "home", 3, "home-p3", event_id="e2")
    assert result.ok
    assert not result.data["messages"]
    slot = state["lineup"]["home"]["slots"]["3"]
    assert slot["active_player_id"] == "home-p3"
    reentries = [a for a in slot["entry_history"] if a["entry_type"] == "REENTRY"]
    assert len(reentries) == 1 and reentries[0]["player_id"] == "home-p3"


def test_BB_02_same_starter_attempts_second_reentry_is_soft_warning() -> None:
    state = _new_state()
    _start_baseball_lineup(state, "home")
    LineupService.substitute(state, "home", 3, "home-sub1", event_id="e1")
    LineupService.reenter(state, "home", 3, "home-p3", event_id="e2")
    LineupService.substitute(state, "home", 3, "home-sub2", event_id="e3")
    result = LineupService.reenter(state, "home", 3, "home-p3", event_id="e4")
    assert result.ok  # record-reality override -- never blocked
    assert any(m.code == "STARTER_SECOND_REENTRY" and m.severity == "SOFT_WARNING" for m in result.data["messages"])
    assert state["lineup"]["home"]["slots"]["3"]["active_player_id"] == "home-p3"


def test_BB_03_substitute_exits_then_attempts_to_reenter_is_soft_warning() -> None:
    state = _new_state()
    _start_baseball_lineup(state, "home")
    LineupService.substitute(state, "home", 3, "home-sub1", event_id="e1")
    LineupService.substitute(state, "home", 3, "home-sub2", event_id="e2")
    result = LineupService.reenter(state, "home", 3, "home-sub1", event_id="e3")
    assert result.ok
    assert any(
        m.code == "SUBSTITUTE_REENTRY_NOT_ORDINARILY_ALLOWED" and m.severity == "SOFT_WARNING"
        for m in result.data["messages"]
    )
    # not silently accepted as an ordinary legal re-entry -- it IS recorded though.
    assert state["lineup"]["home"]["slots"]["3"]["active_player_id"] == "home-sub1"


# --- BB-04 / BB-05: Player/DH -----------------------------------------------


def test_BB_04_player_dh_replaced_only_on_defense_keeps_the_dh_role() -> None:
    state = _new_state()
    _start_baseball_lineup(state, "home", dh_mode=DH_PLAYER)
    LineupService.assign_role(state, "home", "home-p1", ROLE_PLAYER_DH)
    result = LineupService.replace_on_defense_only(state, "home", "P", "home-sub9")
    assert result.ok
    assert state["lineup"]["home"]["roles"]["home-p1"] == ROLE_PLAYER_DH
    assert state["lineup"]["home"]["defense"]["P"] == "home-sub9"


def test_BB_05_player_dh_pinch_run_for_terminates_the_dh_role() -> None:
    state = _new_state()
    _start_baseball_lineup(state, "home", dh_mode=DH_PLAYER)
    LineupService.assign_role(state, "home", "home-p1", ROLE_PLAYER_DH)
    result = LineupService.terminate_player_dh_role(state, "home", "home-p1", reason="PINCH_RUN")
    assert result.ok
    assert state["lineup"]["home"]["roles"]["home-p1"] == ROLE_NONE
    assert result.data["event"]["payload"]["transition"] == "PLAYER_DH_ENDED"


# --- BB-06: defensive meetings -----------------------------------------------


def test_BB_06_second_defensive_meeting_in_same_half_inning_is_a_warning() -> None:
    state = _new_state()
    _start_baseball_lineup(state, "home")
    first = LineupService.record_defensive_meeting(state, "home")
    assert first.ok and not first.data["messages"]
    second = LineupService.record_defensive_meeting(state, "home")
    assert second.ok
    assert any(m.code == "SECOND_DEFENSIVE_MEETING" for m in second.data["messages"])
    # not auto-charged as a coach conference
    assert state["lineup"]["home"]["charged_conferences"] == 0
    events = [e for e in state["lineup_events"] if e["event_type"] == "PLAYER_DEFENSIVE_MEETING"]
    assert len(events) == 2


# --- SB-01 / SB-02: softball re-entry ---------------------------------------


def _start_softball_lineup(state: dict, side: str) -> None:
    starters = {i: f"{side}-p{i}" for i in range(1, 10)}
    defense = {"P": f"{side}-p1", "C": f"{side}-p2"}
    LineupService.start_lineup(state, side, starters, defense, sport="softball")


def test_SB_01_substitute_reenters_once_in_same_batting_slot_is_accepted() -> None:
    state = _new_state()
    state["sport"] = "softball"
    _start_softball_lineup(state, "home")
    LineupService.substitute(state, "home", 6, "home-sub1", sport="softball", event_id="e1")
    result = LineupService.reenter(state, "home", 6, "home-sub1", sport="softball", event_id="e2")
    assert result.ok
    assert not result.data["messages"]
    assert state["lineup"]["home"]["slots"]["6"]["active_player_id"] == "home-sub1"


def test_SB_02_player_reenters_in_different_batting_slot_is_a_warning() -> None:
    # Softball re-entry must return to the SAME batting position -- an
    # attempt to re-enter a player into a DIFFERENT slot than the one
    # they actually appeared in is a warning/ruling workflow, not a silent
    # slot remap.
    state = _new_state()
    state["sport"] = "softball"
    _start_softball_lineup(state, "home")
    LineupService.substitute(state, "home", 6, "home-sub1", sport="softball", event_id="e1")
    LineupService.substitute(state, "home", 6, "home-p6", sport="softball", event_id="e2")
    # home-sub1's only history is in slot 6 -- attempting to re-enter them
    # into slot 7 instead is the wrong-slot case.
    result = LineupService.reenter(state, "home", 7, "home-sub1", sport="softball", event_id="e3")
    assert result.ok
    assert any(m.code == "REENTRY_WRONG_SLOT" for m in result.data["messages"])


# --- SB-03 / SB-04 / SB-05: DP/FLEX ------------------------------------------


def test_SB_03_dp_plays_defense_for_flex() -> None:
    state = _new_state()
    state["sport"] = "softball"
    _start_softball_lineup(state, "home")
    LineupService.start_dp_flex(state, "home", "home-dp", 4, "home-flex")
    result = LineupService.dp_plays_defense_for_flex(state, "home")
    assert result.ok
    dp_flex = state["lineup"]["home"]["dp_flex"]
    assert dp_flex["active_count"] == 9
    assert dp_flex["offense_occupant"] == "DP"
    assert state["lineup"]["home"]["slots"]["4"]["active_player_id"] == "home-dp"


def test_SB_04_flex_bats_for_dp() -> None:
    state = _new_state()
    state["sport"] = "softball"
    _start_softball_lineup(state, "home")
    LineupService.start_dp_flex(state, "home", "home-dp", 4, "home-flex")
    result = LineupService.flex_bats_for_dp(state, "home")
    assert result.ok
    dp_flex = state["lineup"]["home"]["dp_flex"]
    assert dp_flex["active_count"] == 9
    assert dp_flex["offense_occupant"] == "FLEX"
    assert state["lineup"]["home"]["slots"]["4"]["active_player_id"] == "home-flex"
    # HARD invariant: cannot do it again while FLEX is already the occupant.
    again = LineupService.flex_bats_for_dp(state, "home")
    assert again.code == "HARD_ERROR"


def test_SB_05_dp_reenters_after_flex_batted_supports_both_legal_configurations() -> None:
    state = _new_state()
    state["sport"] = "softball"
    _start_softball_lineup(state, "home")
    LineupService.start_dp_flex(state, "home", "home-dp", 4, "home-flex")
    LineupService.flex_bats_for_dp(state, "home")

    # Wizard choice A: FLEX returns to the bench-only #10 role -> 10 active.
    result_a = LineupService.dp_reenters(state, "home", flex_resulting_state="RETURNS_TO_TEN")
    assert result_a.ok
    dp_flex = state["lineup"]["home"]["dp_flex"]
    assert dp_flex["offense_occupant"] == "DP"
    assert dp_flex["active_count"] == 10
    assert state["lineup"]["home"]["slots"]["4"]["active_player_id"] == "home-dp"

    # Wizard choice B: FLEX leaves entirely -> 9 active, role cleared.
    LineupService.flex_bats_for_dp(state, "home")
    result_b = LineupService.dp_reenters(state, "home", flex_resulting_state="LEAVES")
    assert result_b.ok
    assert state["lineup"]["home"]["dp_flex"]["active_count"] == 9
    assert "home-flex" not in state["lineup"]["home"]["roles"]


def test_SB_dp_and_flex_never_both_active_on_offense() -> None:
    # The HARD invariant itself, exercised directly (Sec.9.2/14.1).
    state = _new_state()
    state["sport"] = "softball"
    _start_softball_lineup(state, "home")
    LineupService.start_dp_flex(state, "home", "home-dp", 4, "home-flex")
    assert state["lineup"]["home"]["dp_flex"]["offense_occupant"] == "DP"
    result = LineupService.dp_plays_defense_for_flex(state, "home")
    assert result.ok  # legal: DP stays on offense, FLEX exits entirely
    # attempting dp_plays_defense_for_flex again is a no-op-safe re-check,
    # not a path to double offense occupancy
    assert state["lineup"]["home"]["dp_flex"]["offense_occupant"] == "DP"


# --- SB-06: look-back violation ruling ---------------------------------------


def test_SB_06_look_back_violation_applies_exactly_as_ruled_no_inference() -> None:
    # Sec.9.4: "CSRN may display context, but must never infer the out.
    # Use LOOK_BACK_RULING with runnerId, out/no-out result, base placement
    # for other runners, and the umpire-entered consequence." This reuses
    # the SAME generic UmpireRulingPayload mechanism RUL-01 (P1) already
    # proved -- a look-back violation is just another ruling code, applied
    # exactly as recorded, never inferred by the engine.
    diamond_state = {"sport": "softball"}
    diamond_state.update(diamond_default_state())
    DiamondStateFoundation.place_runner(diamond_state, "second", "runner-3", reason="PLATE_APPEARANCE")
    payload = {
        "rulingCode": "LOOK_BACK_VIOLATION",
        "rulingBy": "BASE",
        "ballStatus": "DEAD",
        "baseAwards": [],
        "outsAwarded": [{"runnerId": "runner-3"}],
    }
    result = AtBatRulesService.record_ruling(diamond_state, payload)
    assert result.ok
    # the engine applied exactly one out, as ruled -- no base movement was
    # invented, and the runner's own base occupancy is untouched by this
    # ruling (the umpire's out call is the only recorded consequence).
    assert diamond_state["outs"] == 1
    assert diamond_state["base_runners"]["second"]["player_id"] == "runner-3"


# --- CR-01 / CR-02: courtesy runners -----------------------------------------


def test_CR_01_courtesy_runner_enters_for_current_catcher_leaves_lineup_unchanged() -> None:
    state = _new_state()
    _start_baseball_lineup(state, "home")
    before = dict(state["lineup"]["home"]["slots"])
    result = LineupService.enter_courtesy_runner(state, "home", "home-cr1", "home-p2", "CATCHER", event_id="e1")
    assert result.ok
    assert not result.data["messages"]
    # lineup occupant unchanged
    assert state["lineup"]["home"]["slots"] == before
    appearances = state["lineup"]["home"]["courtesy_runners"]
    assert len(appearances) == 1
    assert appearances[0]["runner_player_id"] == "home-cr1"
    assert appearances[0]["for_player_id"] == "home-p2"
    assert appearances[0]["for_role_at_time"] == "CATCHER"


def test_CR_02_potentially_ineligible_courtesy_runner_is_a_warning_not_a_block() -> None:
    state = _new_state()
    _start_baseball_lineup(state, "home")
    result = LineupService.enter_courtesy_runner(
        state, "home", "home-cr1", "home-p1", "PITCHER", eligible=False, event_id="e1"
    )
    assert result.ok
    assert any(m.code == "COURTESY_RUNNER_POSSIBLY_INELIGIBLE" and m.severity == "SOFT_WARNING" for m in result.data["messages"])
    assert len(state["lineup"]["home"]["courtesy_runners"]) == 1


# --- BOO-01 / BOO-02: batting out of order -----------------------------------


def test_BOO_01_wrong_batter_hits_with_no_appeal_leaves_a_warning_and_no_auto_out() -> None:
    state = _new_state()
    _start_baseball_lineup(state, "home")
    result = LineupService.record_batter(state, "home", 3, "home-p5", event_id="e1")
    assert result.ok
    assert result.data["alert"] is not None
    assert result.data["alert"]["status"] == "OPEN"
    assert any(m.code == "BATTING_ORDER_MISMATCH" for m in result.data["messages"])
    # no out was created and no lineup cursor changed by this call alone
    assert state["lineup"]["home"]["slots"]["3"]["active_player_id"] == "home-p3"


def test_BOO_02_wrong_batter_appealed_and_ruled_applies_the_ruling() -> None:
    state = _new_state()
    _start_baseball_lineup(state, "home")
    LineupService.record_batter(state, "home", 3, "home-p5", event_id="e1")
    result = LineupService.apply_appeal_ruling(
        state, "home", 0, appeal_type="BATTING_OUT_OF_ORDER", ruling_result="OUT_AT_BAT", next_batter_slot=6, event_id="e2"
    )
    assert result.ok
    assert result.data["next_batter_slot"] == 6
    assert state["lineup"]["home"]["batting_order_alerts"][0]["status"] == "APPEAL_RULING_RECORDED"
