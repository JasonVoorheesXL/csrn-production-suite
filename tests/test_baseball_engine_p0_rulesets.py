"""Baseball/softball engine P0 (docs/BASEBALL_SOFTBALL_ENGINE_SCOPING_PLAN.md,
docs/CSRN_NFHS_Baseball_Softball_Rules_Engine_Spec_2026.docx): RulesProfile-
shaped ruleset documents for the two sports, resolving through the existing
ruleset_service machinery with zero code changes to the resolver itself
(only new _CATALOG rows + documents) -- and the per-game effective-profile
stamp that lands at broadcast load time.

Football's own rulesets/catalog/behaviour are covered by test_ruleset_golden
and must stay byte-identical; this file only covers the new baseball/
softball documents and the stamping mechanism.
"""

from __future__ import annotations

import ruleset_service


def test_bat_ball_base_is_a_shared_extends_parent_never_directly_resolved() -> None:
    base = ruleset_service.load_ruleset("bat-ball-base")
    assert "extends" not in base  # it is the root of the chain
    assert base["regulation"]["scheduledInnings"] == 7
    assert base["regulation"]["minimumRegulationInnings"] == 7
    assert base["runRules"] == []
    assert base["tieBreaker"]["mode"] == "NONE"
    assert base["lineup"]["courtesyRunnerPolicy"]["enabled"] is False
    assert base["field"]["doubleFirstBaseRequired"] is False
    # no (country, region, association, sport) tuple maps to it -- it is
    # only ever reached via "extends", never resolve()/resolve_id()
    for sport in ("football", "baseball", "softball"):
        assert ruleset_service.resolve_id(sport=sport) != "bat-ball-base"


def test_baseball_us_nfhs_extends_the_shared_base() -> None:
    resolved = ruleset_service.resolve(country="US", association="NFHS", sport="baseball")
    assert resolved["id"] == "baseball/us-nfhs"
    assert "extends" not in resolved  # fully resolved
    assert resolved["jurisdiction"] == {"country": "US", "region": None, "association": "NFHS"}
    # inherited from bat-ball-base, unmodified
    assert resolved["regulation"]["scheduledInnings"] == 7
    assert resolved["tieBreaker"]["mode"] == "NONE"
    assert resolved["runRules"] == []
    # baseball-specific overrides
    assert resolved["lineup"]["reentryPolicy"] == "STARTER_ONCE"
    assert resolved["lineup"]["dhPolicy"] == "NONE_TRADITIONAL_OR_PLAYER_DH"
    assert resolved["lineup"]["dpFlexPolicy"] is None
    assert resolved["runnerControl"]["lookBackRule"] is False
    assert resolved["lineup"]["courtesyRunnerPolicy"]["enabled"] is False


def test_softball_us_nfhs_extends_the_shared_base_with_its_own_differences() -> None:
    resolved = ruleset_service.resolve(country="US", association="NFHS", sport="softball")
    assert resolved["id"] == "softball/us-nfhs"
    assert "extends" not in resolved
    assert resolved["jurisdiction"] == {"country": "US", "region": None, "association": "NFHS"}
    # inherited
    assert resolved["regulation"]["scheduledInnings"] == 7
    # softball-specific overrides, distinct from baseball's
    assert resolved["lineup"]["reentryPolicy"] == "ANY_PLAYER_ONCE"
    assert resolved["lineup"]["dpFlexPolicy"] == "NFHS_2026"
    assert resolved["lineup"]["dhPolicy"] is None
    assert resolved["runnerControl"]["lookBackRule"] is True
    assert resolved["communications"]["defensiveOneWayRecipients"] == ["CATCHER"]


