"""Operator-facing correction boundary for the basketball engine
(docs/BASKETBALL_ENGINE_SCOPING_PLAN.md Sec.2/Sec.10 P2 row:
"hoops_event_service (operator boundary, edit/undo/restore,
EVENT_VOIDED/EVENT_CORRECTED)"). Mirrors diamond_event_service.py's role
for baseball/softball exactly -- same "'undo' is a visible correction
event, not destructive deletion" discipline. Every operation here voids
or appends -- never deletes -- and recomputes state via
HoopsStateFoundation.rebuild(), the same structural interpreters a live
play uses, so a correction's result is always exactly what replaying the
corrected ledger from scratch would produce.

Undo/redo mirrors diamond_event_service's own contract: undo voids the
most recent contributing event, redo un-voids the most recently voided
one, both via a full rebuild rather than an incremental patch. This only
works because hoops_period_service.start_game() appends its own
GAME_START event (P2 finding -- see hoops_state_service.apply_game_start()'s
docstring): a rebuild from just the ledger, no baseline, must be able to
reproduce the ruleset-derived period length / timeouts / shot clock a
live game started with, or undoing back past the first real play would
reset those to zero/blank.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from hoops_state_service import HoopsStateFoundation


@dataclass(frozen=True)
class HoopsEventResult:
    code: str
    state: dict[str, Any]
    data: dict[str, Any]

    @property
    def ok(self) -> bool:
        return self.code == "OK"


class HoopsEventService:
    @classmethod
    def _contributing_events(cls, state: Mapping[str, Any]) -> list[dict[str, Any]]:
        hoops = state.get("hoops") or {}
        return [e for e in hoops.get("hoops_events", []) if not e.get("voided")]

    @classmethod
    def _rebuild_in_place(cls, state: dict[str, Any]) -> None:
        hoops = state.get("hoops") or {}
        rebuilt = HoopsStateFoundation.rebuild(state, hoops.get("hoops_events", []))
        state.clear()
        state.update(rebuilt)

    @classmethod
    def undo(cls, state: dict[str, Any]) -> HoopsEventResult:
        """Void the most recent contributing event and rebuild -- 'undo
        the last thing that happened', not an operator-chosen arbitrary
        event (that's void_event/correct_event, below). Refuses to undo
        GAME_START itself -- there is nothing before it to return to."""
        contributing = cls._contributing_events(state)
        if not contributing:
            return HoopsEventResult("NO_EVENTS_TO_UNDO", state, {})
        target = contributing[-1]
        if target.get("event_type") == "GAME_START":
            return HoopsEventResult("CANNOT_UNDO_GAME_START", state, {})
        HoopsStateFoundation.void_event(state.setdefault("hoops", {}), target["event_id"])
        cls._rebuild_in_place(state)
        return HoopsEventResult("OK", state, {"undone_event_id": target["event_id"]})

    @classmethod
    def redo(cls, state: dict[str, Any]) -> HoopsEventResult:
        """Un-void the most recently voided event (ledger order) and
        rebuild."""
        hoops = state.setdefault("hoops", {})
        voided = [e for e in hoops.get("hoops_events", []) if e.get("voided")]
        if not voided:
            return HoopsEventResult("NO_EVENTS_TO_REDO", state, {})
        target = voided[-1]
        for event in hoops["hoops_events"]:
            if event["event_id"] == target["event_id"]:
                event["voided"] = False
                break
        cls._rebuild_in_place(state)
        return HoopsEventResult("OK", state, {"redone_event_id": target["event_id"]})

    @classmethod
    def void_event(cls, state: dict[str, Any], event_id: str, *, reason: str = "") -> HoopsEventResult:
        """EVENT_VOIDED: targets a SPECIFIC event (not necessarily the
        most recent) -- e.g. an operator correcting a foul recorded
        several possessions ago. Refuses to void GAME_START (same
        rationale as undo())."""
        hoops = state.setdefault("hoops", {})
        original = next((e for e in hoops.get("hoops_events", []) if e.get("event_id") == event_id), None)
        if original is None:
            return HoopsEventResult("EVENT_NOT_FOUND", state, {})
        if original.get("event_type") == "GAME_START":
            return HoopsEventResult("CANNOT_VOID_GAME_START", state, {})
        found = HoopsStateFoundation.void_event(hoops, event_id)
        if not found:
            return HoopsEventResult("EVENT_NOT_FOUND", state, {})
        cls._rebuild_in_place(state)
        return HoopsEventResult("OK", state, {"voided_event_id": event_id, "reason": reason})

    @classmethod
    def correct_event(
        cls, state: dict[str, Any], event_id: str, replacement_payload: Mapping[str, Any], *, reason: str = "",
    ) -> HoopsEventResult:
        """EVENT_CORRECTED: voids the original (kept in the ledger, never
        deleted) and appends a new event of the SAME type carrying the
        corrected payload, referencing the original -- then rebuilds, so
        every canonical field downstream of the correction (team fouls,
        bonus, disqualification, score) is recomputed from the corrected
        fact, not patched by hand. This is the gate example: 'a foul
        entered late and corrected keeps team fouls + bonus + DQ right' --
        holds by construction, since the same apply_foul() interpreter
        that computed them the first time computes them again from the
        corrected payload."""
        hoops = state.setdefault("hoops", {})
        events = hoops.get("hoops_events", [])
        original = next((e for e in events if e.get("event_id") == event_id), None)
        if original is None:
            return HoopsEventResult("EVENT_NOT_FOUND", state, {})
        if original.get("event_type") == "GAME_START":
            return HoopsEventResult("CANNOT_CORRECT_GAME_START", state, {})
        HoopsStateFoundation.void_event(hoops, event_id)
        new_event = HoopsStateFoundation.append_event(hoops, original["event_type"], replacement_payload)
        new_event["corrects_event_id"] = event_id
        cls._rebuild_in_place(state)
        return HoopsEventResult(
            "OK", state, {"corrected_event_id": event_id, "new_event_id": new_event["event_id"], "reason": reason},
        )
