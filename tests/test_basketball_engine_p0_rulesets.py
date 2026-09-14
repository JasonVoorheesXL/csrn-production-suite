"""Basketball engine P0 (docs/BASKETBALL_ENGINE_SCOPING_PLAN.md): RulesProfile-
shaped ruleset documents for basketball, resolving through the existing
ruleset_service machinery with zero code changes to the resolver itself
(only new _CATALOG rows + documents).

Unlike baseball P0 (which shipped NFHS-generic only and deferred any MHSAA
document to P6), this scoping doc's own P0 row calls for an MHSAA overlay
to exist already -- its 3 flagged values (shot clock, bonus rule,
timeouts) shipped as unconfirmed placeholders carried via _source_notes,
not omitted. P6 (2026-09-13) resolved all three: shot_clock.enabled=false
is now a permanent product decision (CSRN never runs a shot clock,
regardless of MHSAA's actual rule), and bonus_rule/timeouts are settled as
"use the NFHS-generic default, not independently confirmed for MHSAA" --
see this document's own _source_notes for the exact reasoning on each.
See docs/BASKETBALL_ENGINE_SCOPING_PLAN.md Sec.4.2/8.1 and the P6 phase-
status entry.

Football's own rulesets/catalog/behaviour are covered by test_ruleset_golden
and must stay byte-identical; baseball's own documents are covered by
test_baseball_engine_p0_rulesets.py and must stay untouched; this file only
covers the new basketball documents.
"""

from __future__ import annotations

import ruleset_service


def test_basketball_us_nfhs_resolves_the_current_five_foul_bonus_rule() -> None:
    resolved = ruleset_service.resolve(country="US", association="NFHS", sport="basketball")
    assert resolved["id"] == "basketball/us-nfhs"
    assert "extends" not in resolved  # fully resolved, no parent document
    assert resolved["jurisdiction"] == {"country": "US", "region": None, "association": "NFHS"}
    assert resolved["period"] == {
        "format": "quarters", "count": 4, "length_seconds": 480,
        "ot_length_seconds": 240, "ot_count_cap": None,
    }
    assert resolved["fouls"]["team_foul_scope"] == "quarter"
    assert resolved["fouls"]["bonus_rule"] == {
        "type": "TWO_SHOT_ON_FIFTH_FOUL", "scope": "quarter", "threshold": 5,
    }
    assert resolved["fouls"]["personal_foul_disqualification"] == 5
    assert resolved["shot_clock"]["enabled"] is False
    assert resolved["timeouts"] == {"full": 3, "short": 2, "carryover_ot": 1, "media_format": None}
    assert resolved["overtime"] == {"length_seconds": 240, "untimed_final_period": False}
    assert resolved["technical"]["shots_awarded"] == 2


def test_basketball_us_nfhs_subvarsity_shortens_the_period_only() -> None:
    resolved = ruleset_service.load_ruleset("basketball/us-nfhs-subvarsity")
    assert "extends" not in resolved  # load_ruleset() flattens the chain
    assert resolved["period"]["length_seconds"] == 360
    assert resolved["period"]["format"] == "quarters"
    # inherited from basketball/us-nfhs, unmodified
    assert resolved["fouls"]["bonus_rule"]["type"] == "TWO_SHOT_ON_FIFTH_FOUL"
    assert resolved["shot_clock"]["enabled"] is False
    # Not yet catalog-resolvable -- no (country, region, association, sport)
    # tuple selects it in P0 (no level/classification concept exists yet
    # to route to it); it exists so the shape is ready.
    for association in ("NFHS", "MHSAA"):
        assert ruleset_service.resolve_id(
            country="US", association=association, sport="basketball"
        ) != "basketball/us-nfhs-subvarsity"


def test_basketball_us_ms_mhsaa_extends_nfhs_with_settled_p6_values() -> None:
    resolved = ruleset_service.resolve(
        country="US", region="MS", association="MHSAA", sport="basketball"
    )
    assert resolved["id"] == "basketball/us-ms-mhsaa"
    assert "extends" not in resolved  # fully resolved
    assert resolved["jurisdiction"] == {"country": "US", "region": "MS", "association": "MHSAA"}
    # Repeats the NFHS-generic values verbatim -- as of P6 this is settled,
    # not a placeholder: shot_clock.enabled=false is a permanent product
    # decision, and bonus_rule/timeouts are deliberately NOT independently
    # confirmed against MHSAA's own handbook (not worth chasing for a
    # broadcast-only product). See this document's own _source_notes.
    assert resolved["shot_clock"]["enabled"] is False
    assert resolved["fouls"]["bonus_rule"]["type"] == "TWO_SHOT_ON_FIFTH_FOUL"
    assert resolved["timeouts"]["full"] == 3
    # inherited, unmodified
    assert resolved["period"]["count"] == 4
    assert resolved["overtime"]["length_seconds"] == 240
    assert resolved["defaults"]["timezone"] == "America/Chicago"


def test_basketball_catalog_fallback_matches_football_and_baseball_pattern() -> None:
    assert ruleset_service.resolve(country="US", region="AL", sport="basketball")["id"] == "basketball/us-nfhs"
    assert ruleset_service.resolve(country="US", sport="basketball")["id"] == "basketball/us-nfhs"
    assert ruleset_service.resolve_id(country="MX", sport="basketball") == ruleset_service.DEFAULT_RULESET_ID


def test_source_notes_present_for_every_flagged_basketball_value() -> None:
    nfhs = ruleset_service.load_ruleset("basketball/us-nfhs")
    for key in (
        "fouls.bonus_rule", "shot_clock.enabled", "period.format",
        "overtime.length_seconds", "fouls.personal_foul_disqualification",
        "technical.shots_awarded", "timeouts",
    ):
        assert key in nfhs["_source_notes"], key

    mhsaa = ruleset_service.load_ruleset("basketball/us-ms-mhsaa")
    for key in ("shot_clock.enabled", "fouls.bonus_rule", "timeouts"):
        assert key in mhsaa["_source_notes"], key

    subvarsity = ruleset_service.load_ruleset("basketball/us-nfhs-subvarsity")
    assert "period.format" in subvarsity["_source_notes"]
    assert "period.length_seconds" in subvarsity["_source_notes"]


def test_football_and_baseball_rulesets_are_untouched_by_the_basketball_catalog_additions() -> None:
    assert ruleset_service.resolve(sport="football")["id"] == "football/us-nfhs"
    assert ruleset_service.resolve(
        country="US", region="MS", association="MHSAA", sport="football"
    )["id"] == "football/us-ms-mhsaa"
    assert ruleset_service.resolve(country="US", association="NFHS", sport="baseball")["id"] == "baseball/us-nfhs"
    assert ruleset_service.resolve(country="US", association="NFHS", sport="softball")["id"] == "softball/us-nfhs"
