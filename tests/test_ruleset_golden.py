"""GOLDEN TEST -- the resolved us-ms-mhsaa / us-nfhs football rulesets must
reproduce every value CSRN currently hardcodes, exactly, BEFORE any consumer
is migrated to read from them.

If this test ever fails, the ruleset JSON has drifted from the live
constants -- fix the JSON, do not "adjust" this test.
"""

from __future__ import annotations

import app
import ruleset_service
from penalty_service import PenaltyService


def _ms() -> dict:
    return ruleset_service.resolve(
        country="US", region="MS", association="MHSAA", sport="football"
    )


def test_resolve_maps_mississippi_football_to_the_mhsaa_ruleset() -> None:
    r = _ms()
    assert r["id"] == "football/us-ms-mhsaa"
    assert "extends" not in r  # fully resolved
    assert r["jurisdiction"] == {"country": "US", "region": "MS", "association": "MHSAA"}


def test_penalty_yardages_match_PenaltyService_RULES_exactly() -> None:
    resolved = ruleset_service.penalty_rules(_ms())
    assert resolved == PenaltyService.RULES


def test_field_spots_match_canonical_state_service_literals() -> None:
    field = _ms()["field"]
    # canonical_state_service.enter_kickoff -> _team_own_yard_spot(..., 40)
    assert ruleset_service.field_spot_yardage(field["kickoff_spot"]) == ("own", 40)
    # enter_free_kick -> _team_own_yard_spot(..., 20)
    assert ruleset_service.field_spot_yardage(field["free_kick_spot"]) == ("own", 20)
    # enter_pending_try -> _opponent_yard_spot(..., 3)
    assert ruleset_service.field_spot_yardage(field["try_spot"]) == ("opp", 3)


def test_period_structure_matches_period_service_and_default_state() -> None:
    period = _ms()["period"]
    assert period["quarter_length_seconds"] == 720           # period_service._stop_clock reset
    assert period["quarter_length_seconds"] == app.DEFAULT_STATE["clock_seconds"]
    assert period["count"] == 4
    assert period["quarters"] == ["1", "2", "3", "4", "OT"]  # PeriodService._quarter valid set
    # Round 26 groundwork: the 4-down cycle is becoming ruleset data. This
    # value must stay 4 for every US football ruleset -- canonical_state_
    # service / rules_service / penalty_service all still hardcode ["1st".."4th"]
    # today and will migrate to read this. 3 is Canadian (ships as ca-base).
    assert period["downs_per_set"] == 4


def test_field_geometry_matches_the_hardcoded_0_to_100_scale() -> None:
    # Round 26 groundwork: the bare 0-100 field literal and the red-zone 20
    # are becoming ruleset data. These must reproduce today's geometry exactly
    # for every US ruleset (canonical_state_service end == 100 / 0 touchdown
    # + safety detection, field_state red_zone 0 < to_goal <= 20).
    field = _ms()["field"]
    assert field["length_yards"] == 100
    assert field["end_zone_depth_yards"] == 10
    assert field["red_zone_yards"] == 20
    assert field["no_fair_catch"] is False   # NFHS keeps the fair catch


def test_scoring_values_match_the_current_point_deltas() -> None:
    # game_operations_service.VALID_SCORE_DELTAS = {-1, 1, 2, 3, 6};
    # statistics_service infers FG == 3 / XP == 1 / 2PT == 2 / TD == 6 from
    # the delta. `single` (the rouge) ships in the schema so ca-base can
    # inherit the shape -- a US game never scores one.
    scoring = _ms()["scoring"]
    assert scoring == {
        "touchdown": 6,
        "field_goal": 3,
        "safety": 2,
        "convert_kick": 1,
        "convert_major": 2,
        "single": 1,
    }


def test_downs_sequence_helper_reproduces_the_four_down_cycle() -> None:
    # Round 26: canonical_state_service / rules_service / penalty_service all
    # hardcode ["1st".."4th"] + a "4th -> 1st" wrap + a "4th is terminal"
    # check. downs_sequence / next_down / is_terminal_down must reproduce
    # that exactly for every US ruleset (3 is Canadian, ships as ca-base).
    seq = ruleset_service.downs_sequence(_ms())
    assert seq == ["1st", "2nd", "3rd", "4th"]
    assert ruleset_service.next_down("1st", seq) == "2nd"
    assert ruleset_service.next_down("3rd", seq) == "4th"
    assert ruleset_service.next_down("4th", seq) == "1st"
    assert ruleset_service.is_terminal_down("4th", seq) is True
    assert ruleset_service.is_terminal_down("3rd", seq) is False


