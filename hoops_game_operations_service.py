"""Basketball equivalent of GameOperationsService's lifecycle/persistence
boundary -- the "game_operations_service" row in docs/BASKETBALL_ENGINE_
SCOPING_PLAN.md Sec.2, delivered here in P4 same as baseball deferred its
own diamond_game_operations_service.py to its P4.

Deliberately a SEPARATE module rather than an edit to
game_operations_service.py -- same reasoning as baseball's
diamond_game_operations_service.py: GameOperationsService is football's
shared, already-frozen persistence/locking boundary; this class reuses
the exact same load_state/save_state/transaction_lock plumbing and the
same live_command_service idempotency/metadata helpers, but never
imports or edits that file.

Unlike diamond_game_operations_service.dispatch() (baseball), this
dispatch() does NOT route through a hoops_view()/commit_hoops_view()
flattening step. That adapter exists in engine_router.py (P0) but was
confirmed UNUSED as of P3 (see engine_router.commit_hoops_view()'s own
docstring): every hoops_state_service/hoops_rules_service/
hoops_period_service/hoops_event_service/hoops_lineup_service classmethod
was designed from P1 onward to take the full outer `state` dict directly
(reading/writing state["hoops"] and the shared period/clock/possession/
score fields itself), unlike baseball's P0-P3 modules, which were built
and tested against ONE flat dict predating the state["diamond"]
namespacing decision and therefore genuinely need diamond_view() to
reconcile the two. Basketball never had that problem, so dispatch() here
just passes `state` straight through to whichever P1/P2 classmethod ran,
and persists whatever it mutated in place -- confirming, not working
around, the P3 finding.

dispatch() is one generic method rather than ~13 hand-written wrapper
methods, same rationale as baseball's own: every P1/P2 basketball
classmethod already follows the `state` first, everything else a plain
keyword-bindable argument (or a single `payload: Mapping`) shape, so
dispatch() resolves the action name against ACTIONS and binds the
payload's own keys onto that function's parameter names. Adding a future
P1/P2 mutator later is a one-line ACTIONS entry, not a new wrapper method.
"""

from __future__ import annotations

import copy
import inspect
from dataclasses import dataclass
from typing import Any, Callable, Mapping

import engine_router
from hoops_event_service import HoopsEventService
from hoops_lineup_service import HoopsLineupService
from hoops_period_service import HoopsPeriodService
from hoops_rules_service import HoopsRulesService
from live_command_service import (
    assign_next_revision,
    attach_metadata,
    command_id_from,
    command_metadata,
    duplicate_result,
    remember_command,
)


@dataclass(frozen=True)
class HoopsGameOperationsResult:
    code: str
    data: dict[str, Any]

    @property
    def ok(self) -> bool:
        return self.code == "OK"


# Action name -> bound classmethod. Every entry's own signature is
# `(state, ...)` (the implicit `cls` aside) -- the same convention every
# P1/P2 hoops service already follows, so a single generic dispatch() can
# drive all of them identically.
ACTIONS: dict[str, Callable[..., Any]] = {
    # hoops_rules_service (P1/P2)
    "shot": HoopsRulesService.shot,
    "free_throw": HoopsRulesService.free_throw,
    "rebound": HoopsRulesService.rebound,
    "foul": HoopsRulesService.foul,
    "held_ball": HoopsRulesService.held_ball,
    "turnover": HoopsRulesService.turnover,
    "violation": HoopsRulesService.violation,
    "ruling": HoopsRulesService.ruling,
    "timeout": HoopsRulesService.timeout,
    "set_value": HoopsRulesService.set_value,
    "correct_foul": HoopsRulesService.correct_event_for_foul,
    "confirm_game_end": HoopsRulesService.confirm_game_end,
    # hoops_event_service (P2 -- undo/redo/correction boundary)
    "undo": HoopsEventService.undo,
    "redo": HoopsEventService.redo,
    "void_event": HoopsEventService.void_event,
    "correct_event": HoopsEventService.correct_event,
    # hoops_lineup_service (P2)
    "set_starting_five": HoopsLineupService.set_starting_five,
    "substitute": HoopsLineupService.substitute,
}

# live_command_service's control-metadata keys (client_id, command_id, ...)
# ride along in every route payload but are never valid arguments to any
# ACTIONS entry -- excluded on top of the normal signature-membership
# filter purely for clarity/documentation; _bind_kwargs's signature check
# would already drop them.
_CONTROL_KEYS: frozenset[str] = frozenset({"command_id", "client_id", "source"})


