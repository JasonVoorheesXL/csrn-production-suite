"""Basketball engine P1 (docs/BASKETBALL_ENGINE_SCOPING_PLAN.md Sec.10 P1
row): hoops_state_service (canonical fields, mutators, state_hash) +
hoops_rules_service (shot/foul-with-bonus-and-foul-out/free_throw/
possession+arrow) + hoops_period_service (quarters -> OT, per-period foul
reset). Gate: "A scripted 4-quarter game (incl. reaching bonus, a
foul-out, a held-ball arrow flip, an OT) reaches a correct final state
through service calls; replay-by-hash + void-and-replay invariants hold."

No UI, no routes -- every call here is direct service-to-service, exactly
as P1 is scoped (that's P4/P5).
"""

from __future__ import annotations

import copy

import pytest

from hoops_period_service import HoopsPeriodService
from hoops_rules_service import HoopsRulesService
from hoops_state_service import HoopsStateFoundation


def _new_game() -> tuple[dict, dict]:
    state = {
        "sport": "basketball", "country": "US", "region": None, "association": "NFHS",
        "home_team": "Home", "visitor_team": "Visitor",
        "home_score": 0, "visitor_score": 0,
    }
    ruleset = HoopsRulesService.active_ruleset(state)
    HoopsPeriodService.start_game(state, ruleset)
    return state, ruleset


def test_start_game_seeds_period_clock_timeouts_from_the_nfhs_ruleset():
    state, ruleset = _new_game()
    assert ruleset["id"] == "basketball/us-nfhs"
    assert state["period"] == "1"
    assert state["clock_seconds"] == 480
    assert state["clock_running"] is False
    hoops = state["hoops"]
    assert hoops["period_format"] == "quarters"
    assert hoops["period_length_seconds"] == 480
    # NFHS-generic ships the shot clock off (P0 ruleset) -- blank/hidden,
    # not a stale/zero value (docs/HOOPS_OVERLAY_CONTRACT.md Sec.1).
    assert hoops["shot_clock_seconds"] is None
    assert hoops["shot_clock_visible"] is False
    # 3 full + 2 short combined (see hoops_period_service's own comment on
    # why this is a deliberate simplification, not a lost distinction).
    assert hoops["home_timeouts"] == 5
    assert hoops["visitor_timeouts"] == 5
    assert hoops["home_bonus"] == "NONE"
    assert hoops["visitor_bonus"] == "NONE"
    assert hoops["player_fouls"] == {}
    assert hoops["disqualified"] == []


