"""Regression coverage for the pregame overlay bug report: info-panel
layout overflow + missing sponsor rotation during pregame.

templates/pregame_universal_overlay.html renders pregame, halftime, and
delay states from one shared template (driven by pregame_presentation.py).

1/4. CRITICAL (same root cause) -- .content had no min-height:0 (so a tall
     card could force the grid row taller than the viewport, pushing a
     stray scrollbar behind the opaque .topbar) and centered its card
     instead of anchoring it to the top, with no internal scroll -- so a
     card taller than the panel had its top edge pushed out of view
     ("a gap at the top... information goes outside the box").
2. Style parity -- pregame-only cards (game info, team profiles,
   storylines, next matchup) used a smaller default type scale than
   halftime's spotlight/sponsor cards, so the panel read inconsistently
   depending on state.
3. Missing feature -- the active sponsor roster was computed unconditionally
   in rebuildCards() but only spliced into the halftime branch's card list,
   never the pregame branch's, so sponsors never rotated in pregame despite
   the same data being available.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def _content_rule() -> str:
    html = _read("templates/pregame_universal_overlay.html")
    start = html.index(".content{")
    return html[start: html.index("}", start) + 1]


def test_content_panel_is_top_anchored_with_internal_scroll_and_no_grid_overflow() -> None:
    rule = _content_rule()
    assert "min-height:0" in rule
    assert "align-items:flex-start" in rule
    assert "overflow-y:auto" in rule
    # the old centering behaviour that pushed tall cards out of view is gone
    assert "align-items:center" not in rule


def test_pregame_cards_share_halftimes_large_type_scale() -> None:
    html = _read("templates/pregame_universal_overlay.html")
    kicker_rule = html[html.index(".card-kicker{"): html.index("}", html.index(".card-kicker{")) + 1]
    assert "font-size:24px" in kicker_rule
    h1_start = html.index(".card h1{")
    h1_rule = html[h1_start: html.index("}", h1_start) + 1]
    assert "font-size:72px" in h1_rule
    assert "margin:12px 0 28px" in h1_rule
    # the now-redundant per-state duplicate of the same rule is gone
    assert ".card-spotlight .card-kicker,.card-sponsor .card-kicker" not in html
    assert ".card-spotlight h1,.card-sponsor h1" not in html
    # the spotlight/sponsor image + meta row scale-up (which the other
    # pregame cards don't have the markup for) is untouched
    assert ".card-spotlight .spotlight-portrait{width:280px;height:280px}" in html
    assert ".card-sponsor .spotlight-portrait{width:340px;height:210px" in html


def test_pregame_branch_of_rebuild_cards_includes_sponsor_rotation() -> None:
    html = _read("templates/pregame_universal_overlay.html")
    fn = html[html.index("function rebuildCards()"):]
    fn = fn[: fn.index("\nfunction showCard", 1)]
    # sponsors is computed unconditionally...
    assert "const sponsors=Array.isArray(data.halftime_sponsors)" in fn
    # ...and now spliced into BOTH the halftime branch and the pregame
    # (else) branch, not halftime only.
    else_branch = fn[fn.index("}else{"):]
    assert "...sponsors" in else_branch
    halftime_branch = fn[fn.index("}else if(halftime){"): fn.index("}else{")]
    assert "...sponsors" in halftime_branch


def test_halftime_and_delay_branches_are_unchanged() -> None:
    html = _read("templates/pregame_universal_overlay.html")
    fn = html[html.index("function rebuildCards()"):]
    fn = fn[: fn.index("\nfunction showCard", 1)]
    assert "list=[weather,delayState,gameDetailsCard(),teamProfilesCard(),storylinesCard(),nextWeekCard()];" in fn
    assert "list=[delayState,gameDetailsCard(),weather,teamProfilesCard(),storylinesCard(),nextWeekCard()];" in fn
    assert "list=[weather,...spotlights.map(spotlightCard),...sponsors];" in fn
