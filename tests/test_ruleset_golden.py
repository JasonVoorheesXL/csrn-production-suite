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


def test_single_restart_spot_is_absent_for_us_and_flagged_unverified_for_ca() -> None:
    # Round 26 Phase B 4d: after conceding a single/rouge the team scored
    # upon restarts from field.single_restart_spot. US rulesets have no
    # single, so it is null/"".
    for rid in ("football/us-nfhs", "football/us-ms-mhsaa"):
        assert ruleset_service.single_restart_spot(ruleset_service.load_ruleset(rid)) == ""
    ca = ruleset_service.load_ruleset("football/ca-base")
    assert ruleset_service.single_restart_spot(ca) == "own_35"
    assert ruleset_service.single_restart_spot(
        ruleset_service.load_ruleset("football/ca-cjfl-ofc")
    ) == "own_35"
    # the value is a best guess -- it must be flagged, not shipped as fact
    assert "single_restart_spot" in ca["_source_notes"]
    assert "UNVERIFIED" in ca["_source_notes"]["single_restart_spot"] or \
        "NOT verified" in ca["_source_notes"]["single_restart_spot"]


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
    # an unknown US jurisdiction -> generic US base, never the MS document
    assert (
        ruleset_service.resolve(country="US", region="AL", sport="football")["id"]
        == "football/us-nfhs"
    )
    # a wholly unknown country still falls back to the generic US base
    assert (
        ruleset_service.resolve(country="MX", region="DIF", sport="football")["id"]
        == "football/us-nfhs"
    )


# --- Round 26 7/7: the Canadian ruleset documents --------------------------

def _ca() -> dict:
    return ruleset_service.resolve(country="CA", sport="football")


def _cjfl() -> dict:
    return ruleset_service.resolve(
        country="CA", region="ON", association="CJFL", sport="football"
    )


def test_ca_catalogue_entries_resolve() -> None:
    assert _ca()["id"] == "football/ca-base"
    assert _cjfl()["id"] == "football/ca-cjfl-ofc"
    # generic Canadian, not routed to the Ontario/CJFL document
    assert ruleset_service.resolve(country="CA", region="BC", sport="football")["id"] == "football/ca-base"
    # even Ontario without the CJFL association is generic ca-base
    assert ruleset_service.resolve(country="CA", region="ON", sport="football")["id"] == "football/ca-base"


def test_ca_base_carries_the_canadian_shape() -> None:
    ca = _ca()
    assert ruleset_service.downs_sequence(ca) == ["1st", "2nd", "3rd"]
    geo = ruleset_service.field_geometry(ca)
    assert geo["length_yards"] == 110
    assert geo["end_zone_depth_yards"] == 20
    assert ruleset_service.no_fair_catch(ca) is True
    assert ruleset_service.no_yards_halo(ca) == 5
    assert ruleset_service.scoring_values(ca)["single"] == 1
    # No Yards is a Canadian-only Special Teams foul; the rest of the
    # catalogue is inherited from us-nfhs.
    pens = ruleset_service.penalty_rules(ca)
    assert ("Special Teams", "No Yards") in pens
    assert ("Offensive", "False Start") in pens  # inherited
    # uncertain values are flagged, not silently shipped as fact
    assert "try_spot" in ca["_source_notes"]
    assert "no_yards_halo_yards" in ca["_source_notes"]


def test_ca_cjfl_ofc_extends_ca_base() -> None:
    cjfl = _cjfl()
    assert "extends" not in cjfl  # fully resolved
    assert cjfl["jurisdiction"] == {"country": "CA", "region": "ON", "association": "CJFL"}
    assert cjfl["defaults"]["timezone"] == "America/Toronto"
    # inherits the Canadian shape from ca-base
    assert ruleset_service.downs_sequence(cjfl) == ["1st", "2nd", "3rd"]
    assert ruleset_service.field_geometry(cjfl)["length_yards"] == 110
    assert ruleset_service.no_fair_catch(cjfl) is True


def test_field_spot_yardage_clamps_to_the_rulesets_own_midfield() -> None:
    # Round 26 Phase B: field_spot_yardage() turns a ruleset spec ("own_35")
    # into a yard int for canonical_state_service._field_yards. The clamp is
    # the field's half-way point, not a hardcoded 50 -- so a Canadian
    # "own_55" (midfield of a 110-yd field) is not pulled back to 50.
    assert ruleset_service.field_spot_yardage("own_40") == ("own", 40)          # default length 100
    assert ruleset_service.field_spot_yardage("own_60") == ("own", 50)          # clamp at 100/2
    assert ruleset_service.field_spot_yardage("own_55", 110) == ("own", 55)     # 110/2 = 55
    assert ruleset_service.field_spot_yardage("opp_70", 110) == ("opp", 55)
    # nothing shipped hits the old clamp -- every ruleset's specs are <= 40
    for rid in ("football/us-nfhs", "football/us-ms-mhsaa", "football/ca-base", "football/ca-cjfl-ofc"):
        field = ruleset_service.load_ruleset(rid)["field"]
        for spec_key in ("kickoff_spot", "free_kick_spot", "try_spot", "touchback_spot"):
            spec = field.get(spec_key)
            if spec:
                _side, yard = ruleset_service.field_spot_yardage(spec, field.get("length_yards", 100))
                assert yard <= 40, (rid, spec_key, spec, yard)


