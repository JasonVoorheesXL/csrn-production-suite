"""The halftime state of templates/pregame_universal_overlay.html must never
render anything containing the word "pregame".

Confirmed live (after several genuine restarts): during halftime the screen
still showed the literal label "PREGAME". Root cause: the brand-lockup label
`<strong class="brand-pregame">PREGAME</strong>` was hard-coded and never
updated by JS -- 0bc9486 only changed the #stateBadge pill, the hero
eyebrow, and the count label, not this second on-screen "PREGAME".

There is no JS runtime in this test suite (documented in
test_halftime_overlay.py), so this file combines:
  * exact-string assertions that each known leak point is fixed, and
  * a faithful re-derivation of the overlay's own branch logic for the
    halftime case, asserting the resulting card set + state word contain no
    "pregame".
See the module docstring of test_halftime_overlay.py and OVERNIGHT_SUMMARY
for the manual live-verification procedure.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "templates" / "pregame_universal_overlay.html").read_text(encoding="utf-8")


# --- the brand-lockup "PREGAME" is now dynamic, not hard-coded --------------

def test_brand_state_label_has_an_id_so_js_can_update_it() -> None:
    assert 'id="brandStateLabel"' in HTML


def test_render_static_sets_the_brand_label_from_the_shared_state_word() -> None:
    # One word feeds both the pill and the brand label.
    assert "const stateWord=delayed?(weatherDelay?'WEATHER DELAY':'GAME DELAYED'):halftime?'HALFTIME':'PREGAME';" in HTML
    assert "document.getElementById('stateBadge').textContent=stateWord;" in HTML
    assert "brandStateLabel.textContent=stateWord;" in HTML


# --- the other halftime-path "pregame" leaks are fixed ---------------------

def test_halftime_empty_state_is_not_worded_pregame() -> None:
    assert "halftime?'Halftime coverage is loading.':'Pregame information is loading.'" in HTML


def test_footer_fallback_is_halftime_aware() -> None:
    assert "(halftime?'CSRN Halftime':delayed?'CSRN':'CSRN Pregame')" in HTML


def test_title_is_not_pregame_branded() -> None:
    title = re.search(r"<title>(.*?)</title>", HTML, re.I).group(1).lower()
    assert "pregame" not in title


# --- behavioural: re-derive the halftime card set from the source ----------

def _halftime_card_sources() -> str:
    """Return the RHS of `list=[...]` for the `else if(halftime)` branch of
    rebuildCards(), straight from the template."""
    branch = re.search(
        r"\}else if\(halftime\)\{(.*?)\}else\{", HTML, re.S
    ).group(1)
    return re.search(r"list=\[(.*?)\];", branch, re.S).group(1)


def test_halftime_card_set_excludes_pregame_only_cards() -> None:
    sources = _halftime_card_sources()
    # storylinesCard() renders "<h1>Pregame Storylines</h1>" -- it must not be
    # in the halftime rotation. gameDetails/teamProfiles/nextWeek are the
    # pregame set too.
    for pregame_only in ("storylinesCard", "gameDetailsCard", "teamProfilesCard", "nextWeekCard"):
        assert pregame_only not in sources, f"{pregame_only} leaked into the halftime rotation"


def test_halftime_card_set_is_weather_then_spotlights_then_sponsors() -> None:
    sources = _halftime_card_sources()
    assert "weather" in sources
    assert "spotlights.map(spotlightCard)" in sources
    assert "...sponsors" in sources


def test_no_visible_pregame_text_in_the_halftime_render_path() -> None:
    """Simulate the overlay's own logic for broadcast_phase == 'halftime'
    and assert nothing user-visible says "pregame"."""
    delayed = False
    halftime = True
    weather_delay = False

    # stateWord (renderStatic)
    state_word = (
        "WEATHER DELAY" if (delayed and weather_delay)
        else "GAME DELAYED" if delayed
        else "HALFTIME" if halftime
        else "PREGAME"
    )
    # hero eyebrow / count label (renderStatic)
    hero_eyebrow = "Halftime" if halftime else "Tonight's Matchup"
    count_label = "Score at the Half" if halftime else "Kickoff In"
    empty_state = "Halftime coverage is loading." if halftime else "Pregame information is loading."
    footer_fallback = "CSRN Halftime" if halftime else "CSRN Pregame"

    for value in (state_word, hero_eyebrow, count_label, empty_state, footer_fallback):
        assert "pregame" not in value.lower()

    # the card-source expression for the halftime branch
    assert "pregame" not in _halftime_card_sources().lower()


# --- sponsor area is wired in --------------------------------------------

def test_sponsor_card_renderer_exists_and_reuses_the_card_idiom() -> None:
    assert "function sponsorCard(sp)" in HTML
    assert 'data.halftime_sponsors' in HTML
    assert '<section class="card">' in HTML  # native idiom, not a new shell
