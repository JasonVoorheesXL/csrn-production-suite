from __future__ import annotations

import sport_families as sf


def test_families_and_tiles() -> None:
    # Five real licensable families, football first (keeps a single-sport
    # install's login screen visually unchanged), then the gateway tile.
    assert sf.SPORT_FAMILIES == ("football", "basketball", "baseball", "softball", "soccer")
    assert sf.LOGIN_TILES == sf.SPORT_FAMILIES + ("all_others",)
    assert sf.GATEWAY == "all_others"


def test_gateway_is_never_a_context() -> None:
    # "all_others" opens a list; it is not something you can be "in".
    assert sf.normalize_sport("all_others") == "all_others"
    assert sf.context_is_licensed("all_others", sf.SPORT_FAMILIES) is False
    assert sf.is_engine_ready("all_others") is False


def test_normalize_sport_families_codes_and_case() -> None:
    assert sf.normalize_sport("Football") == "football"
    assert sf.normalize_sport("  BASKETBALL ") == "basketball"
    assert sf.normalize_sport("FB") == "football"
    assert sf.normalize_sport("bsb") == "baseball"
    assert sf.normalize_sport("sc") == "soccer"
    assert sf.normalize_sport("other") == "all_others"


def test_normalize_sport_canadian_football_spellings() -> None:
    for spelling in ("canadian_football", "Canadian Football", "canadian-football", "CFL", "canadian"):
        assert sf.normalize_sport(spelling) == "canadian_football"


def test_normalize_sport_rejects_unknown() -> None:
    assert sf.normalize_sport("cricket") == ""
    assert sf.normalize_sport("") == ""
    assert sf.normalize_sport(None) == ""


def test_base_family_collapses_canadian_football_onto_football() -> None:
    # Invariants 1 & 2: licensing and roster/sponsor scoping both key off this.
    assert sf.base_family("canadian_football") == "football"
    assert sf.base_family("CFL") == "football"
    assert sf.base_family("football") == "football"
    assert sf.base_family("basketball") == "basketball"
    assert sf.base_family("hockey") == "hockey"


def test_engine_ready_is_football_baseball_softball_and_basketball() -> None:
    # Football (+ canadian_football, same module), baseball and softball
    # (docs/BASEBALL_SOFTBALL_ENGINE_SCOPING_PLAN.md), and now basketball
    # (docs/BASKETBALL_ENGINE_SCOPING_PLAN.md P5) have a broadcast engine
    # today. The other families are real/licensable but not ready.
    assert sf.is_engine_ready("football") is True
    assert sf.is_engine_ready("canadian_football") is True
    assert sf.is_engine_ready("baseball") is True
    assert sf.is_engine_ready("softball") is True
    assert sf.is_engine_ready("basketball") is True
    assert sf.is_engine_ready("soccer") is False
    assert sf.is_engine_ready("hockey") is False


def test_family_sport_options_separates_licensed_not_ready_from_unlicensed() -> None:
    # basketball now has an engine (P5) -- soccer is the still-engineless
    # family this test uses as its "licensed but not ready" example instead
    # (same swap baseball's own P5 made when baseball stopped being that
    # example).
    opts = {o["family"]: o for o in sf.family_sport_options(["football", "soccer"])}
    # football: licensed + engine -> available
    assert opts["football"] == {
        "family": "football", "label": "Football",
        "licensed": True, "engine_ready": True, "available": True,
    }
    # soccer: licensed, but no engine -> NOT available, and the reason is
    # "engine not ready", not "unlicensed"
    assert opts["soccer"]["licensed"] is True
    assert opts["soccer"]["engine_ready"] is False
    assert opts["soccer"]["available"] is False
    # baseball: not licensed (but does have an engine)
    assert opts["baseball"]["licensed"] is False
    assert opts["baseball"]["available"] is False


def test_resolve_licensed_families_wildcard_and_intersection() -> None:
    assert sf.resolve_licensed_families(["*"]) == list(sf.SPORT_FAMILIES)
    assert sf.resolve_licensed_families(["Basketball", "Football"]) == ["football", "basketball"]
    assert sf.resolve_licensed_families([]) == []
    # A licence that (wrongly) lists canadian_football still grants football.
    assert sf.resolve_licensed_families(["canadian_football"]) == ["football"]


def test_one_football_license_covers_both_football_contexts() -> None:
    # Invariant 1: no second purchase for Canadian football.
    licensed = sf.resolve_licensed_families(["football"])
    assert sf.context_is_licensed("football", licensed) is True
    assert sf.context_is_licensed("canadian_football", licensed) is True
    assert sf.context_is_licensed("basketball", licensed) is False
    # Coming-soon sports are never "licensed" -- there is nothing to enter.
    assert sf.context_is_licensed("hockey", licensed) is False


def test_other_sport_options_marks_canadian_football_available_with_football_license() -> None:
    options = sf.other_sport_options(["football"])
    by_context = {o["context"]: o for o in options}
    assert by_context["canadian_football"] == {
        "context": "canadian_football",
        "label": "Canadian Football",
        "available": True,
    }
    assert by_context["hockey"]["available"] is False
    assert by_context["tennis"]["available"] is False
    # No football license -> Canadian football not available either.
    assert {o["context"]: o["available"] for o in sf.other_sport_options(["basketball"])}[
        "canadian_football"
    ] is False


def test_sport_context_view_reports_scope_for_canadian_football() -> None:
    view = sf.sport_context_view("canadian_football", ["football"])
    assert view["sport_context"] == "canadian_football"
    assert view["sport_scope"] == "football"          # invariant 2: shared pool
    assert view["licensed_sports"] == ["football"]
    assert view["all_sports_licensed"] is False
    assert any(o["context"] == "canadian_football" and o["available"] for o in view["other_sports"])
    # family_sports is embedded for the login tiles / top-nav switcher.
    fams = {f["family"]: f for f in view["family_sports"]}
    assert fams["football"]["available"] is True
    assert fams["basketball"]["available"] is False


def test_sport_context_view_blank_and_gateway_read_as_none() -> None:
    for stored in ("", "all_others", "nonsense"):
        view = sf.sport_context_view(stored, list(sf.SPORT_FAMILIES))
        assert view["sport_context"] == ""
        assert view["sport_scope"] == ""
    assert sf.sport_context_view("", ["*"] and list(sf.SPORT_FAMILIES))["all_sports_licensed"] is True