def test_coordinate_space_is_state_aware_for_canadian_field_length() -> None:
    # Round 26 Phase B 4a: the scrimmage coordinate space is 0..length_yards
    # -- 0-100 for NFHS, 0-110 for a Canadian game. Threading state through
    # the coord helpers is what makes a 110-yard drive actually reachable.
    from canonical_state_service import CanonicalStateFoundation as C
    from rules_service import RulesService

    us = {}  # no jurisdiction -> generic US base
    ca = {"country": "CA", "region": "ON", "association": "CJFL"}

    # goal line: 100 vs 110
    assert C._spot_to_coord("RIGHT GOAL", us) == 100
    assert C._spot_to_coord("RIGHT GOAL", ca) == 110
    assert RulesService.spot_to_coord("right goal", us) == 100
    assert RulesService.spot_to_coord("right goal", ca) == 110

    # "RIGHT 45" = 45 yds from the right goal: coord 55 on a 100 field,
    # coord 65 on a 110 field
    assert C._spot_to_coord("RIGHT 45", us) == 55
    assert C._spot_to_coord("RIGHT 45", ca) == 65
    assert C._coord_to_spot(65, ca) == "RIGHT 45"
    # Canadian centre line is the 55
    assert C._coord_to_spot(55, ca) == "55"
    assert C._coord_to_spot(55, us) == "RIGHT 45"

    # yards_to_goal / field_state report at the right scale
    ca_state = dict(ca, ball_spot="LEFT 20", possession="home", home_direction="right")
    fs = C.field_state(ca_state)
    assert fs["length_yards"] == 110
    assert fs["end_zone_depth_yards"] == 20
    assert fs["yards_to_goal"] == 90  # 110 - 20

    us_state = {"ball_spot": "LEFT 20", "possession": "home", "home_direction": "right"}
    assert C.field_state(us_state)["yards_to_goal"] == 80
    assert C.field_state(us_state)["length_yards"] == 100


def test_available_rulesets_exposes_jurisdiction_for_the_picker() -> None:
    # Round 26 Phase B 1/5: the broadcast-creation jurisdiction picker
    # groups on available_rulesets()' country / region / association.
    rows = {r["id"]: r for r in ruleset_service.available_rulesets()}
    assert set(rows) == {
        "football/us-nfhs",
        "football/us-ms-mhsaa",
        "football/ca-base",
        "football/ca-cjfl-ofc",
    }
    assert (rows["football/us-nfhs"]["country"], rows["football/us-nfhs"]["region"],
            rows["football/us-nfhs"]["association"]) == ("US", None, "NFHS")
    assert (rows["football/us-ms-mhsaa"]["country"], rows["football/us-ms-mhsaa"]["region"],
            rows["football/us-ms-mhsaa"]["association"]) == ("US", "MS", "MHSAA")
    assert (rows["football/ca-base"]["country"], rows["football/ca-base"]["region"],
            rows["football/ca-base"]["association"]) == ("CA", None, None)
    assert (rows["football/ca-cjfl-ofc"]["country"], rows["football/ca-cjfl-ofc"]["region"],
            rows["football/ca-cjfl-ofc"]["association"]) == ("CA", "ON", "CJFL")
    for row in rows.values():
        assert row["sport"] == "football"
        # the tuple the picker will store must resolve straight back to this
        # same ruleset id
        assert ruleset_service.resolve_id(
            country=row["country"], region=row["region"],
            association=row["association"], sport="football",
        ) == row["id"]


def test_field_goal_play_is_disabled_on_every_shipped_ruleset() -> None:
    # Engine reality: no field-goal play-type handler exists, so no shipped
    # ruleset -- US or Canadian -- may enable it. This pins that alignment
    # so ca-base can't later drift to field_goal_play: true ahead of the
    # engine.
    for rid in (
        "football/us-nfhs",
        "football/us-ms-mhsaa",
        "football/ca-base",
        "football/ca-cjfl-ofc",
    ):
        ruleset = ruleset_service.load_ruleset(rid)
        assert ruleset["field"].get("field_goal_play") is False, rid
        assert "field_goal" not in ruleset_service.valid_play_types(ruleset), rid
