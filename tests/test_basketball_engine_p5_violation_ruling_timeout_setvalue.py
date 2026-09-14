"""Basketball engine P5 addendum: violation()/ruling()/timeout()/
set_value() -- three real gaps found while building the P5 operator UI
(docs/BASKETBALL_ENGINE_SCOPING_PLAN.md's P5 row names "violation entry,
ruling workflow, manual set-value," none of which had backing engine
support from P1-P4) plus a fourth (timeout entry) noticed in the same
pass. Designed and tested here, mirroring the same care P1-P4 gave every
other action, before any UI is wired to them.
"""

from __future__ import annotations

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


# --- violation() -------------------------------------------------------------

def test_violation_is_recorded_and_applies_the_supplied_possession_consequence():
    state, ruleset = _new_game()
    state["possession"] = "home"
    result = HoopsRulesService.violation(state, {
        "team": "home", "violationType": "traveling", "playerId": "h1", "possessionTo": "visitor",
    })
    assert result.ok
    assert state["possession"] == "visitor"
    assert result.data["event"]["event_type"] == "VIOLATION"
    assert result.data["event"]["payload"]["violationType"] == "traveling"


def test_violation_never_guesses_a_possession_consequence_when_none_is_given():
    # No possessionTo supplied -- e.g. a violation type the operator
    # doesn't want to change possession for (or a scoring consequence like
    # goaltending, which this method deliberately doesn't model itself).
    state, ruleset = _new_game()
    state["possession"] = "home"
    result = HoopsRulesService.violation(state, {"team": "visitor", "violationType": "goaltending"})
    assert result.ok
    assert state["possession"] == "home"  # untouched


def test_unknown_violation_type_is_flagged_not_silently_accepted():
    state, ruleset = _new_game()
    try:
        HoopsRulesService.violation(state, {"team": "home", "violationType": "not_a_real_violation"})
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "unknown violationType" in str(exc)


# --- ruling() ------------------------------------------------------------------

def test_ruling_can_adjust_score_possession_and_clock_together():
    state, ruleset = _new_game()
    state["clock_seconds"] = 100
    result = HoopsRulesService.ruling(state, {
        "scoreAdjustment": {"team": "home", "points": 2},
        "possessionTo": "visitor",
        "clockSecondsAdjustment": -5,
    })
    assert result.ok
    assert state["home_score"] == 2
    assert state["possession"] == "visitor"
    assert state["clock_seconds"] == 95


def test_ruling_clock_adjustment_never_goes_below_zero():
    state, ruleset = _new_game()
    state["clock_seconds"] = 3
    HoopsRulesService.ruling(state, {"clockSecondsAdjustment": -10})
    assert state["clock_seconds"] == 0


def test_ruling_with_no_fields_is_a_harmless_no_op():
    state, ruleset = _new_game()
    before_hash = HoopsStateFoundation.state_hash(state)  # excludes ledger fields already
    result = HoopsRulesService.ruling(state, {})
    assert result.ok
    # Only the ledger grew (a RULING event with an empty payload was
    # still recorded, for audit) -- canonical game state is unchanged.
    assert HoopsStateFoundation.state_hash(state) == before_hash


# --- timeout() -----------------------------------------------------------------

def test_timeout_decrements_the_teams_combined_remaining_count():
    state, ruleset = _new_game()
    assert state["hoops"]["home_timeouts"] == 5
    result = HoopsRulesService.timeout(state, {"team": "home"})
    assert result.ok
    assert state["hoops"]["home_timeouts"] == 4


def test_timeout_with_none_remaining_is_a_hard_error_not_a_negative_count():
    state, ruleset = _new_game()
    state["hoops"]["home_timeouts"] = 0
    result = HoopsRulesService.timeout(state, {"team": "home"})
    assert result.code == "HARD_ERROR"
    assert state["hoops"]["home_timeouts"] == 0


# --- set_value() ---------------------------------------------------------------

def test_set_value_corrects_a_shared_field_directly():
    state, ruleset = _new_game()
    result = HoopsRulesService.set_value(state, "clock_seconds", 250)
    assert result.ok
    assert state["clock_seconds"] == 250
    assert result.data["event"]["event_type"] == "SET_VALUE"


def test_set_value_corrects_a_hoops_namespaced_field_directly():
    state, ruleset = _new_game()
    result = HoopsRulesService.set_value(state, "visitor_timeouts", 1)
    assert result.ok
    assert state["hoops"]["visitor_timeouts"] == 1


def test_set_value_on_team_fouls_recomputes_the_opponents_bonus():
    # Setting visitor_team_fouls directly to 5 must flip HOME's bonus to
    # DOUBLE, same rule as apply_foul()'s own bonus-direction fix.
    state, ruleset = _new_game()
    result = HoopsRulesService.set_value(state, "visitor_team_fouls", 5)
    assert result.ok
    assert state["hoops"]["visitor_team_fouls"] == 5
    assert state["hoops"]["home_bonus"] == "DOUBLE"
    assert state["hoops"]["visitor_bonus"] == "NONE"


def test_set_value_rejects_an_unsettable_field():
    state, ruleset = _new_game()
    try:
        HoopsRulesService.set_value(state, "disqualified", ["h1"])
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "not settable" in str(exc)


def test_set_value_shot_clock_accepts_none_to_disable_it():
    state, ruleset = _new_game()
    result = HoopsRulesService.set_value(state, "shot_clock_seconds", None)
    assert result.ok
    assert state["hoops"]["shot_clock_seconds"] is None


# --- replay covers all four new event types -------------------------------------

def test_replay_reproduces_violation_ruling_timeout_and_set_value():
    state, ruleset = _new_game()
    baseline = HoopsStateFoundation.snapshot(state)
    state["possession"] = "home"
    HoopsRulesService.violation(state, {"team": "home", "violationType": "traveling", "possessionTo": "visitor"})
    HoopsRulesService.ruling(state, {"scoreAdjustment": {"team": "home", "points": 2}})
    HoopsRulesService.timeout(state, {"team": "home"})
    HoopsRulesService.set_value(state, "visitor_team_fouls", 5)

    events = state["hoops"]["hoops_events"]
    rebuilt = HoopsStateFoundation.rebuild(state, events, baseline=baseline)
    assert HoopsStateFoundation.state_hash(rebuilt) == HoopsStateFoundation.state_hash(state)
    assert rebuilt["possession"] == "visitor"
    assert rebuilt["home_score"] == 2
    assert rebuilt["hoops"]["home_timeouts"] == 4
    assert rebuilt["hoops"]["home_bonus"] == "DOUBLE"
