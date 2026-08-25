"""Regression coverage for the halftime/delay overlay build
(templates/pregame_universal_overlay.html), 2026-08-25:

1. HALFTIME banner -- follows the existing .statebadge pattern (PREGAME/
   GAME DELAYED already used it).
2. Weather -- reused as-is via the existing weatherCard(), sourced from
   VenueWeatherService (pregame_presentation.py's _weather()); no new
   tracking. Covered behaviorally in test_pregame_presentation.py and by a
   real end-to-end Flask check against tonight's broadcast data (not
   committed as a test -- see session notes).
3. Spotlight rotation -- native page markup (spotlightCard(), matching this
   page's own .card/.card-kicker/.info idiom), sourced from real event
   history via pregame_presentation.py's _first_half_spotlights()
   (tested in test_pregame_presentation.py), wired into the page's
   existing rebuildCards()/cards[]/tick() rotation -- not a new rotation
   mechanism.
4. Bonus: shouldShow() previously only excluded 'live'/'completed', so
   'postgame'/'final' fell through to showing stale pregame content too.
5. Delay handling extended post-kickoff: WEATHER DELAY vs generic GAME
   DELAYED badge text (delay_type already existed as a settings field;
   shouldShow()/delayGameStateCard() already worked post-kickoff before
   this change -- only the badge text was generic).

No node/execjs/playwright harness in this suite -- other gate tests for
this project's JS/HTML files use static source assertions, matched here.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_should_show_excludes_all_post_game_phases() -> None:
    html = read("templates/pregame_universal_overlay.html")
    assert "if(['live','completed','postgame','final'].includes(phase))return false;" in html


def test_halftime_banner_follows_existing_statebadge_pattern() -> None:
    html = read("templates/pregame_universal_overlay.html")
    assert ".statebadge.halftime{" in html
    assert "halftime?'HALFTIME':'PREGAME'" in html
    assert "document.getElementById('stateBadge').classList.toggle('halftime',halftime);" in html


def test_delay_badge_distinguishes_weather_delay_from_generic() -> None:
    html = read("templates/pregame_universal_overlay.html")
    assert "const weatherDelay=delayed&&String(cfg.delay_type||'').toLowerCase()==='weather';" in html
    assert "weatherDelay?'WEATHER DELAY':'GAME DELAYED'" in html


def test_halftime_countdown_area_shows_score_not_a_stale_countdown() -> None:
    html = read("templates/pregame_universal_overlay.html")
    assert "document.getElementById('countdown').textContent=`${Number(g.home_score||0)}-${Number(g.visitor_score||0)}`;" in html
    assert "'Score at the Half'" in html


def test_spotlight_card_reuses_page_native_markup_idiom() -> None:
    html = read("templates/pregame_universal_overlay.html")
    assert "function spotlightCard(entry)" in html
    assert '<section class="card">' in html  # reused, not a new card shell
    assert "class=\"spotlight-portrait\"" in html


def test_rebuild_cards_wires_spotlights_into_existing_rotation() -> None:
    html = read("templates/pregame_universal_overlay.html")
    assert "const halftime=data.settings?.mode!=='delayed'&&phase==='halftime';" in html
    assert "list=[weather,...spotlights.map(spotlightCard)];" in html
