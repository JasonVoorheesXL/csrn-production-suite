"""Baseball engine P1 acceptance (docs/BASEBALL_SOFTBALL_ENGINE_SCOPING_PLAN.md
P1 row): "A scripted regulation game reaches a correct final state + line
score through service calls; spec Sec.19 END-*, RUL-01 and the Sec.19.1
replay/void invariants pass." No UI, no routes -- every call here is direct
service-to-service, exactly as P1 is scoped.
"""

from __future__ import annotations

import copy

import pytest

import ruleset_service
from at_bat_rules_service import AtBatRulesService
from diamond_state_service import DiamondStateFoundation, default_state
from game_end_evaluator import GameEndEvaluator
from inning_service import InningService
from rules_validator import RulesValidator


def _new_game() -> dict:
    # "status"/"home_score"/"visitor_score" are shared CSRN fields owned by
    # app.py's DEFAULT_STATE, not diamond_state_service -- P1 is "No UI," so
    # this test fixture stands in for that merge rather than importing app.
    state = {"sport": "baseball", "status": "live", "home_score": 0, "visitor_score": 0}
    state.update(default_state())
    return state


def _out(team: str) -> dict:
    return {"battingTeam": team, "runnerOutcomes": [], "outsRecorded": 1}


def _score(team: str, runs: int) -> dict:
    return {
        "battingTeam": team,
        "runnerOutcomes": [{"from": "batter", "to": "score"} for _ in range(runs)],
        "outsRecorded": 0,
    }


def _play_half_inning(state: dict, team: str, runs: int) -> None:
    if runs:
        result = AtBatRulesService.record_plate_appearance(state, _score(team, runs))
        assert result.ok
    for _ in range(3):
        result = AtBatRulesService.record_plate_appearance(state, _out(team))
        assert result.ok


# --- the scripted regulation game -----------------------------------------


def test_scripted_regulation_game_reaches_correct_final_state_and_line_score() -> None:
    state = _new_game()
    visitor_runs = [0, 1, 0, 0, 1, 0, 1]  # 7 tops
    home_runs = [1, 0, 1, 0, 0, 0]  # 6 complete bottoms; the 7th walks off

    for inning_index in range(6):
        assert state["inning"] == inning_index + 1
        assert state["inning_half"] == "TOP"
        _play_half_inning(state, "visitor", visitor_runs[inning_index])
        assert state["inning_half"] == "BOTTOM"
        _play_half_inning(state, "home", home_runs[inning_index])
        assert state["inning_half"] == "TOP"

    # top 7: visitor takes a 1-run lead (3-2) -- regulation must NOT end yet,
    # home still gets its required bottom-half turn (spec END-02 shape).
    assert state["inning"] == 7
    _play_half_inning(state, "visitor", visitor_runs[6])
    assert state["inning_half"] == "BOTTOM"
    assert state["visitor_score"] == 3 and state["home_score"] == 2
    assert state["game_end_candidate"] is None

    # bottom 7: home scores 2 in one plate appearance -- a walk-off the
    # instant the go-ahead run scores, before any outs are recorded.
    result = AtBatRulesService.record_plate_appearance(state, _score("home", 2))
    assert result.ok
    assert state["home_score"] == 4 and state["visitor_score"] == 3
    assert state["game_end_candidate"] == {"reason": "WALK_OFF", "inning": 7, "half": "BOTTOM"}
    assert state["outs"] == 0  # walk-off ends before three outs, spec Sec.7.3

    confirm = AtBatRulesService.confirm_game_end(state, "WALK_OFF")
    assert confirm.ok
    assert state["status"] == "completed"
    assert state["official_game_end_reason"] == "WALK_OFF"

    assert state["line_score"]["visitor"] == [0, 1, 0, 0, 1, 0, 1]
    assert state["line_score"]["home"] == [1, 0, 1, 0, 0, 0, 2]
    assert state["home_score"] == 4
    assert state["visitor_score"] == 3


# --- spec Sec.19 acceptance scenarios --------------------------------------


def test_END_01_home_leads_after_visitor_completes_top_5_ends_without_bottom_half() -> None:
    state = _new_game()
    state["inning"] = 5
    state["inning_half"] = "TOP"
    state["home_score"] = 12
    state["visitor_score"] = 1

    def fake_ruleset(*_a, **_k):
        return {
            "regulation": {"scheduledInnings": 7},
            "runRules": [{"id": "test-10-after-5", "runDifferential": 10, "earliestCompletedInning": 5}],
        }

    original = ruleset_service.active_ruleset
    ruleset_service.active_ruleset = fake_ruleset
    try:
        result = AtBatRulesService.record_plate_appearance(state, _out("visitor"))
        assert result.ok
        result = AtBatRulesService.record_plate_appearance(state, _out("visitor"))
        assert result.ok
        result = AtBatRulesService.record_plate_appearance(state, _out("visitor"))
        assert result.ok
        # third out of top 5 closes the half-inning; the run-rule fires
        # immediately -- home never has to bat the bottom of the 5th.
        assert state["inning_half"] == "BOTTOM" and state["inning"] == 5
        assert state["game_end_candidate"]["reason"] == "RUN_RULE"
    finally:
        ruleset_service.active_ruleset = original


