"""Canonical CSRN sport vocabulary (Round 27 access model).

The login-screen sport picker, the operator's switchable sport *context*,
and the license ``sports`` list operate on a small set of values:

* **SPORT_FAMILIES** -- the real, licensable families that each get their
  own login icon: football, basketball, baseball, softball, soccer.
* **GATEWAY** (``"all_others"``) -- a sixth login tile that is NOT a
  context. Clicking it opens a secondary list of OTHER_CONTEXTS; the
  operator then picks one of those. ``"all_others"`` is never stored as a
  ``sport_context``.
* **OTHER_CONTEXTS** -- sports without their own icon, reached through the
  gateway. ``canadian_football`` has a real engine (it loads the same
  Round 26 football module, just entered pre-scoped toward Canadian
  rulesets); the rest are "coming soon" with nothing to load yet.

Two invariants from the design:

1. **Licensing is merged.** ``canadian_football`` is entitled by the same
   ``football`` license entry -- never a separate purchase. Every licence
   check goes through :func:`base_family`, which collapses
   ``canadian_football`` -> ``football``.
2. **Roster / sponsor scoping is shared.** A roster or sponsor is tagged
   ``football`` regardless of American vs Canadian (the ruleset is a
   per-broadcast choice, Round 26). So scoping keys off :func:`base_family`
   too -- ``sport_context = "canadian_football"`` surfaces the football
   pool, not an empty one.

This module is a leaf: it imports nothing from the app.
"""

from __future__ import annotations

from typing import Iterable, Mapping

# Real licensable families -- one login icon each, display order.
SPORT_FAMILIES: tuple[str, ...] = (
    "football",
    "basketball",
    "baseball",
    "softball",
    "soccer",
)

# The sixth login tile. A gateway to OTHER_CONTEXTS, never a stored context.
GATEWAY: str = "all_others"

# Full login-tile display order.
LOGIN_TILES: tuple[str, ...] = SPORT_FAMILIES + (GATEWAY,)

# Behind the gateway. Order = display order in the secondary list.
OTHER_CONTEXTS: tuple[str, ...] = (
    "canadian_football",
    "hockey",
    "lacrosse",
    "tennis",
    "swimming",
)

# Contexts a module actually loads for. Everything else in OTHER_CONTEXTS is
# inert / "coming soon".
ENGINE_READY: frozenset[str] = frozenset({*SPORT_FAMILIES, "canadian_football"})

# Wildcard token a license may carry in its ``sports`` list ("every family").
ALL: str = "*"

LABELS: dict[str, str] = {
    "football": "Football",
    "basketball": "Basketball",
    "baseball": "Baseball",
    "softball": "Softball",
    "soccer": "Soccer",
    "all_others": "All Others",
    "canadian_football": "Canadian Football",
    "hockey": "Hockey",
    "lacrosse": "Lacrosse",
    "tennis": "Tennis",
    "swimming": "Swimming",
}

# sport_context -> the family whose roster/sponsor pool AND license entry it
# draws from. The only collapse today is Canadian football onto football.
_BASE: dict[str, str] = {"canadian_football": "football"}

# Short codes / spellings seen elsewhere (DragonFly SPORT_CODES, broadcast
# id prefixes, operator input) mapped onto a canonical value.
_ALIASES: dict[str, str] = {
    "fb": "football",
    "bb": "basketball",
    "ba": "baseball",
    "bsb": "baseball",
    "sb": "softball",
    "sc": "soccer",
    "soc": "soccer",
    "cfl": "canadian_football",
    "canadian": "canadian_football",
    "ca_football": "canadian_football",
    "canada_football": "canadian_football",
    "other": "all_others",
    "others": "all_others",
}


def normalize_sport(value: object) -> str:
    """Canonical value for a raw sport string, or "" if unrecognised.

    Accepts a family, the gateway token, an other-context, or a known
    short code / spelling. Case-, space-, dash- and dot-insensitive.
    """

    text = str(value or "").strip().casefold()
    for character in ("-", " ", "."):
        text = text.replace(character, "_")
    while "__" in text:
        text = text.replace("__", "_")
    text = text.strip("_")
    if not text:
        return ""
    if text in SPORT_FAMILIES or text == GATEWAY or text in OTHER_CONTEXTS:
        return text
    return _ALIASES.get(text, "")


# Back-compat name used by earlier Round 27 commits / tests.
normalize_family = normalize_sport


def base_family(value: object) -> str:
    """The family a context draws its pool + license from (Round 27 inv. 1 & 2).

    ``canadian_football`` -> ``football``; everything else is itself.
    """

    context = normalize_sport(value)
    return _BASE.get(context, context)


def is_engine_ready(value: object) -> bool:
    """True when a module actually loads for this context."""

    return normalize_sport(value) in ENGINE_READY


def resolve_licensed_families(sports: Iterable[object]) -> list[str]:
    """Canonical FAMILIES a license's ``sports`` list grants, in display order.

    ``"*"`` grants every family. Each token is run through
    :func:`base_family`, so a license listing ``canadian_football`` (it
    should list ``football`` instead, but be forgiving) still grants
    football. An empty / unrecognised list grants nothing, matching
    ``EntitlementService.allows()``.
    """

    tokens = [str(item).strip() for item in (sports or [])]
    if any(token == ALL for token in tokens):
        return list(SPORT_FAMILIES)
    granted = {base_family(token) for token in tokens}
    granted &= set(SPORT_FAMILIES)
    return [family for family in SPORT_FAMILIES if family in granted]


def context_is_licensed(
    context: object, licensed_families: Iterable[str]
) -> bool:
    """Whether the operator may enter ``context`` given the licensed families.

    The gateway token and unrecognised values are never enterable. Uses
    :func:`base_family` so ``canadian_football`` is covered by a ``football``
    license (Round 27 invariant 1).
    """

    resolved = normalize_sport(context)
    if not resolved or resolved == GATEWAY:
        return False
    return base_family(resolved) in set(licensed_families)


def other_sport_options(
    licensed_families: Iterable[str],
) -> list[dict[str, object]]:
    """The secondary-list metadata for the All Others gateway.

    ``available`` means a module loads for it AND its base family is
    licensed -- i.e. the operator can actually pick it.
    """

    licensed = set(licensed_families)
    return [
        {
            "context": context,
            "label": LABELS.get(context, context),
            "available": context in ENGINE_READY
            and base_family(context) in licensed,
        }
        for context in OTHER_CONTEXTS
    ]


def sport_context_view(
    sport_context: object, licensed_families: Iterable[str]
) -> Mapping[str, object]:
    """The block both /api/security-status and /api/session-context embed."""

    licensed = list(licensed_families)
    resolved = normalize_sport(sport_context)
    # A stored context that is somehow the gateway or unknown reads as none.
    if resolved == GATEWAY:
        resolved = ""
    return {
        "sport_context": resolved,
        "sport_scope": base_family(resolved) if resolved else "",
        "licensed_sports": licensed,
        "all_sports_licensed": licensed == list(SPORT_FAMILIES),
        "other_sports": other_sport_options(licensed),
    }
