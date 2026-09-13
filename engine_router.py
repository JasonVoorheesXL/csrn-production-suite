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

Basketball engine, P0 addendum (2026-09-13, engine_router.py decision):
basketball's own hoops_view()/commit_hoops_view() live in this file
alongside diamond_view()/commit_diamond_view(), rather than a separate
per-sport adapter module and rather than generalizing this whole module
up front -- the basketball scoping doc had assumed a single generic
dispatch table this module never was; this addendum is the resolution,
not a rewrite. Only the truly sport-agnostic sliver (get-or-create a
namespaced sub-state dict) is factored out, as
_ensure_namespaced_state() below; the shared-field lists, owned-key
lists, and commit semantics stay separate per sport because they
genuinely differ -- basketball's own docs/HOOPS_OVERLAY_CONTRACT.md
keeps period/clock/possession/scores SHARED with football (never
namespaced), unlike diamond's home_score/visitor_score, which DO live
inside state["diamond"] and need sync_shared_fields() to project back
out. Forcing both sports through one identical shape would have hidden
that real difference, not simplified anything.

hoops_state_service.py (the actual state machine) is basketball P1, not
this round -- default_hoops_state() below is a placeholder scaffold so
hoops_view()/ensure_hoops_state() have something namespaced to create
today, exactly the role default_diamond_state() played before P0-P3 built
diamond_state_service/lineup_service. P1 should replace its body with a
delegated import, the same way default_diamond_state() delegates instead
of inlining defaults.
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


def _ensure_namespaced_state(
    state: dict[str, Any], key: str, default_factory: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    """Get-or-create state[key], seeding it with default_factory() if
    missing or empty. This is the one piece diamond_view() and hoops_view()
    genuinely share -- which shared fields ride along in the view, which
    keys fold back on commit, and whether a shared field ever gets
    projected back out (sync_shared_fields) differ per sport and stay in
    each pair of functions rather than being forced into one shape here."""
    sub = state.get(key)
    if not isinstance(sub, dict) or not sub:
        sub = default_factory()
        state[key] = sub
    return sub


def ensure_diamond_state(state: dict[str, Any]) -> dict[str, Any]:
    """Returns state["diamond"], creating a fresh one if this game doesn't
    have one yet. No-op (returns {}) for a non-diamond sport -- never
    mutates a football game's state."""
    if not is_diamond_sport(state):
        return {}
    return _ensure_namespaced_state(state, "diamond", default_diamond_state)


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


HOOPS_SPORTS: frozenset[str] = frozenset({"basketball"})

# docs/HOOPS_OVERLAY_CONTRACT.md Sec.1 -- the fields ONLY the basketball
# engine produces. period/clock/possession/home_score/visitor_score are
# explicitly SHARED with football per that same doc ("no new
# basketball-specific score field") and are never namespaced here -- the
# asymmetry with DIAMOND_OWNED_KEYS (which does include home_score/
# visitor_score) is real, not an oversight: baseball/softball's scores
# live inside state["diamond"] and need sync_shared_fields() to project
# back out; basketball's scores were never moved off the top level in the
# first place, so there is nothing to project.
HOOPS_OWNED_KEYS: tuple[str, ...] = (
    "shot_clock", "home_fouls", "visitor_fouls",
    "home_bonus", "visitor_bonus", "home_timeouts", "visitor_timeouts",
)

# Shared/administrative fields a hoops_view() needs from the OUTER state,
# per docs/HOOPS_OVERLAY_CONTRACT.md Sec.1's "shared with football" table.
_HOOPS_SHARED_VIEW_KEYS: tuple[str, ...] = (
    "sport", "country", "region", "association", "status",
    "effective_profile_id", "effective_profile_version",
    "home_team", "visitor_team", "broadcast_id",
    "period", "quarter", "clock", "clock_seconds", "possession",
    "home_score", "visitor_score",
)


def is_hoops_sport(state_or_sport: Any) -> bool:
    sport = state_or_sport if isinstance(state_or_sport, str) else str((state_or_sport or {}).get("sport", "") or "")
    return sport.strip().lower() in HOOPS_SPORTS


def default_hoops_state() -> dict[str, Any]:
    """A fresh state["hoops"] blob. Placeholder scaffold only -- see the
    module docstring's P0 addendum. Blank/zeroed defaults, not
    ruleset-derived ones (e.g. real timeout counts): resolving a ruleset is
    P1's job (hoops_state_service.py), not this router's."""
    return {
        "shot_clock": "",
        "home_fouls": "0",
        "visitor_fouls": "0",
        "home_bonus": "NONE",
        "visitor_bonus": "NONE",
        "home_timeouts": "",
        "visitor_timeouts": "",
    }


def ensure_hoops_state(state: dict[str, Any]) -> dict[str, Any]:
    """Returns state["hoops"], creating a fresh one if this game doesn't
    have one yet. No-op (returns {}) for a non-basketball sport -- never
    mutates a football/baseball/softball game's state."""
    if not is_hoops_sport(state):
        return {}
    return _ensure_namespaced_state(state, "hoops", default_hoops_state)


def hoops_view(state: dict[str, Any]) -> dict[str, Any]:
    """A flat dict combining the shared fields (period/clock/possession/
    scores/...) with state["hoops"]'s own fields -- the basketball
    equivalent of diamond_view(). Creates state["hoops"] first if missing.
    Same shared-vs-nested-object caveat as diamond_view(): the returned
    dict is a fresh top-level dict, but nested values (none yet, since
    every HOOPS_OWNED_KEYS value today is a plain string) would be shared
    with state["hoops"] if any were added."""
    hoops = ensure_hoops_state(state)
    view: dict[str, Any] = {key: state.get(key) for key in _HOOPS_SHARED_VIEW_KEYS}
    view.update(hoops)
    return view


def commit_hoops_view(state: dict[str, Any], view: dict[str, Any]) -> dict[str, Any]:
    """Folds a hoops_view() back into state: hoops-owned keys go back into
    state["hoops"]. Unlike commit_diamond_view(), there is no shared
    "status" write-back and no sync_shared_fields() call here -- no P0-era
    basketball service writes status through this view, and basketball's
    scores were never namespaced to begin with (see HOOPS_OWNED_KEYS's own
    comment). Add a status write-back here if/when basketball P1 actually
    needs one; this scaffold does not guess at that shape now."""
    state.setdefault("hoops", {})
    for key in HOOPS_OWNED_KEYS:
        if key in view:
            state["hoops"][key] = view[key]
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
