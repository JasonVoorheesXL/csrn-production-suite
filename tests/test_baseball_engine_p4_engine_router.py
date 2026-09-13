"""Baseball engine P4 (docs/BASEBALL_SOFTBALL_ENGINE_SCOPING_PLAN.md P4 row):
engine_router dispatch on state["sport"]. Covers the diamond_view()/
commit_diamond_view() adapter that lets state["diamond"] stay namespaced
while every P0-P3 service (built and tested against a flat dict) keeps
working unmodified.
"""

from __future__ import annotations

import engine_router
from at_bat_rules_service import AtBatRulesService


def _football_state() -> dict:
    return {"sport": "Football", "status": "live", "home_score": 0, "visitor_score": 0}


def _baseball_state(**overrides) -> dict:
    state = {
        "sport": "baseball",
        "status": "live",
        "country": "US",
        "home_team": "Caledonia",
        "visitor_team": "New Hope",
        "home_score": 0,
        "visitor_score": 0,
    }
    state.update(overrides)
    return state


def test_is_diamond_sport_is_case_insensitive_and_false_for_football() -> None:
    assert engine_router.is_diamond_sport("Baseball")
    assert engine_router.is_diamond_sport({"sport": "softball"})
    assert not engine_router.is_diamond_sport({"sport": "Football"})
    assert not engine_router.is_diamond_sport({})


def test_ensure_diamond_state_is_a_no_op_for_football() -> None:
    state = _football_state()
    before = dict(state)
    result = engine_router.ensure_diamond_state(state)
    assert result == {}
    assert state == before
    assert "diamond" not in state


def test_ensure_diamond_state_creates_a_fresh_diamond_for_baseball() -> None:
    state = _baseball_state()
    diamond = engine_router.ensure_diamond_state(state)
    assert diamond["inning"] == 1
    assert diamond["lineup"]["home"]["slots"] == {}
    assert state["diamond"] is diamond
    # Calling again does not clobber an in-progress game.
    diamond["outs"] = 2
    again = engine_router.ensure_diamond_state(state)
    assert again["outs"] == 2


def test_diamond_view_merges_shared_fields_onto_the_nested_diamond_fields() -> None:
    state = _baseball_state(country="US", region="MS")
    view = engine_router.diamond_view(state)
    assert view["country"] == "US"
    assert view["region"] == "MS"
    assert view["sport"] == "baseball"
    assert view["inning"] == 1  # from the freshly-created state["diamond"]


def test_commit_diamond_view_propagates_status_and_projects_scores() -> None:
    state = _baseball_state()
    view = engine_router.diamond_view(state)
    view["home_score"] = 4
    view["visitor_score"] = 1
    view["status"] = "completed"
    engine_router.commit_diamond_view(state, view)

    assert state["diamond"]["home_score"] == 4
    assert state["status"] == "completed"  # shared field, propagated to the OUTER state
    assert "status" not in state["diamond"]  # never duplicated into the nested namespace
    assert state["home_score"] == 4  # projected for the shared renderer
    assert state["visitor_score"] == 1


def test_run_diamond_mutation_records_a_plate_appearance_and_syncs_scores() -> None:
    state = _baseball_state()

    def mutate(view: dict) -> AtBatRulesService:
        return AtBatRulesService.record_plate_appearance(view, {
            "battingTeam": "visitor", "batterId": "b1", "pitcherId": "p1",
            "resultCode": "HR",
            "runnerOutcomes": [{"from": "batter", "to": "score", "playerId": "b1"}],
            "outsRecorded": 0, "hits": 1,
        })

    result = engine_router.run_diamond_mutation(state, mutate)
    assert result.ok
    assert state["diamond"]["visitor_score"] == 1
    assert state["visitor_score"] == 1  # sync_shared_fields projected it
    assert state["diamond"]["diamond_events"]  # ledger recorded the play


def test_overlay_payload_resolves_the_real_ruleset_from_the_outer_state() -> None:
    state = _baseball_state()
    payload = engine_router.overlay_payload(state)
    assert payload["regulation_innings"] == 7
    assert payload["inning_half"] == "TOP"


def test_box_score_report_dispatches_through_the_nested_diamond_state() -> None:
    state = _baseball_state()

    def mutate(view: dict) -> AtBatRulesService:
        return AtBatRulesService.record_plate_appearance(view, {
            "battingTeam": "visitor", "batterId": "b1", "pitcherId": "p1",
            "resultCode": "HR",
            "runnerOutcomes": [{"from": "batter", "to": "score", "playerId": "b1"}],
            "outsRecorded": 0, "hits": 1,
        })

    engine_router.run_diamond_mutation(state, mutate)
    report = engine_router.box_score_report(state)
    assert report["batting"]["b1"]["h"] == 1
    assert report["batting"]["b1"]["r"] == 1
