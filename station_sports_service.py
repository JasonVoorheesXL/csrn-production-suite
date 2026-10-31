"""Station sports (audit round 3, 2026-10-31): which of its licensed sports a
station actually uses.

A switched-off sport leaves the login tiles and the header sport picker and
cannot be entered; the license itself is untouched, so switching it back on in
Settings is all it takes. Only sports with a broadcast engine can be switched;
the rest keep their license / "soon" behaviour.
"""
from __future__ import annotations

from typing import Any, Iterable, Mapping

import sport_families

SWITCHABLE: tuple[str, ...] = tuple(
    family for family in sport_families.SPORT_FAMILIES if family in sport_families.ENGINE_READY
)
DEFAULT_ON: tuple[str, ...] = ("football",)


def normalize_station_sports(raw: object) -> dict[str, Any]:
    """`{"on": [...]}` in display order; football alone when unset or empty."""
    value = raw.get("on") if isinstance(raw, Mapping) else None
    if isinstance(value, (list, tuple)):
        chosen = {str(item).strip().lower() for item in value}
        on = [family for family in SWITCHABLE if family in chosen]
        if on:
            return {"on": on}
    return {"on": list(DEFAULT_ON)}


def validate_station_sports(raw: object) -> str | None:
    """An operator-facing problem with a save request, or None."""
    if not isinstance(raw, Mapping) or not isinstance(raw.get("on"), list):
        return "Send the sports to switch on as a list."
    unknown = [str(item) for item in raw["on"] if str(item).strip().lower() not in SWITCHABLE]
    if unknown:
        return f"Unknown sport: {', '.join(unknown)}."
    if not raw["on"]:
        return "Keep at least one sport switched on."
    return None


def families_in_use(licensed: Iterable[str], station: object) -> list[str]:
    """The licensed families minus the ones this station switched off."""
    on = set(normalize_station_sports(station)["on"])
    return [family for family in licensed if family not in SWITCHABLE or family in on]


def switched_off(licensed: Iterable[str], station: object) -> list[str]:
    on = set(normalize_station_sports(station)["on"])
    return [family for family in licensed if family in SWITCHABLE and family not in on]
