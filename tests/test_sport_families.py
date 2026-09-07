from __future__ import annotations

import sport_families


def test_families_are_stable_and_football_leads() -> None:
    # The login screen renders icons in this order; football first keeps the
    # single-sport install's screen visually unchanged.
    assert sport_families.SPORT_FAMILIES[0] == "football"
    assert set(sport_families.SPORT_FAMILIES) == {
        "football",
        "basketball",
        "baseball",
        "softball",
        "volleyball",
        "soccer",
    }


def test_normalize_family_accepts_names_codes_and_case() -> None:
    assert sport_families.normalize_family("Football") == "football"
    assert sport_families.normalize_family("  BASKETBALL ") == "basketball"
    assert sport_families.normalize_family("FB") == "football"
    assert sport_families.normalize_family("bsb") == "baseball"
    assert sport_families.normalize_family("sc") == "soccer"


def test_normalize_family_rejects_unknown_and_subvariants() -> None:
    # American vs Canadian football is NOT a family -- it is resolved inside
    # the football context by the Round 26 jurisdiction picker.
    assert sport_families.normalize_family("canadian-football") == ""
    assert sport_families.normalize_family("") == ""
    assert sport_families.normalize_family(None) == ""
    assert sport_families.normalize_family("hockey") == ""


def test_resolve_licensed_families_expands_wildcard() -> None:
    assert sport_families.resolve_licensed_families(["*"]) == list(
        sport_families.SPORT_FAMILIES
    )
    assert sport_families.resolve_licensed_families(["football", "*"]) == list(
        sport_families.SPORT_FAMILIES
    )


def test_resolve_licensed_families_intersects_in_display_order() -> None:
    assert sport_families.resolve_licensed_families(["Basketball", "Football"]) == [
        "football",
        "basketball",
    ]
    # Unknown entries are dropped, not errored.
    assert sport_families.resolve_licensed_families(["football", "curling"]) == [
        "football"
    ]


def test_resolve_licensed_families_empty_grants_nothing() -> None:
    # Matches EntitlementService.allows(): an empty sports list allows no
    # sport-scoped feature.
    assert sport_families.resolve_licensed_families([]) == []
    assert sport_families.resolve_licensed_families(None) == []
