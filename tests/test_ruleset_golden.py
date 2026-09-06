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


def test_scoring_values_helper_matches_the_current_point_deltas() -> None:
    assert ruleset_service.scoring_values(_ms()) == {
        "touchdown": 6,
        "field_goal": 3,
        "safety": 2,
        "convert_kick": 1,
        "convert_major": 2,
        "single": 1,
    }


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