def test_baseball_and_softball_have_independent_reentry_and_special_lineup_rules() -> None:
    # Spec Sec.16 differences matrix: re-entry, special lineup role, and
    # runner control all differ between the two sports even though they
    # share the same regulation/run-rule/suspension mechanism shape.
    bb = ruleset_service.resolve(sport="baseball")
    sb = ruleset_service.resolve(sport="softball")
    assert bb["lineup"]["reentryPolicy"] != sb["lineup"]["reentryPolicy"]
    assert bb["lineup"]["dhPolicy"] and not sb["lineup"]["dhPolicy"]
    assert sb["lineup"]["dpFlexPolicy"] and not bb["lineup"]["dpFlexPolicy"]
    assert bb["runnerControl"]["lookBackRule"] is False
    assert sb["runnerControl"]["lookBackRule"] is True
    # both share the exact same regulation/tieBreaker/suspendedGame shape
    # (inherited unmodified from bat-ball-base)
    for key in ("regulation", "tieBreaker", "suspendedGame", "runRules", "timeLimit"):
        assert bb[key] == sb[key]


def test_baseball_catalog_fallback_matches_football_pattern() -> None:
    # Same fallback shape as football: an unrecognised region/association
    # for a known (country, sport) falls back to the generic document, and
    # an unrecognised country still resolves (via DEFAULT_RULESET_ID) rather
    # than raising.
    assert ruleset_service.resolve(country="US", region="AL", sport="baseball")["id"] == "baseball/us-nfhs"
    assert ruleset_service.resolve(country="US", sport="softball")["id"] == "softball/us-nfhs"
    # DEFAULT_RULESET_ID is football/us-nfhs -- an unknown (country, sport)
    # combination with no baseball/softball catalog match at all falls back
    # to it exactly like football's own fallback test does, since resolve_id
    # has no baseball-specific default.
    assert ruleset_service.resolve_id(country="MX", sport="baseball") == ruleset_service.DEFAULT_RULESET_ID


def test_source_notes_present_for_every_flagged_baseball_softball_value() -> None:
    # T1 spec re-pin discipline mirror: every value this round could not
    # verify against the licensed NFHS rules book (as opposed to genuine
    # NFHS structural facts stated plainly in the spec) carries a
    # _source_notes entry, same convention as football/ca-base.json.
    base = ruleset_service.load_ruleset("bat-ball-base")
    for key in ("minimumRegulationInnings", "tieBreaker.mode", "field.doubleFirstBaseRequired"):
        assert key in base["_source_notes"], key

    bb = ruleset_service.load_ruleset("baseball/us-nfhs")
    for key in ("lineup.reentryPolicy", "lineup.dhPolicy", "lineup.courtesyRunnerPolicy.enabled"):
        assert key in bb["_source_notes"], key

    sb = ruleset_service.load_ruleset("softball/us-nfhs")
    for key in (
        "lineup.reentryPolicy", "lineup.dpFlexPolicy",
        "lineup.courtesyRunnerPolicy.enabled", "runnerControl.lookBackRule",
        "communications.defensiveOneWayRecipients",
    ):
        assert key in sb["_source_notes"], key


def test_mhsaa_state_overlays_are_not_shipped_yet() -> None:
    # P6 (deferred, gated on the owner's own MHSAA handbook confirmation) --
    # a Mississippi-specific baseball/softball ruleset must not exist until
    # then, matching docs/BASEBALL_SOFTBALL_ENGINE_SCOPING_PLAN.md P6.
    for rid in ("baseball/us-ms-mhsaa", "softball/us-ms-mhsaa"):
        try:
            ruleset_service.load_ruleset(rid)
        except FileNotFoundError:
            continue
        raise AssertionError(f"{rid} should not be shipped before P6")
    assert ruleset_service.resolve_id(
        country="US", region="MS", association="MHSAA", sport="baseball"
    ) == "baseball/us-nfhs"
    assert ruleset_service.resolve_id(
        country="US", region="MS", association="MHSAA", sport="softball"
    ) == "softball/us-nfhs"


def test_football_rulesets_are_untouched_by_the_baseball_catalog_additions() -> None:
    assert ruleset_service.resolve(sport="football")["id"] == "football/us-nfhs"
    assert ruleset_service.resolve(
        country="US", region="MS", association="MHSAA", sport="football"
    )["id"] == "football/us-ms-mhsaa"
