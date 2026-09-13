"""Diamond (baseball/softball) equivalent of GameOperationsService's
lifecycle/persistence boundary -- the "game_operations_service baseball
extensions" the P2 phase-table row deferred to P4 (BASEBALL_SOFTBALL_
ENGINE_SCOPING_PLAN.md's P2 scoping note: GameOperationsService.
DEFAULT_STATE had no baseball/lineup fields to extend until this round's
own app.py wiring puts them there).

Deliberately a SEPARATE module rather than an edit to
game_operations_service.py. GameOperationsService is football's shared,
already-frozen persistence/locking boundary; this class reuses the exact
same load_state/save_state/transaction_lock plumbing and the same
live_command_service idempotency/metadata helpers, but never imports or
edits that file -- football's byte-identical contract stays untouched by
construction, not by care alone.

dispatch() is intentionally one generic method rather than ~20 hand-written
wrapper methods (one per lineup_service/diamond_event_service/
game_suspension_service/at_bat_rules_service classmethod). Every one of
those classmethods already follows the same shape -- `state` first,
everything else a plain keyword-bindable argument, a Result object (or,
for a couple of lineup_service mutators, `None`) with the mutated state
attached -- so dispatch() resolves the action name against ACTIONS,
binds the payload's own keys onto that function's parameter names, and
always funnels the call through engine_router.diamond_view()/
commit_diamond_view() so namespacing, persistence and shared-field sync
(home_score/visitor_score/status) happen in exactly one place no matter
which of the ~28 actions ran. Adding a new P1-P3 mutator later is a
one-line ACTIONS entry, not a new wrapper method.
"""

from __future__ import annotations

import copy
import inspect
from dataclasses import dataclass
from typing import Any, Callable, Mapping

import engine_router
from at_bat_rules_service import AtBatRulesService
from diamond_event_service import DiamondEventService
from game_suspension_service import GameSuspensionService
from lineup_service import LineupService
from live_command_service import (
    assign_next_revision,
    attach_metadata,
    command_id_from,
    command_metadata,
    duplicate_result,
    remember_command,
)


@dataclass(frozen=True)
class DiamondGameOperationsResult:
    code: str
    data: dict[str, Any]

    @property
    def ok(self) -> bool:
        return self.code == "OK"


# Action name -> bound classmethod. Every entry's own signature is
# `(state, ...)` (the implicit `cls` aside) -- the same convention every
# P1/P2 diamond/lineup service already follows, so a single generic
# dispatch() can drive all of them identically.
ACTIONS: dict[str, Callable[..., Any]] = {
    # at_bat_rules_service (P1)
    "record_plate_appearance": AtBatRulesService.record_plate_appearance,
    "record_ruling": AtBatRulesService.record_ruling,
    "confirm_game_end": AtBatRulesService.confirm_game_end,
    # diamond_event_service (P2 -- undo/redo/correction boundary)
    "undo": DiamondEventService.undo,
    "redo": DiamondEventService.redo,
    "void_event": DiamondEventService.void_event,
    "correct_event": DiamondEventService.correct_event,
    # game_suspension_service (P2)
    "suspend": GameSuspensionService.suspend,
    "resume": GameSuspensionService.resume,
    # lineup_service (P2 -- baseball + softball sub-engines)
    "start_lineup": LineupService.start_lineup,
    "substitute": LineupService.substitute,
    "reenter": LineupService.reenter,
    "position_change": LineupService.position_change,
    "replace_on_defense_only": LineupService.replace_on_defense_only,
    "terminate_player_dh_role": LineupService.terminate_player_dh_role,
    "assign_role": LineupService.assign_role,
    "record_defensive_meeting": LineupService.record_defensive_meeting,
    "record_charged_conference": LineupService.record_charged_conference,
    "reset_half_inning_meetings": LineupService.reset_half_inning_meetings,
    "start_dp_flex": LineupService.start_dp_flex,
    "dp_plays_defense_for_flex": LineupService.dp_plays_defense_for_flex,
    "flex_bats_for_dp": LineupService.flex_bats_for_dp,
    "dp_reenters": LineupService.dp_reenters,
    "substitute_for_dp": LineupService.substitute_for_dp,
    "substitute_for_flex": LineupService.substitute_for_flex,
    "enter_courtesy_runner": LineupService.enter_courtesy_runner,
    "return_courtesy_runner": LineupService.return_courtesy_runner,
    "record_batter": LineupService.record_batter,
    "apply_appeal_ruling": LineupService.apply_appeal_ruling,
    "dismiss_alert_no_appeal": LineupService.dismiss_alert_no_appeal,
}

# live_command_service's control-metadata keys (client_id, command_id, ...)
# ride along in every route payload but are never valid arguments to any
# ACTIONS entry -- excluded on top of the normal signature-membership
# filter purely for clarity/documentation; _bind_kwargs's signature check
# would already drop them.
_CONTROL_KEYS: frozenset[str] = frozenset({"command_id", "client_id", "source"})


