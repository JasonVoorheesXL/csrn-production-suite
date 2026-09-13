"""Sport dispatch between football's flat game state and baseball/softball's
namespaced diamond sub-state (baseball engine scoping plan, P4).

Football's state dict (app.py's DEFAULT_STATE) is a single flat ~100-key
dict, and nothing about this module changes that -- every function here is
a no-op for state["sport"] not in DIAMOND_SPORTS, so football gains zero
new keys and zero new behavior.

Baseball/softball state instead gets ONE new top-level key, state["diamond"],
holding everything diamond_state_service.default_state() and lineup_service.
default_state() already produce (inning, outs, base_runners, lineup, the
diamond_events/lineup_events ledgers, ...). This is a deliberate namespacing
choice (round decision, P4): it keeps baseball/softball's ~25 fields
completely isolated from football's DEFAULT_STATE shape, at the cost of one
wrinkle -- diamond_state_service, lineup_service, at_bat_rules_service,
game_end_evaluator, rules_validator, diamond_event_service,
game_suspension_service, box_score_service and overlay_serializer were all
built and tested (P0-P3) against a single FLAT dict that also carries the
game's shared/administrative fields (sport, country, region, association,
status -- overlay_serializer.regulation_innings() needs country/region/
association to resolve the ruleset; at_bat_rules_service.confirm_game_end()
and game_suspension_service both read/write the shared "status" field
directly, exactly like football's own GameOperationsService.end_game()
does).

diamond_view()/commit_diamond_view() are the adapter that reconciles that:
build a temporary flat dict (shared fields + state["diamond"]'s own fields)
to hand to any P0-P3 service call, then fold the result back -- the
diamond-owned fields into state["diamond"], the shared "status" field back
onto the outer state (never nested) -- so storage stays cleanly namespaced
while every already-tested P0-P3 service keeps working completely
unmodified.

sync_shared_fields() is the other half: the already-shipped T1/Phase C
renderer and every other shared consumer (recap_service, broadcast list
cards, sponsor rotation, ...) reads home_score/visitor_score flat off the
top-level state, exactly like football. After every diamond mutation this
projects those (and nothing else) from state["diamond"] onto the top level,
so none of that shared code needs to learn a second place to look.
"""

from __future__ import annotations

import copy
from typing import Any, Callable

DIAMOND_SPORTS: frozenset[str] = frozenset({"baseball", "softball"})

# diamond_state_service.CANONICAL_FIELDS + its ledger fields, kept as a
# literal tuple here (rather than importing the private _LEDGER_FIELDS) so
# this module's contract with diamond_state_service is explicit and doesn't
# silently widen if that module's private tuple ever changes shape.
_DIAMOND_STATE_KEYS: tuple[str, ...] = (
    "inning", "inning_half", "outs", "balls", "strikes", "base_runners",
    "current_batter_id", "current_pitcher_id", "current_catcher_id",
    "plate_appearance_id", "at_bat_sequence", "home_score", "visitor_score",
    "line_score", "home_hits", "visitor_hits", "home_errors", "visitor_errors",
    "left_on_base", "ball_status", "pending_ruling", "game_end_candidate",
    "official_game_end_reason",
    "diamond_events", "last_applied_sequence", "last_snapshot_event_id",
)

# lineup_service.default_state()'s own top-level keys.
_LINEUP_STATE_KEYS: tuple[str, ...] = ("lineup", "lineup_events")

# game_suspension_service stores its snapshot directly under this key on
# whatever dict it's given -- same flat-merge assumption as everything else.
_SUSPENSION_STATE_KEYS: tuple[str, ...] = ("suspension",)

DIAMOND_OWNED_KEYS: tuple[str, ...] = (
    _DIAMOND_STATE_KEYS + _LINEUP_STATE_KEYS + _SUSPENSION_STATE_KEYS
)

# Shared/administrative fields a diamond_view() needs from the OUTER state
# to behave correctly (ruleset resolution, status propagation) -- never
# duplicated into state["diamond"] itself.
_SHARED_VIEW_KEYS: tuple[str, ...] = (
    "sport", "country", "region", "association", "status",
    "effective_profile_id", "effective_profile_version",
    "home_team", "visitor_team", "broadcast_id",
)


def is_diamond_sport(state_or_sport: Any) -> bool:
    sport = state_or_sport if isinstance(state_or_sport, str) else str((state_or_sport or {}).get("sport", "") or "")
    return sport.strip().lower() in DIAMOND_SPORTS


def default_diamond_state() -> dict[str, Any]:
    """A fresh state["diamond"] blob: diamond_state_service + lineup_service
    defaults, merged (they own disjoint keys -- see the module docstring)."""
    from diamond_state_service import default_state as _diamond_default
    from lineup_service import default_state as _lineup_default

    merged = _diamond_default()
    merged.update(_lineup_default())
    return merged


