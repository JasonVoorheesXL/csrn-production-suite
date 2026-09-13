"""Basketball engine P3 (docs/BASKETBALL_ENGINE_SCOPING_PLAN.md Sec.10 P3
row): the overlay-state serializer emitting the docs/HOOPS_OVERLAY_
CONTRACT.md keys (all already consumed by Phase C). Gate: "Payload drives
a live basketball scorebug across all five themes with no theme change;
bonus enum -> badge mapping verified."

No route/Flask involvement -- HoopsOverlaySerializer and
engine_router.hoops_overlay_payload()/hoops_box_score_report() are pure
and directly testable, same as baseball's overlay_serializer.py was at P3
(routes wiring is P4, not this phase).
"""

from __future__ import annotations

import re

import pytest

import engine_router
from hoops_overlay_serializer import BONUS_STATES, HoopsOverlaySerializer
from hoops_period_service import HoopsPeriodService
from hoops_rules_service import HoopsRulesService


def _new_game() -> tuple[dict, dict]:
    state = {
        "sport": "basketball", "country": "US", "region": None, "association": "NFHS",
        "home_team": "Home", "visitor_team": "Visitor",
        "home_score": 0, "visitor_score": 0,
    }
    ruleset = HoopsRulesService.active_ruleset(state)
    HoopsPeriodService.start_game(state, ruleset)
    return state, ruleset


def test_serialized_field_names_exactly_match_productionbasketballstate():
    # Cross-checks the serializer's own output keys against the ACTUAL
    # already-shipped renderer function (static-source read, same
    # convention this repo uses for exercising unpinned/frozen JS from
    # Python -- see e.g. tests/test_gate166_production_render_binding.py)
    # rather than trusting the HOOPS_OVERLAY_CONTRACT.md doc's transcription
    # of it.
    js = (
        __import__("pathlib").Path(__file__).resolve().parents[1]
        / "static" / "csrn-production-theme-runtime.js"
    ).read_text(encoding="utf-8")
    fn = js[js.index("function productionBasketballState("):]
    fn = fn[: fn.index("\nfunction ", 1)]
    wire_keys = set(re.findall(r'pick\("([a-z_]+)",', fn))
    assert wire_keys == {
        "shot_clock", "home_fouls", "visitor_fouls",
        "home_bonus", "visitor_bonus", "home_timeouts", "visitor_timeouts",
    }

    state, ruleset = _new_game()
    serialized = HoopsOverlaySerializer.serialize(state)
    assert set(serialized) == wire_keys


def test_shot_clock_is_blank_not_stale_zero_when_the_profile_has_it_disabled():
    state, ruleset = _new_game()  # NFHS-generic ships shot_clock.enabled=false
    serialized = HoopsOverlaySerializer.serialize(state)
    assert serialized["shot_clock"] == ""


def test_shot_clock_is_a_formatted_string_when_the_profile_enables_it():
    state = {"sport": "basketball", "country": "US", "region": None, "association": "NFHS"}
    ruleset = HoopsRulesService.active_ruleset(state)
    ruleset = dict(ruleset)
    ruleset["shot_clock"] = {"enabled": True, "length_seconds": 30, "reset_offensive_rebound_seconds": 20}
    HoopsPeriodService.start_game(state, ruleset)
    serialized = HoopsOverlaySerializer.serialize(state)
    assert serialized["shot_clock"] == "30"


def test_fouls_and_timeouts_are_already_formatted_strings_not_ints():
    state, ruleset = _new_game()
    HoopsRulesService.foul(state, {"team": "visitor", "playerId": "V1", "foulType": "personal"})
    serialized = HoopsOverlaySerializer.serialize(state)
    assert serialized["visitor_fouls"] == "1"
    assert isinstance(serialized["visitor_fouls"], str)
    assert serialized["home_timeouts"] == "5"
    assert isinstance(serialized["home_timeouts"], str)


def test_bonus_enum_is_pinned_to_exactly_three_values():
    # Sec.1: "Fixed 3-value enum, pinned here -- no rendering-side mapping
    # exists yet, so this engine's serializer is the FIRST and ONLY
    # producer of this value." The serializer refuses to emit anything
    # outside {NONE, ONE_AND_ONE, DOUBLE} rather than silently passing an
    # unmapped string through to a renderer with no badge for it.
    assert BONUS_STATES == ("NONE", "ONE_AND_ONE", "DOUBLE")
    state, ruleset = _new_game()
    state["hoops"]["home_bonus"] = "SOMETHING_ELSE"
    with pytest.raises(ValueError, match="pinned enum"):
        HoopsOverlaySerializer.serialize(state)


def test_bonus_reaches_double_and_serializes_correctly_after_five_team_fouls():
    state, ruleset = _new_game()
    for _ in range(5):
        HoopsRulesService.foul(state, {"team": "visitor", "playerId": "V1", "foulType": "personal"})
    serialized = HoopsOverlaySerializer.serialize(state)
    assert serialized["home_bonus"] == "DOUBLE"
    assert serialized["visitor_bonus"] == "NONE"


def test_engine_router_dispatch_functions_produce_the_same_payloads():
    state, ruleset = _new_game()
    HoopsRulesService.shot(state, {"team": "home", "made": True, "points": 2, "shooterId": "H1"})
    HoopsRulesService.foul(state, {"team": "visitor", "playerId": "V1", "foulType": "personal"})

    overlay = engine_router.hoops_overlay_payload(state)
    assert overlay == HoopsOverlaySerializer.serialize(state)
    assert overlay["visitor_fouls"] == "1"

    from hoops_box_score_service import HoopsBoxScoreService
    box = engine_router.hoops_box_score_report(state)
    assert box == HoopsBoxScoreService.report(state)
    assert box["players"]["H1"]["pts"] == 2


def test_shared_fields_are_untouched_by_the_serializer_confirming_no_p3_action_needed():
    # Sec.3/Sec.4 of the contract: period/clock/possession/scores are
    # already correct on the flat state with zero engine action -- the
    # serializer must not attempt to also produce them (that would risk a
    # second, driftable source for fields the renderer already reads
    # directly).
    state, ruleset = _new_game()
    serialized = HoopsOverlaySerializer.serialize(state)
    for shared_field in ("period", "clock_seconds", "possession", "home_score", "visitor_score"):
        assert shared_field not in serialized