def test_field_geometry_helper_matches_the_0_to_100_scale() -> None:
    assert ruleset_service.field_geometry(_ms()) == {
        "length_yards": 100,
        "end_zone_depth_yards": 10,
        "red_zone_yards": 20,
    }
    assert ruleset_service.no_fair_catch(_ms()) is False


def test_service_field_geometry_caches_reproduce_the_0_to_100_scale() -> None:
    # Round 26: canonical_state_service + rules_service resolve their field
    # length / red-zone threshold from the ruleset instead of a bare 100/20
    # literal. For every US ruleset this must round-trip identically to the
    # old hardcoded 0-100 coordinate space.
    from canonical_state_service import CanonicalStateFoundation
    from rules_service import RulesService

    geo = ruleset_service.field_geometry(_ms())
    assert geo["length_yards"] == 100
    assert CanonicalStateFoundation._field_geometry() == geo
    assert RulesService._field_geometry() == geo

    assert CanonicalStateFoundation._spot_to_coord("RIGHT 30") == 70
    assert CanonicalStateFoundation._coord_to_spot(100) == "RIGHT GOAL"
    assert CanonicalStateFoundation._coord_to_spot(50) == "50"
    assert RulesService.spot_to_coord("right 30") == 70
    assert RulesService.coord_to_spot(100) == "RIGHT GOAL"
    assert RulesService.coord_to_spot(50) == "50"


def test_scoring_values_helper_matches_the_current_point_deltas() -> None:
    assert ruleset_service.scoring_values(_ms()) == {
        "touchdown": 6,
        "field_goal": 3,
        "safety": 2,
        "convert_kick": 1,
        "convert_major": 2,
        "single": 1,
    }


def test_service_scoring_caches_match_the_ruleset_point_values() -> None:
    # Round 26 4/7: canonical_state_service + rules_service resolve TD / safety
    # point values from the ruleset. For every US ruleset they must equal the
    # old hardcoded +6 / +2.
    from canonical_state_service import CanonicalStateFoundation
    from rules_service import RulesService

    scoring = ruleset_service.scoring_values(_ms())
    assert scoring["touchdown"] == 6 and scoring["safety"] == 2
    assert CanonicalStateFoundation._scoring() == scoring
    assert RulesService._scoring() == scoring


def test_fair_catch_kept_and_no_yards_absent_for_us_rulesets() -> None:
    # Round 26 5/7 dormancy: NFHS keeps the fair catch, has no restraining
    # zone, and its penalty catalogue has no "No Yards" foul.
    from rules_service import RulesService

    assert _ms()["field"]["no_fair_catch"] is False
    assert _ms()["field"]["no_yards_halo_yards"] == 0
    assert ruleset_service.no_fair_catch(_ms()) is False
    assert ruleset_service.no_yards_halo(_ms()) == 0
    assert RulesService._no_fair_catch() is False
    assert not any(name == "No Yards" for _u, name in ruleset_service.penalty_rules(_ms()))
    base = ruleset_service.load_ruleset("football/us-nfhs")
    assert base["field"]["no_fair_catch"] is False
    assert base["field"]["no_yards_halo_yards"] == 0


def test_single_never_produced_and_field_goal_play_stays_out_for_us_rulesets() -> None:
    # Round 26 4/7 dormancy proof: no NFHS/MHSAA ruleset enables the
    # field_goal play type, and RulesService rejects it exactly as before.
    # (The single/rouge has no ruleset "enable" flag -- it simply never
    # occurs because nothing emits a SINGLE event in a US game -- but the
    # schema still carries scoring.single so ca-base can inherit the shape.)
    from rules_service import RulesService

    assert _ms()["field"]["field_goal_play"] is False
    assert ruleset_service.valid_play_types(_ms()) == {"run", "pass", "kickoff", "punt"}
    assert RulesService._valid_play_types() == {"run", "pass", "kickoff", "punt"}
    assert "field_goal" not in RulesService._valid_play_types()
    # base NFHS document carries the flag at the same value
    base = ruleset_service.load_ruleset("football/us-nfhs")
    assert base["field"]["field_goal_play"] is False