def ensure_diamond_state(state: dict[str, Any]) -> dict[str, Any]:
    """Returns state["diamond"], creating a fresh one if this game doesn't
    have one yet. No-op (returns {}) for a non-diamond sport -- never
    mutates a football game's state."""
    if not is_diamond_sport(state):
        return {}
    diamond = state.get("diamond")
    if not isinstance(diamond, dict) or not diamond:
        diamond = default_diamond_state()
        state["diamond"] = diamond
    return diamond


def diamond_view(state: dict[str, Any]) -> dict[str, Any]:
    """A flat dict combining the shared fields P0-P3 services need
    (sport/country/region/association/status/...) with state["diamond"]'s
    own fields -- the shape every diamond_state_service/lineup_service/
    at_bat_rules_service/... call already expects. Creates state["diamond"]
    first if it's missing. The returned dict is a fresh top-level dict
    (safe to mutate top-level keys on) but its nested values (base_runners,
    lineup, diamond_events, ...) are the SAME objects stored in
    state["diamond"] -- see commit_diamond_view() for why that's fine.
    """
    diamond = ensure_diamond_state(state)
    view: dict[str, Any] = {key: state.get(key) for key in _SHARED_VIEW_KEYS}
    view.update(diamond)
    return view


def commit_diamond_view(state: dict[str, Any], view: dict[str, Any]) -> dict[str, Any]:
    """Folds a diamond_view() back into state after a P0-P3 service call:
    diamond-owned keys go back into state["diamond"]; the shared "status"
    field (the only shared key a diamond service is allowed to write --
    at_bat_rules_service.confirm_game_end(), game_suspension_service.
    suspend()/resume()) is propagated onto the OUTER state, never nested.
    Then projects the shared display fields (sync_shared_fields) so the
    existing renderer/reporting layers see the update. Returns state."""
    state.setdefault("diamond", {})
    for key in DIAMOND_OWNED_KEYS:
        if key in view:
            state["diamond"][key] = view[key]
    if "status" in view and view["status"] is not None:
        state["status"] = view["status"]
    return sync_shared_fields(state)


def sync_shared_fields(state: dict[str, Any]) -> dict[str, Any]:
    """Projects the fields the rest of the app already reads flat
    (home_score/visitor_score) from state["diamond"] onto the top level.
    No-op for football (whose home_score/visitor_score ARE the top-level
    fields already -- there is nothing to project)."""
    if not is_diamond_sport(state):
        return state
    diamond = state.get("diamond")
    if not isinstance(diamond, dict) or not diamond:
        return state
    state["home_score"] = diamond.get("home_score", 0)
    state["visitor_score"] = diamond.get("visitor_score", 0)
    return state


def overlay_payload(state: dict[str, Any], *, pitcher_name: str = "", batter_name: str = "", batter_position: str = "") -> dict[str, Any]:
    """The DIAMOND_OVERLAY_CONTRACT.md wire payload for this game. Callers
    (routes) are responsible for resolving pitcher_name/batter_name/
    batter_position against a roster -- this module only knows player ids."""
    from overlay_serializer import OverlaySerializer

    return OverlaySerializer.serialize(
        diamond_view(state),
        pitcher_name=pitcher_name,
        batter_name=batter_name,
        batter_position=batter_position,
    )


def box_score_report(state: dict[str, Any]) -> dict[str, Any]:
    """Dispatch for the statistics/box-score reporting path: baseball and
    softball route to box_score_service; this function is simply not
    meaningful for football (callers already have their own
    StatisticsService for that sport and should not call this)."""
    from box_score_service import BoxScoreService

    return BoxScoreService.report(diamond_view(state))


def run_diamond_mutation(
    state: dict[str, Any],
    mutate: Callable[[dict[str, Any]], Any],
) -> Any:
    """Runs `mutate` against a diamond_view() of `state`, commits the
    resulting view back (diamond_view()'s nested containers -- base_runners,
    lineup, diamond_events, ... -- are shared objects, so in-place mutators
    like DiamondStateFoundation's already take effect on state["diamond"]
    directly; this call additionally re-syncs top-level keys such as
    home_score/status that get reassigned rather than mutated in place),
    and returns whatever `mutate` returned.

    `mutate` receives the flat view and is expected to return the P0-P3
    service Result object (AtBatResult / LineupResult / SuspensionResult /
    ...) it produced by calling into diamond_state_service/lineup_service/
    at_bat_rules_service/diamond_event_service/game_suspension_service with
    that view as their `state` argument.
    """
    view = diamond_view(state)
    result = mutate(view)
    result_state = getattr(result, "state", None)
    commit_diamond_view(state, result_state if isinstance(result_state, dict) else view)
    return result