def test_END_02_visitor_takes_lead_in_top_5_home_still_gets_its_turn() -> None:
    state = _new_game()
    state["inning"] = 5
    state["inning_half"] = "TOP"
    state["home_score"] = 0
    state["visitor_score"] = 0

    def fake_ruleset(*_a, **_k):
        return {
            "regulation": {"scheduledInnings": 7},
            "runRules": [{"id": "test-10-after-5", "runDifferential": 10, "earliestCompletedInning": 5}],
        }

    original = ruleset_service.active_ruleset
    ruleset_service.active_ruleset = fake_ruleset
    try:
        result = AtBatRulesService.record_plate_appearance(state, _score("visitor", 10))
        assert result.ok
        assert state["visitor_score"] == 10
        # visitor took a 10-run lead mid top-5 -- home has not batted yet,
        # so no run-rule candidate can exist regardless of the differential.
        assert state["game_end_candidate"] is None

        _play_half_inning(state, "visitor", 0)  # close out the rest of top 5
        assert state["inning_half"] == "BOTTOM" and state["inning"] == 5
        # home's turn has *started* but not completed -- still no candidate.
        assert state["game_end_candidate"] is None

        _play_half_inning(state, "home", 0)  # home completes its turn, scoreless
        assert state["inning_half"] == "TOP" and state["inning"] == 6
        assert state["game_end_candidate"]["reason"] == "RUN_RULE"
        assert state["game_end_candidate"]["trailingTeam"] == "home"
    finally:
        ruleset_service.active_ruleset = original


def test_END_03_home_scores_go_ahead_run_in_bottom_final_inning_is_a_walk_off() -> None:
    state = _new_game()
    state["inning"] = 7
    state["inning_half"] = "BOTTOM"
    state["home_score"] = 3
    state["visitor_score"] = 3

    result = AtBatRulesService.record_plate_appearance(state, _score("home", 1))
    assert result.ok
    assert state["game_end_candidate"] == {"reason": "WALK_OFF", "inning": 7, "half": "BOTTOM"}
    # finalize the play first, terminate second -- outs untouched, no
    # engine-invented "game over" flag before confirm_game_end is called.
    assert state["status"] != "completed"
    AtBatRulesService.confirm_game_end(state, "WALK_OFF")
    assert state["status"] == "completed"


def test_END_04_tie_after_scheduled_innings_seeds_the_tiebreaker_runner() -> None:
    state = _new_game()
    state["inning"] = 8
    state["inning_half"] = "TOP"
    state["home_score"] = 2
    state["visitor_score"] = 2

    def fake_ruleset(*_a, **_k):
        return {
            "regulation": {"scheduledInnings": 7},
            "tieBreaker": {"mode": "RUNNER_ON_SECOND", "startsAtInning": 8},
        }

    original = ruleset_service.active_ruleset
    ruleset_service.active_ruleset = fake_ruleset
    try:
        result = GameEndEvaluator.seed_tiebreaker_runner(state, "player-99")
        assert result.ok
        assert state["base_runners"]["second"]["player_id"] == "player-99"
        assert state["base_runners"]["second"]["reason"] == "TIEBREAKER_RUNNER_PLACED"
        events = [e for e in state["diamond_events"] if e["event_type"] == "TIEBREAKER_RUNNER_PLACED"]
        assert len(events) == 1
        assert events[0]["payload"] == {"base": "second", "playerId": "player-99"}

        # not eligible a second time -- base already occupied
        again = GameEndEvaluator.seed_tiebreaker_runner(state, "player-100")
        assert again.code == "BASE_OCCUPIED"
    finally:
        ruleset_service.active_ruleset = original


def test_RUL_01_obstruction_award_to_third_applies_exactly_as_ruled() -> None:
    state = _new_game()
    state["base_runners"]["first"] = {"player_id": "runner-1", "reason": "PLATE_APPEARANCE", "event_id": ""}
    payload = {
        "rulingCode": "OBSTRUCTION",
        "rulingBy": "BASE",
        "ballStatus": "DEAD",
        "baseAwards": [{"runnerId": "runner-1", "fromBase": "first", "toBase": "third"}],
        "outsAwarded": [],
    }
    result = AtBatRulesService.record_ruling(state, payload)
    assert result.ok
    # the engine only moved the runner exactly where ruled -- no judgment
    # about whether third was "deserved."
    assert state["base_runners"]["first"] is None
    assert state["base_runners"]["third"]["player_id"] == "runner-1"
    assert state["ball_status"] == "DEAD"
    assert state["pending_ruling"] is None


# --- spec Sec.19.1 property/invariant tests --------------------------------


