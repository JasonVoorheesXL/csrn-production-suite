"""Canonical CSRN sport-family vocabulary (Round 27 access model).

The login-screen sport picker, the license ``sports`` list, and the
operator's switchable sport *context* all operate at the FAMILY level --
"football", "basketball", "baseball", and so on. Sub-variants (American vs
Canadian football) are NOT families: they live inside a family and are
resolved by the jurisdiction / ruleset picker built in Round 26
(country / region / association -> ruleset).

This module is a leaf -- it imports nothing from the app -- so the
entitlement boundary, the routes, and the tests can all share one list.
"""

from __future__ import annotations

from typing import Iterable

# Display order on the login screen and the top-nav switcher. ``all_others``
# is a deliberate catch-all bucket: sports CSRN has no dedicated engine /
# vocabulary for yet (lacrosse, hockey, pickleball, ...). It is a real
# family for licensing and context-scoping purposes; it is not a specific
# sport. (American vs Canadian football is NOT handled here -- it stays
# inside the "football" family, resolved by the Round 26 jurisdiction
# picker.)
SPORT_FAMILIES: tuple[str, ...] = (
    "football",
    "basketball",
    "baseball",
    "softball",
    "soccer",
    "all_others",
)

# Wildcard token a license may carry in its ``sports`` list to mean
# "every family" (the development license uses this).
ALL = "*"

# Short codes seen elsewhere in the codebase (DragonFly SPORT_CODES,
# broadcast id prefixes) and a few spellings mapped back onto a canonical
# family, so a license or a stored record written with a code still
# resolves.
_ALIASES: dict[str, str] = {
    "fb": "football",
    "bb": "basketball",
    "ba": "baseball",
    "bsb": "baseball",
    "sb": "softball",
    "sc": "soccer",
    "soc": "soccer",
    "other": "all_others",
    "others": "all_others",
    "all-others": "all_others",
    "all others": "all_others",
    "allothers": "all_others",
}


def normalize_family(value: object) -> str:
    """Return the canonical family for a raw sport string, or "" if unknown.

    Case-insensitive; accepts a canonical family name or a known short code.
    """

    text = str(value or "").strip().casefold()
    if not text:
        return ""
    if text in SPORT_FAMILIES:
        return text
    return _ALIASES.get(text, "")


def is_known_family(value: object) -> bool:
    """True when ``value`` resolves to a canonical family."""

    return normalize_family(value) != ""


def resolve_licensed_families(sports: Iterable[object]) -> list[str]:
    """Canonical families a license's ``sports`` list grants, in display order.

    * ``"*"`` anywhere in the list grants every family.
    * An empty list (or one with no recognised entries) grants nothing --
      matching ``EntitlementService.allows()``, where an empty ``sports``
      list allows no sport-scoped feature.
    """

    tokens = [str(item).strip() for item in (sports or [])]
    if any(token == ALL for token in tokens):
        return list(SPORT_FAMILIES)
    granted = {normalize_family(token) for token in tokens}
    granted.discard("")
    return [family for family in SPORT_FAMILIES if family in granted]
