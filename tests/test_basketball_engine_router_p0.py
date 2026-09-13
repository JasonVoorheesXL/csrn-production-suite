"""Basketball engine, P0 addendum to engine_router.py (2026-09-13 decision):
hoops_view()/commit_hoops_view() alongside the existing
diamond_view()/commit_diamond_view(), sharing only the genuinely sport-
agnostic _ensure_namespaced_state() helper. See engine_router.py's module
docstring for the full rationale. tests/test_baseball_engine_p4_engine_router.py
covers the diamond side and must stay green -- this file is the hoops
mirror, plus a couple of direct checks that the shared-helper extraction
didn't change diamond's own behavior.
"""

from __future__ import annotations

import engine_router


def test_is_hoops_sport_is_case_insensitive_and_false_for_football() -> None:
    assert engine_router.is_hoops_sport("Basketball") is True
    assert engine_router.is_hoops_sport({"sport": "BASKETBALL"}) is True
    assert engine_router.is_hoops_sport("football") is False
    assert engine_router.is_hoops_sport("baseball") is False
    assert engine_router.is_hoops_sport(None) is False


def test_ensure_hoops_state_is_a_no_op_for_football_and_diamond_sports() -> None:
    football_state = {"sport": "football"}
    assert engine_router.ensure_hoops_state(football_state) == {}
    assert "hoops" not in football_state

    baseball_state = {"sport": "baseball"}
    assert engine_router.ensure_hoops_state(baseball_state) == {}
    assert "hoops" not in baseball_state


def test_ensure_hoops_state_creates_a_fresh_hoops_blob_for_basketball() -> None:
    state = {"sport": "basketball"}
    hoops = engine_router.ensure_hoops_state(state)
    assert state["hoops"] is hoops
    assert set(hoops) == set(engine_router.HOOPS_OWNED_KEYS)
    # A second call reuses the same dict rather than resetting it.
    hoops["shot_clock"] = "24"
    assert engine_router.ensure_hoops_state(state)["shot_clock"] == "24"


def test_hoops_view_merges_shared_fields_onto_the_nested_hoops_fields() -> None:
    state = {
        "sport": "basketball",
        "status": "live",
        "period": "2",
        "clock": "5:41",
        "possession": "home",
        "home_score": 41,
        "visitor_score": 38,
        "home_team": "Caledonia",
        "hoops": {
            "shot_clock": "14",
            "home_fouls": "3",
            "visitor_fouls": "2",
            "home_bonus": "ONE_AND_ONE",
            "visitor_bonus": "NONE",
            "home_timeouts": "2",
            "visitor_timeouts": "3",
        },
    }
    view = engine_router.hoops_view(state)
    assert view["period"] == "2"
    assert view["clock"] == "5:41"
    assert view["possession"] == "home"
    assert view["home_score"] == 41
    assert view["home_team"] == "Caledonia"
    assert view["shot_clock"] == "14"
    assert view["home_bonus"] == "ONE_AND_ONE"


def test_commit_hoops_view_folds_owned_keys_back_without_touching_shared_ones() -> None:
    state = {"sport": "basketball"}
    view = engine_router.hoops_view(state)
    view["shot_clock"] = "9"
    view["home_bonus"] = "DOUBLE"
    # A hoops mutator has no business writing shared/administrative fields
    # through this view -- commit_hoops_view() must not project them even
    # if present (unlike commit_diamond_view()'s deliberate "status" case).
    view["status"] = "final"

    engine_router.commit_hoops_view(state, view)

    assert state["hoops"]["shot_clock"] == "9"
    assert state["hoops"]["home_bonus"] == "DOUBLE"
    assert "status" not in state  # never projected -- see docstring


def test_default_hoops_state_has_exactly_the_contract_owned_keys() -> None:
    defaults = engine_router.default_hoops_state()
    assert set(defaults) == set(engine_router.HOOPS_OWNED_KEYS)
    # Blank/zeroed placeholders, not guessed ruleset-derived values (P1's job).
    assert defaults["shot_clock"] == ""
    assert defaults["home_bonus"] == "NONE"
    assert defaults["visitor_bonus"] == "NONE"


def test_hoops_owned_keys_never_shadow_diamond_owned_keys() -> None:
    # These two sports' namespaces are never mixed -- confirms the P0
    # addendum didn't accidentally reuse a diamond field name for a
    # different meaning.
    assert not set(engine_router.HOOPS_OWNED_KEYS) & set(engine_router.DIAMOND_OWNED_KEYS)


def test_diamond_behavior_is_unchanged_by_the_shared_helper_extraction() -> None:
    # ensure_diamond_state() now calls the shared _ensure_namespaced_state()
    # helper internally -- confirm the externally-visible behavior is
    # identical to before the refactor (see
    # test_baseball_engine_p4_engine_router.py for the full diamond suite).
    state = {"sport": "baseball"}
    diamond = engine_router.ensure_diamond_state(state)
    assert state["diamond"] is diamond
    assert diamond  # non-empty default, same as before
    diamond["inning"] = 3
    assert engine_router.ensure_diamond_state(state)["inning"] == 3
