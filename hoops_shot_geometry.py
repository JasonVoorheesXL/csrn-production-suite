"""Where a basketball shot was taken.

A spot is stored in feet on an 84 x 50 court, from the shooter's point of view:
as if the team always attacks the basket at x = 84, with y below 25 on the
shooter's left. That keeps every shot of a game comparable after the teams
switch ends at halftime.
"""

from __future__ import annotations

import math
from typing import Any, Mapping

COURT_LENGTH = 84.0
COURT_WIDTH = 50.0
RIM_X = COURT_LENGTH - 5.25
RIM_Y = COURT_WIDTH / 2
THREE_POINT_RADIUS = 19.75
CORNER_Y = 5.25
LANE_LENGTH = 19.0
LANE_WIDTH = 12.0
RIM_RANGE_FEET = 4.5


def distance_to_rim(x: float, y: float) -> float:
    return math.hypot(RIM_X - x, RIM_Y - y)


def is_three(x: float, y: float) -> bool:
    if y < CORNER_Y or y > COURT_WIDTH - CORNER_Y:
        return True
    return distance_to_rim(x, y) > THREE_POINT_RADIUS


def zone(x: float, y: float) -> str:
    if is_three(x, y):
        if x >= RIM_X - 8:
            return "left_corner_three" if y < RIM_Y else "right_corner_three"
        if abs(y - RIM_Y) < 8:
            return "top_three"
        return "left_wing_three" if y < RIM_Y else "right_wing_three"
    if distance_to_rim(x, y) <= RIM_RANGE_FEET:
        return "rim"
    if x >= COURT_LENGTH - LANE_LENGTH and abs(y - RIM_Y) <= LANE_WIDTH / 2:
        return "paint"
    return "mid_range"


def clean_spot(payload: Mapping[str, Any]) -> dict[str, Any]:
    """The payload with a tidy spot and its zone, or with any bad spot removed.
    A play with no spot is still a good play."""
    result = dict(payload)
    try:
        x = float(payload["spotX"])
        y = float(payload["spotY"])
        if not (math.isfinite(x) and math.isfinite(y)):
            raise ValueError
    except (KeyError, TypeError, ValueError):
        for key in ("spotX", "spotY", "zone"):
            result.pop(key, None)
        return result
    x = round(min(COURT_LENGTH, max(0.0, x)), 1)
    y = round(min(COURT_WIDTH, max(0.0, y)), 1)
    result.update(spotX=x, spotY=y, zone=zone(x, y))
    return result


def shots_with_notes(events: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Every shot still standing, with anything noted on it afterwards merged in:
    what the shot chart and the on-air marker read."""
    notes: dict[str, dict[str, Any]] = {}
    for event in events:
        if event.get("event_type") == "PLAY_NOTE" and not event.get("voided"):
            payload = event.get("payload") or {}
            target = str(payload.get("targetEventId", ""))
            notes.setdefault(target, {}).update({k: v for k, v in payload.items() if k != "targetEventId"})
    shots = []
    for event in events:
        if event.get("event_type") == "SHOT" and not event.get("voided"):
            shots.append({"event_id": event.get("event_id"), **dict(event.get("payload") or {}), **notes.get(str(event.get("event_id")), {})})
    return shots
