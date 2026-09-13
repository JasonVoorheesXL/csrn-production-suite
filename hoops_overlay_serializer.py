"""Overlay-state serializer -- the basketball engine's OUTPUT side of
docs/HOOPS_OVERLAY_CONTRACT.md, the field-level contract the already-
shipped rendering layer (productionBasketballState() in
csrn-production-theme-runtime.js) committed to consuming.

Sec.1's own "Shared with football" table means this module is narrower
than baseball's overlay_serializer.py: period / clock / possession /
home_score / visitor_score are already flat, shared fields on the outer
state dict (engine_router.py's hoops_view() keeps them there, never
namespaces them under state["hoops"] -- see that module's own docstring
on why basketball's split from diamond's fully-namespaced precedent is
deliberate) -- productionBasketballState() and mergeRuntimeState()'s
basketball branch already read them correctly off the flat runtime state
with ZERO engine action needed (confirmed in docs/HOOPS_OVERLAY_CONTRACT.md
Sec.3/Sec.4, and re-confirmed here since this module is exactly where
that claim would break if it were wrong). This module's only job is the
fields basketball ALONE produces: shot_clock, home/visitor_fouls,
home/visitor_bonus, home/visitor_timeouts -- projected from
state["hoops"]'s raw values onto the wire's ALREADY-FORMATTED-STRING
shape (Sec.1: "string (already formatted, e.g. \"3\")").

Wiring this into the live /api/runtime-state payload is P4 (routes),
same split baseball used (overlay_serializer.py was P3, diamond_game_
routes.py + app.py wiring was P4) -- this module and its
engine_router.hoops_overlay_payload() dispatch are pure and directly
testable without any route/Flask involvement.
"""

from __future__ import annotations

from typing import Any, Mapping

BONUS_STATES: tuple[str, str, str] = ("NONE", "ONE_AND_ONE", "DOUBLE")


class HoopsOverlaySerializer:
    @classmethod
    def serialize(cls, state: Mapping[str, Any]) -> dict[str, Any]:
        hoops = state.get("hoops") or {}

        shot_clock_seconds = hoops.get("shot_clock_seconds")
        # Sec.1: "Blank/absent when the active profile's shot_clock.enabled
        # is false -- the renderer does not itself know the profile, it
        # just shows whatever string it's given. Do not publish a stale/
        # zero value when the profile has the shot clock off."
        shot_clock_text = "" if shot_clock_seconds is None else str(int(shot_clock_seconds))

        home_bonus = str(hoops.get("home_bonus", "NONE"))
        visitor_bonus = str(hoops.get("visitor_bonus", "NONE"))
        if home_bonus not in BONUS_STATES or visitor_bonus not in BONUS_STATES:
            # Sec.1: "Fixed 3-value enum, pinned here... this engine's
            # serializer is the FIRST and ONLY producer of this value."
            # A value outside the pinned enum is a real bug upstream
            # (hoops_state_service.set_bonus() already rejects anything
            # else), not something to silently coerce or pass through.
            raise ValueError(
                f"bonus state outside the pinned enum {BONUS_STATES}: "
                f"home={home_bonus!r} visitor={visitor_bonus!r}"
            )

        return {
            "shot_clock": shot_clock_text,
            "home_fouls": str(int(hoops.get("home_team_fouls", 0))),
            "visitor_fouls": str(int(hoops.get("visitor_team_fouls", 0))),
            "home_bonus": home_bonus,
            "visitor_bonus": visitor_bonus,
            "home_timeouts": str(int(hoops.get("home_timeouts", 0))),
            "visitor_timeouts": str(int(hoops.get("visitor_timeouts", 0))),
        }
