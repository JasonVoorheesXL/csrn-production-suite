"""CSRN_FIVE_ISSUES_BUGREPORT.md -- frontend pieces of items 1, 2, and 4
(the backend/service pieces are covered by test_roster_service.py,
test_sponsor_service.py, test_broadcast_service.py, and
test_broadcast_routes_blueprint.py).
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")


def _fn(name: str) -> str:
    start = HTML.index(name)
    rest = HTML[start:]
    for marker in ("\nasync function ", "\nfunction "):
        idx = rest.find(marker, 1)
        if idx != -1:
            return rest[:idx]
    return rest


# --- item 1a: roster sport tagging -----------------------------------------


def test_roster_sport_select_offers_canadian_football() -> None:
    assert '<option>Football</option><option>Canadian Football</option>' in HTML


def test_new_roster_defaults_and_locks_sport_from_the_active_context() -> None:
    body = _fn("function newRoster(){")
    assert "sportContext==='canadian_football'?'Canadian Football'" in body
    assert "sportContext==='football'?'Football':''" in body
    assert "rosterSportSelect.disabled=Boolean(contextRosterSport);" in body


# --- item 1d: sponsor scoping split (owner-confirmed) ----------------------


def test_sponsor_family_label_includes_canadian_football() -> None:
    assert "canadian_football:'Canadian Football'" in HTML


def test_new_sponsor_defaults_sport_from_the_exact_context_not_the_licensing_scope() -> None:
    body = _fn("function newSponsor(){")
    # sportScope is the base_family-collapsed licensing scope; sportContext
    # is the exact one -- using the wrong one here would re-introduce the
    # same American/Canadian leak the roster fix corrects.
    assert "populateSponsorSportOptions(sportContext||'')" in body
    assert "populateSponsorSportOptions(sportScope||'')" not in body


# --- item 4: field position controller Canadian-field awareness -----------


def test_team_spot_from_coord_rescales_by_active_field_length() -> None:
    body = _fn("function teamSpotFromCoord(coord){")
    assert "const L=activeFieldLength();" in body
    assert "const mid=Math.round(L/2);" in body
    assert "if(c===50)return String(mid);" in body
    assert "const yards=c<50?Math.round((c/100)*L):Math.round(L-(c/100)*L);" in body
    # the old hardcoded-100 version is gone, not just shadowed
    assert "return c<50?`${leftName} ${c}`:`${rightName} ${100-c}`" not in HTML


def test_field_position_scale_labels_are_generated_not_hardcoded() -> None:
    assert "function fieldPositionScaleLabels(length){" in HTML
    body = _fn("function fieldPositionScaleLabels(length){")
    assert "'G','10','20','30','40','50','C','50','40','30','20','10','G'" in body  # Canadian, 110
    assert "'G','10','20','30','40','50','40','30','20','10','G'" in body  # US, 100
    assert "function renderFieldPositionScale(source,length){" in HTML


def test_render_field_position_controllers_regenerates_both_scales() -> None:
    body = _fn("function renderFieldPositionControllers(){")
    assert "const length=activeFieldLength();" in body
    assert "renderFieldPositionScale(source,length);" in body


def test_statistician_and_broadcaster_sliders_stay_a_0_to_100_percentage() -> None:
    # The underlying coordinate system (coordFromSpot/spotFromCoord) is
    # already field-length-agnostic percentage math -- min/max 1-99 does
    # NOT need to change, only the display math that was still treating the
    # percentage as a literal 100-yard-field yard count (teamSpotFromCoord,
    # fixed above). Confirms the sliders were deliberately left alone.
    assert 'id="statisticianFieldSlider" type="range" min="1" max="99"' in HTML
    assert 'id="broadcasterFieldSlider" type="range" min="1" max="99"' in HTML