def test_scripted_four_quarter_game_reaches_bonus_foulout_arrow_flip_and_overtime():
    state, ruleset = _new_game()

    # --- Q1: a made shot, a held ball (arrow flip) ---------------------
    result = HoopsRulesService.shot(state, {"team": "home", "made": True, "points": 2, "shooterId": "H1"})
    assert result.ok
    assert state["home_score"] == 2

    held = HoopsRulesService.held_ball(state, {})
    assert held.data["possession_arrow"] == "home"
    assert state["possession"] == "home"

    # Visitor commits 5 personal fouls, all on the same player (V1) --
    # by the 5th: home should be in the DOUBLE bonus (a team's fouls send
    # its OPPONENT to the bonus, never itself) and V1 should foul out
    # (personal_foul_disqualification: 5 in the NFHS ruleset).
    foul_result = None
    for _ in range(5):
        foul_result = HoopsRulesService.foul(state, {"team": "visitor", "playerId": "V1", "foulType": "personal"})
        assert foul_result.ok
    assert state["hoops"]["visitor_team_fouls"] == 5
    assert state["hoops"]["home_bonus"] == "DOUBLE"
    assert state["hoops"]["visitor_bonus"] == "NONE"
    assert state["hoops"]["player_fouls"]["V1"] == 5
    assert "V1" in state["hoops"]["disqualified"]
    assert foul_result.data["fouled_out"] is True
    # Home is in the bonus at the moment of this (the 5th) foul -- a
    # non-shooting personal foul with the fouled team in DOUBLE bonus
    # proposes 2 free throws.
    assert foul_result.data["free_throws_proposed"] == 2

    # End Q1 -- force the clock to 0 and let the next call close it.
    state["clock_seconds"] = 0
    result = HoopsRulesService.shot(state, {"team": "visitor", "made": False, "points": 2, "shooterId": "V2"})
    assert result.data["period_closed"] is True
    assert result.data["game_end_candidate"] is None
    assert state["period"] == "2"
    assert state["clock_seconds"] == 480
    assert state["clock_running"] is False
    # Team fouls (and the bonus they earned) reset every quarter under
    # the NFHS ruleset's fouls.team_foul_scope="quarter" -- but personal
    # fouls and disqualification are for the whole game and must persist.
    assert state["hoops"]["home_team_fouls"] == 0
    assert state["hoops"]["visitor_team_fouls"] == 0
    assert state["hoops"]["home_bonus"] == "NONE"
    assert state["hoops"]["visitor_bonus"] == "NONE"
    assert state["hoops"]["player_fouls"]["V1"] == 5
    assert "V1" in state["hoops"]["disqualified"]

    # --- Q2: visitor answers, tying it 2-2 ------------------------------
    HoopsRulesService.shot(state, {"team": "visitor", "made": True, "points": 2, "shooterId": "V3"})
    assert state["visitor_score"] == 2
    state["clock_seconds"] = 0
    result = HoopsRulesService.shot(state, {"team": "home", "made": False, "points": 2, "shooterId": "H2"})
    assert state["period"] == "3"

    # --- Q3: quiet quarter, just close it -------------------------------
    state["clock_seconds"] = 0
    result = HoopsRulesService.shot(state, {"team": "home", "made": False, "points": 2, "shooterId": "H3"})
    assert state["period"] == "4"

    # --- Q4: tied 2-2 when the clock expires -> proposes OT, not a
    # game-end candidate; the period does NOT report closed via the
    # regulation path, it advances straight into overtime. ---------------
    state["clock_seconds"] = 0
    result = HoopsRulesService.shot(state, {"team": "visitor", "made": False, "points": 3, "shooterId": "V4"})
    assert result.data["game_end_candidate"] is None
    assert result.data["period_closed"] is True
    assert state["period"] == "OT"
    assert state["clock_seconds"] == 240  # NFHS ruleset's overtime.length_seconds
    assert state["hoops"]["home_team_fouls"] == 0  # reset entering OT too

    # --- OT: home wins it -----------------------------------------------
    HoopsRulesService.shot(state, {"team": "home", "made": True, "points": 2, "shooterId": "H1"})
    assert state["home_score"] == 4
    state["clock_seconds"] = 0
    result = HoopsRulesService.shot(state, {"team": "visitor", "made": False, "points": 2, "shooterId": "V1"})
    # Decided score with the clock at 0 in an OT period -> a real
    # GAME_END_CANDIDATE, and -- unlike every prior period boundary in
    # this test -- the period is NOT closed (there is no well-defined
    # "next period" once the game is over; see hoops_period_service's
    # _next_period_label()).
    assert result.data["period_closed"] is False
    assert result.data["game_end_candidate"] == {"reason": "OVERTIME", "period": "OT"}
    assert state["period"] == "OT"

    final = HoopsRulesService.confirm_game_end(state, "OVERTIME")
    assert final.ok
    assert state["status"] == "completed"
    assert state["hoops"]["official_end_reason"] == "OVERTIME"


def test_replay_by_hash_reproduces_the_live_result():
    state, ruleset = _new_game()
    baseline = HoopsStateFoundation.snapshot(state)

    HoopsRulesService.shot(state, {"team": "home", "made": True, "points": 2, "shooterId": "H1"})
    HoopsRulesService.held_ball(state, {})
    HoopsRulesService.foul(state, {"team": "visitor", "playerId": "V1", "foulType": "personal"})

    events = copy.deepcopy(state["hoops"]["hoops_events"])
    rebuilt = HoopsStateFoundation.rebuild(state, events, baseline=baseline)

    assert HoopsStateFoundation.state_hash(rebuilt) == HoopsStateFoundation.state_hash(state)
    assert rebuilt["home_score"] == state["home_score"] == 2
    assert rebuilt["possession"] == state["possession"] == "home"
    assert rebuilt["hoops"]["visitor_team_fouls"] == state["hoops"]["visitor_team_fouls"] == 1


def test_voiding_an_event_and_replaying_reproduces_the_result_without_it():
    state, ruleset = _new_game()
    baseline = HoopsStateFoundation.snapshot(state)

    HoopsRulesService.shot(state, {"team": "home", "made": True, "points": 2, "shooterId": "H1"})
    foul_result = HoopsRulesService.foul(state, {"team": "visitor", "playerId": "V1", "foulType": "personal"})
    foul_event_id = foul_result.data["event"]["event_id"]

    events = copy.deepcopy(state["hoops"]["hoops_events"])

    # Sanity: replaying without voiding anything reproduces the live state.
    rebuilt_full = HoopsStateFoundation.rebuild(state, events, baseline=baseline)
    assert HoopsStateFoundation.state_hash(rebuilt_full) == HoopsStateFoundation.state_hash(state)
    assert rebuilt_full["hoops"]["visitor_team_fouls"] == 1

    # Void the foul and replay again -- reproduces the pre-foul result,
    # except the voided event itself stays visible in the ledger (audit).
    for event in events:
        if event["event_id"] == foul_event_id:
            event["voided"] = True
    rebuilt_voided = HoopsStateFoundation.rebuild(state, events, baseline=baseline)

    assert rebuilt_voided["hoops"]["visitor_team_fouls"] == 0
    assert rebuilt_voided["hoops"]["player_fouls"] == {}
    assert rebuilt_voided["home_score"] == 2  # the shot event is untouched
    voided_ids = [e["event_id"] for e in rebuilt_voided["hoops"]["hoops_events"] if e.get("voided")]
    assert foul_event_id in voided_ids