def test_active_ruleset_is_the_single_resolver_and_caches_by_id() -> None:
    # Round 26 6/7: every engine consumer resolves through
    # ruleset_service.active_ruleset(); derived values are cached keyed by
    # the resolved ruleset id (dicts, not process-wide singletons).
    from canonical_state_service import CanonicalStateFoundation
    from penalty_service import PenaltyService
    from period_service import PeriodService
    from rules_service import RulesService

    assert ruleset_service.active_ruleset_id() == "football/us-nfhs"
    assert ruleset_service.active_ruleset_id({}) == "football/us-nfhs"
    assert (
        ruleset_service.active_ruleset_id(
            {"country": "US", "region": "MS", "association": "MHSAA"}
        )
        == "football/us-ms-mhsaa"
    )
    assert ruleset_service.active_ruleset()["id"] == "football/us-nfhs"

    # Routing every current game through the base is a no-op: us-nfhs and
    # us-ms-mhsaa carry identical engine values.
    nfhs = ruleset_service.active_ruleset()
    mhsaa = ruleset_service.active_ruleset(
        {"country": "US", "region": "MS", "association": "MHSAA"}
    )
    for key in ("period", "field", "scoring", "penalties"):
        assert nfhs[key] == mhsaa[key]

    # Every service cache is now an id-keyed dict.
    CanonicalStateFoundation._field_geometry()
    CanonicalStateFoundation._downs_sequence()
    CanonicalStateFoundation._scoring()
    CanonicalStateFoundation._field_yards()
    PenaltyService._penalty_rules()
    PenaltyService._downs_sequence()
    PeriodService._period()
    RulesService._downs_sequence()
    RulesService._field_geometry()
    RulesService._scoring()
    RulesService._valid_play_types()
    RulesService._no_fair_catch()
    for cache in (
        CanonicalStateFoundation._field_geometry_cache,
        CanonicalStateFoundation._downs_sequence_cache,
        CanonicalStateFoundation._scoring_cache,
        CanonicalStateFoundation._field_yards_cache,
        PenaltyService._penalty_rules_cache,
        PenaltyService._downs_sequence_cache,
        PeriodService._period_cache,
        RulesService._downs_sequence_cache,
        RulesService._field_geometry_cache,
        RulesService._scoring_cache,
        RulesService._valid_play_types_cache,
        RulesService._no_fair_catch_cache,
    ):
        assert isinstance(cache, dict)
        assert "football/us-nfhs" in cache


def test_classification_and_reserved_ids_match_reconcile_5a_csrn_ids() -> None:
    cls = _ms()["classification"]
    assert cls["classes"] == ["1A", "2A", "3A", "4A", "5A", "6A", "7A"]  # SUPPORTED_CLASSES
    # reconcile_5a_csrn_ids: MS5A-001 = Caledonia, MS5A-002 = New Hope
    assert cls["reserved_ids"] == {"MS5A-001": "caledonia", "MS5A-002": "new-hope"}
    assert cls["id_format"] == "{state}{class}-{seq:03d}"    # next_csrn_school_id shape


def test_jurisdiction_defaults_match_current_hardcodes() -> None:
    defaults = _ms()["defaults"]
    assert defaults["timezone"] == "America/Chicago"   # DEFAULT_CONFIG.broadcast_defaults.timezone
    assert defaults["association"] == "MHSAA"          # dragonfly_service association= default


# --- the base ruleset is generic: MS-specifics live only in the child -----

def test_base_nfhs_ruleset_carries_no_mississippi_specifics() -> None:
    base = ruleset_service.load_ruleset("football/us-nfhs")
    assert base["classification"]["reserved_ids"] == {}
    assert base["classification"]["scheme"] is None
    assert base["defaults"]["timezone"] is None
    assert base["defaults"]["association"] == "NFHS"
    # ...but the rules themselves are identical (MHSAA uses NFHS rules)
    assert ruleset_service.penalty_rules(base) == PenaltyService.RULES
    assert base["field"] == _ms()["field"]
    assert base["period"] == _ms()["period"]


def test_extends_chain_and_fallback() -> None:
    assert ruleset_service.resolve(country="US", sport="football")["id"] == "football/us-nfhs"
    # unknown jurisdiction -> generic base, never the MS document
    assert ruleset_service.resolve(country="CA", region="ON", sport="football")["id"] == "football/us-nfhs"