def _bind_kwargs(func: Callable[..., Any], payload: Mapping[str, Any]) -> dict[str, Any]:
    """Binds `payload`'s own keys onto `func`'s parameter names. A couple
    of P1 actions (record_plate_appearance, record_ruling) take their
    entire argument as one `payload: Mapping` parameter (spec Sec.7.2's
    PA-outcome contract) rather than individual named arguments -- for
    those, the whole incoming dict (minus control keys, unless the caller
    already nested it under an explicit "payload" key) is passed through
    as that single argument instead of being matched key-by-key."""
    sig = inspect.signature(func)
    params = sig.parameters
    if "payload" in params:
        nested = payload.get("payload")
        if isinstance(nested, Mapping):
            return {"payload": dict(nested)}
        return {"payload": {k: v for k, v in payload.items() if k not in _CONTROL_KEYS}}
    return {
        key: value
        for key, value in payload.items()
        if key in params and key != "state" and key not in _CONTROL_KEYS
    }


class DiamondGameOperationsService:
    """Live diamond-game-operation boundary, independent of Flask --
    mirrors GameOperationsService's own constructor shape."""

    def __init__(
        self,
        *,
        load_state: Callable[[], Mapping[str, Any]],
        save_state: Callable[[Mapping[str, Any]], Any],
        transaction_lock: Any,
    ) -> None:
        self._load_state = load_state
        self._save_state = save_state
        self._transaction_lock = transaction_lock

    def initialize_diamond(
        self, payload: Mapping[str, Any] | None = None
    ) -> DiamondGameOperationsResult:
        """(Re)creates a fresh state["diamond"] for the current broadcast
        -- called once when an operator starts a new baseball/softball
        broadcast, so the overlay shows inning 1 / 0-0 immediately rather
        than waiting on lazy creation at the first lineup/plate-appearance
        call (engine_router.ensure_diamond_state() still does that lazily
        for any route that forgets to call this first, but every diamond
        route in practice should)."""
        incoming = dict(payload or {})
        with self._transaction_lock:
            state = copy.deepcopy(dict(self._load_state()))
            if not engine_router.is_diamond_sport(state):
                return DiamondGameOperationsResult(
                    "NOT_A_DIAMOND_SPORT", {"state": copy.deepcopy(state)}
                )
            command_id = command_id_from(incoming)
            duplicate = duplicate_result(state, command_id)
            if duplicate is not None:
                return DiamondGameOperationsResult("OK", duplicate)

            state["diamond"] = engine_router.default_diamond_state()
            engine_router.sync_shared_fields(state)
            revision = assign_next_revision(state)
            metadata = command_metadata(
                incoming, action="initialize_diamond", state_revision=revision
            )
            result_data = attach_metadata({"state": copy.deepcopy(state)}, metadata)
            remember_command(state, command_id, metadata=metadata, result=result_data)
            self._save_state(state)
            return DiamondGameOperationsResult("OK", result_data)

    def dispatch(
        self, action: str, payload: Mapping[str, Any] | None = None
    ) -> DiamondGameOperationsResult:
        """Runs one of ACTIONS against the current broadcast's diamond
        sub-state. `payload` supplies that action's own keyword arguments
        by name (e.g. {"side": "home", "slot": 3, "incoming_player_id":
        "p9"} for "substitute")."""
        func = ACTIONS.get(action)
        if func is None:
            return DiamondGameOperationsResult("UNKNOWN_ACTION", {"action": action})
        incoming = dict(payload or {})

        with self._transaction_lock:
            state = copy.deepcopy(dict(self._load_state()))
            if not engine_router.is_diamond_sport(state):
                return DiamondGameOperationsResult(
                    "NOT_A_DIAMOND_SPORT", {"state": copy.deepcopy(state)}
                )
            command_id = command_id_from(incoming)
            duplicate = duplicate_result(state, command_id)
            if duplicate is not None:
                return DiamondGameOperationsResult("OK", duplicate)

            view = engine_router.diamond_view(state)
            kwargs = _bind_kwargs(func, incoming)
            try:
                outcome = func(view, **kwargs)
            except (ValueError, KeyError, TypeError) as exc:
                return DiamondGameOperationsResult("INVALID_REQUEST", {"message": str(exc)})

            outcome_state = getattr(outcome, "state", None)
            engine_router.commit_diamond_view(
                state, outcome_state if isinstance(outcome_state, dict) else view
            )

            code = getattr(outcome, "code", "OK")
            outcome_data = dict(getattr(outcome, "data", {}) or {})
            revision = assign_next_revision(state)
            metadata = command_metadata(incoming, action=action, state_revision=revision)
            result_data = attach_metadata(
                {"state": copy.deepcopy(state), **outcome_data}, metadata
            )
            remember_command(state, command_id, metadata=metadata, result=result_data)
            self._save_state(state)
            return DiamondGameOperationsResult(code, result_data)