def test_technical_foul_does_not_count_toward_team_fouls_but_does_toward_personal():
    state, ruleset = _new_game()
    result = HoopsRulesService.foul(state, {"team": "visitor", "playerId": "V9", "foulType": "technical"})
    assert result.ok
    assert state["hoops"]["visitor_team_fouls"] == 0  # NFHS: technicals don't count toward team fouls
    assert state["hoops"]["player_fouls"]["V9"] == 1  # ruleset's technical_counts_toward_personal=True
    assert result.data["free_throws_proposed"] == 2  # ruleset technical.shots_awarded


def test_rebound_and_turnover_change_possession_without_scoring():
    state, ruleset = _new_game()
    HoopsRulesService.rebound(state, {"team": "visitor", "kind": "defensive"})
    assert state["possession"] == "visitor"
    HoopsRulesService.turnover(state, {"team": "visitor"})
    assert state["possession"] == "home"
    assert state["home_score"] == 0
    assert state["visitor_score"] == 0


def test_halves_format_is_supported_generically_though_unexercised_by_any_shipped_ruleset():
    # No shipped ruleset uses period.format="halves" yet (sub-varsity
    # profiles all keep "quarters" with a shorter length, per P0) --
    # exercises the generic format-handling path directly rather than
    # leaving it unverified.
    state = {"sport": "basketball", "country": "US", "region": None, "association": "NFHS"}
    ruleset = copy.deepcopy(HoopsRulesService.active_ruleset(state))
    ruleset["period"] = {"format": "halves", "count": 2, "length_seconds": 960, "ot_length_seconds": 240, "ot_count_cap": None}
    HoopsPeriodService.start_game(state, ruleset)
    assert state["period"] == "H1"
    assert state["clock_seconds"] == 960

    state["clock_seconds"] = 0
    result = HoopsPeriodService.close_period(state, ruleset)
    assert result.ok
    assert state["period"] == "H2"

    state["home_score"] = 10
    state["visitor_score"] = 3
    state["clock_seconds"] = 0
    candidate = HoopsRulesService.evaluate_game_end(state, ruleset)
    assert candidate == {"reason": "REGULATION", "period": "H2"}


def test_period_count_mismatched_with_format_is_flagged_not_silently_accepted():
    state = {"sport": "basketball", "country": "US", "region": None, "association": "NFHS"}
    ruleset = copy.deepcopy(HoopsRulesService.active_ruleset(state))
    ruleset["period"]["count"] = 3  # quarters implies 4 -- an authoring inconsistency
    with pytest.raises(ValueError, match="does not match"):
        HoopsPeriodService.start_game(state, ruleset)


def test_overtime_cap_reached_is_flagged_not_silently_guessed_at():
    state, ruleset = _new_game()
    ruleset = copy.deepcopy(ruleset)
    ruleset["overtime"]["ot_count_cap"] = 1
    state["period"] = "OT"
    state["home_score"] = 5
    state["visitor_score"] = 5
    state["clock_seconds"] = 0
    with pytest.raises(ValueError, match="ot_count_cap"):
        HoopsPeriodService.close_period(state, ruleset)


def test_unrecognized_bonus_rule_type_is_flagged_not_silently_guessed_at():
    with pytest.raises(ValueError, match="unrecognized bonus_rule.type"):
        HoopsStateFoundation.bonus_for_fouls(5, {"type": "ONE_AND_ONE_THEN_DOUBLE", "threshold": 7})


def test_shot_clock_resets_to_full_length_entering_a_new_period_when_enabled():
    # No shipped ruleset enables the shot clock yet (P0: NFHS-generic and
    # MHSAA both ship it off, pending owner confirmation -- scoping doc
    # Sec.4.2) -- a synthetic ruleset override exercises the reset path
    # that would otherwise have zero coverage. Calls hoops_period_service
    # directly (rather than through HoopsRulesService.shot(), which
    # re-resolves the real, shot-clock-disabled ruleset internally) so the
    # synthetic override actually takes effect.
    state = {"sport": "basketball", "country": "US", "region": None, "association": "NFHS"}
    ruleset = copy.deepcopy(HoopsRulesService.active_ruleset(state))
    ruleset["shot_clock"] = {"enabled": True, "length_seconds": 30, "reset_offensive_rebound_seconds": 20}
    HoopsPeriodService.start_game(state, ruleset)
    assert state["hoops"]["shot_clock_seconds"] == 30
    assert state["hoops"]["shot_clock_visible"] is True

    state["hoops"]["shot_clock_seconds"] = 4  # mid-period, about to expire
    state["clock_seconds"] = 0
    result = HoopsPeriodService.close_period(state, ruleset)
    assert result.ok
    assert state["period"] == "2"
    assert state["hoops"]["shot_clock_seconds"] == 30  # reset, not left at 4
    assert state["hoops"]["shot_clock_visible"] is True