def _bind_kwargs(func: Callable[..., Any], payload: Mapping[str, Any]) -> dict[str, Any]:
    """Binds `payload`'s own keys onto `func`'s parameter names. shot()/
    free_throw()/rebound()/foul()/held_ball()/turnover() take their whole
    argument as one `payload: Mapping` parameter -- for those, the whole
    incoming dict (minus control keys, unless the caller already nested
    it under an explicit "payload" key) is passed through as that single
    argument instead of being matched key-by-key. correct_foul()
    deliberately does NOT use this parameter name (see its own docstring)
    precisely so it falls through to plain by-name binding instead."""
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


class HoopsGameOperationsService:
    """Live basketball-game-operation boundary, independent of Flask --
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

    def initialize_hoops(
        self, payload: Mapping[str, Any] | None = None
    ) -> HoopsGameOperationsResult:
        """(Re)creates state["hoops"] AND the shared period/clock/
        possession fields for the current broadcast -- called once when
        an operator starts a new basketball broadcast, so the overlay
        shows period 1 / a full game clock immediately. Unlike baseball's
        initialize_diamond() (which just assigns default_diamond_state()
        -- diamond's canonical defaults need no ruleset), basketball's
        initial values (period length, shot clock, timeouts) ARE
        ruleset-derived, so this calls hoops_period_service.start_game()
        (which resolves the active ruleset itself and appends the
        replayable GAME_START event -- see hoops_state_service.
        apply_game_start()'s own docstring for why that has to be a real
        event, not an unlogged setup mutation)."""
        incoming = dict(payload or {})
        with self._transaction_lock:
            state = copy.deepcopy(dict(self._load_state()))
            if not engine_router.is_hoops_sport(state):
                return HoopsGameOperationsResult(
                    "NOT_A_HOOPS_SPORT", {"state": copy.deepcopy(state)}
                )
            command_id = command_id_from(incoming)
            duplicate = duplicate_result(state, command_id)
            if duplicate is not None:
                return HoopsGameOperationsResult("OK", duplicate)

            ruleset = HoopsRulesService.active_ruleset(state)
            state["hoops"] = engine_router.default_hoops_state()
            HoopsPeriodService.start_game(state, ruleset)
            revision = assign_next_revision(state)
            metadata = command_metadata(
                incoming, action="initialize_hoops", state_revision=revision
            )
            result_data = attach_metadata({"state": copy.deepcopy(state)}, metadata)
            remember_command(state, command_id, metadata=metadata, result=result_data)
            self._save_state(state)
            return HoopsGameOperationsResult("OK", result_data)

    def dispatch(
        self, action: str, payload: Mapping[str, Any] | None = None
    ) -> HoopsGameOperationsResult:
        """Runs one of ACTIONS against the current broadcast's basketball
        state. `payload` supplies that action's own keyword arguments by
        name (e.g. {"team": "home", "playerId": "p9", "foulType":
        "personal"} for "foul")."""
        func = ACTIONS.get(action)
        if func is None:
            return HoopsGameOperationsResult("UNKNOWN_ACTION", {"action": action})
        incoming = dict(payload or {})

        with self._transaction_lock:
            state = copy.deepcopy(dict(self._load_state()))
            if not engine_router.is_hoops_sport(state):
                return HoopsGameOperationsResult(
                    "NOT_A_HOOPS_SPORT", {"state": copy.deepcopy(state)}
                )
            command_id = command_id_from(incoming)
            duplicate = duplicate_result(state, command_id)
            if duplicate is not None:
                return HoopsGameOperationsResult("OK", duplicate)

            kwargs = _bind_kwargs(func, incoming)
            try:
                outcome = func(state, **kwargs)
            except (ValueError, KeyError, TypeError) as exc:
                return HoopsGameOperationsResult("INVALID_REQUEST", {"message": str(exc)})

            # Every P1/P2 classmethod mutates `state` in place and returns
            # it as `.state` too -- nothing to fold back the way
            # commit_diamond_view() does for baseball (see module
            # docstring); `state` is already the up-to-date dict.
            code = getattr(outcome, "code", "OK")
            outcome_data = dict(getattr(outcome, "data", {}) or {})
            revision = assign_next_revision(state)
            metadata = command_metadata(incoming, action=action, state_revision=revision)
            result_data = attach_metadata(
                {"state": copy.deepcopy(state), **outcome_data}, metadata
            )
            remember_command(state, command_id, metadata=metadata, result=result_data)
            self._save_state(state)
            return HoopsGameOperationsResult(code, result_data)