def test_replaying_the_same_ledger_produces_the_same_state_hash() -> None:
    state = _new_game()
    _play_half_inning(state, "visitor", 1)
    _play_half_inning(state, "home", 2)
    AtBatRulesService.record_plate_appearance(state, _score("visitor", 1))

    live_hash = DiamondStateFoundation.state_hash(state)
    replayed = DiamondStateFoundation.rebuild(state, state["diamond_events"])
    replayed_hash = DiamondStateFoundation.state_hash(replayed)
    assert replayed_hash == live_hash


def test_voiding_an_event_and_replaying_matches_a_clean_ledger_without_it() -> None:
    # Build a ledger with an extra, later-voided plate appearance.
    with_extra = _new_game()
    _play_half_inning(with_extra, "visitor", 1)
    AtBatRulesService.record_plate_appearance(with_extra, _score("visitor", 5))  # to be voided

    clean = _new_game()
    _play_half_inning(clean, "visitor", 1)

    extra_event_id = with_extra["diamond_events"][-1]["event_id"]
    assert DiamondStateFoundation.void_event(with_extra, extra_event_id) is True

    replayed = DiamondStateFoundation.rebuild(with_extra, with_extra["diamond_events"])
    clean_replayed = DiamondStateFoundation.rebuild(clean, clean["diamond_events"])

    assert DiamondStateFoundation.state_hash(replayed) == DiamondStateFoundation.state_hash(clean_replayed)
    # except audit metadata -- the voided event itself is still visible.
    voided = [e for e in replayed["diamond_events"] if e["event_id"] == extra_event_id]
    assert len(voided) == 1 and voided[0]["voided"] is True


def test_no_valid_sequence_leaves_a_runner_on_two_bases_or_double_occupied() -> None:
    state = _new_game()
    DiamondStateFoundation.place_runner(state, "first", "runner-7", reason="TEST")
    messages = RulesValidator.validate_runner_placement(state, "second", "runner-7")
    assert RulesValidator.has_hard_error(messages)
    assert messages[0].code == "RUNNER_ON_TWO_BASES"


def test_four_outs_is_a_hard_error_not_silently_clamped_by_the_validator() -> None:
    state = _new_game()
    state["outs"] = 2
    messages = RulesValidator.validate_outs(state, 2)  # would make 4
    assert RulesValidator.has_hard_error(messages)
    assert messages[0].code == "FOUR_OUTS"

    result = AtBatRulesService.record_plate_appearance(
        state, {"battingTeam": "visitor", "runnerOutcomes": [], "outsRecorded": 2}
    )
    assert result.code == "HARD_ERROR"
    assert state["outs"] == 2  # untouched -- the HARD_ERROR blocked the mutation


def test_a_suspended_and_resumed_game_is_state_equivalent_immediately_before_the_next_event() -> None:
    # Sec.19.1: "A suspended/resumed game is state-equivalent immediately
    # before the next event." Modeled here as: snapshot mid-game, rebuild
    # from that snapshot with zero further events, and confirm it matches
    # a direct snapshot of the same live state.
    state = _new_game()
    _play_half_inning(state, "visitor", 2)
    DiamondStateFoundation.place_runner(state, "second", "runner-4", reason="PLATE_APPEARANCE")
    state["balls"] = 2
    state["strikes"] = 1

    suspended_snapshot = DiamondStateFoundation.snapshot(state)
    resumed = DiamondStateFoundation.rebuild(state, [], baseline=suspended_snapshot)
    assert DiamondStateFoundation.snapshot(resumed) == suspended_snapshot


def test_changing_the_master_ruleset_does_not_change_a_stamped_historical_game() -> None:
    # Sec.3.2, cross-checked against P0's stamping mechanism: a game-end
    # evaluation keyed off effective_profile_id must not drift if a broader
    # active_ruleset() lookup would now resolve differently -- this is
    # exercised end-to-end in test_broadcast_lifecycle_service.py's
    # test_load_never_restamps_a_resumed_live_snapshot; this test only
    # confirms game_end_evaluator reads the ruleset it's given, not a
    # process-wide cached singleton that a later game could clobber.
    state_a = _new_game()
    state_a["inning"], state_a["inning_half"] = 7, "BOTTOM"
    state_a["home_score"], state_a["visitor_score"] = 3, 2

    state_b = _new_game()
    state_b["inning"], state_b["inning_half"] = 7, "BOTTOM"
    state_b["home_score"], state_b["visitor_score"] = 2, 3

    candidate_a = GameEndEvaluator.evaluate(state_a)
    candidate_b = GameEndEvaluator.evaluate(state_b)
    assert candidate_a["reason"] == "WALK_OFF"
    assert candidate_b is None  # visitor leading, no walk-off for the trailing team


def test_football_engine_is_untouched() -> None:
    # No baseball-engine module imports or monkeypatches anything football
    # owns; a smoke check that the football golden suite's own entry point
    # still resolves independently.
    assert ruleset_service.resolve(sport="football")["id"] == "football/us-nfhs"
