"""Operator-facing correction boundary for the diamond engine (CSRN_NFHS_
Baseball_Softball_Rules_Engine_Spec_2026 Sec.15.2, Sec.2.1). "'Undo' should
be implemented as a visible correction event, not destructive deletion."
Every operation here voids or appends -- never deletes -- and recomputes
state via DiamondStateFoundation.rebuild(), the same structural interpreters
a live play uses, so a correction's result is always exactly what replaying
the corrected ledger from scratch would produce.

Undo/redo mirrors EventService's football contract (docs/PHASE_C_THEME_
SPORT_DISPATCH_PLAN.md-era work; the football undo/redo corruption fix
earlier this project): undo voids the most recent contributing event,
redo un-voids the most recently voided one, both via a full rebuild rather
than an incremental patch -- the same "rebuild is the only place state
gets computed" discipline P1's diamond_state_service established.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from diamond_state_service import DiamondStateFoundation


@dataclass(frozen=True)
class DiamondEventResult:
    code: str
    state: dict[str, Any]
    data: dict[str, Any]

    @property
    def ok(self) -> bool:
        return self.code == "OK"


class DiamondEventService:
    @classmethod
    def _contributing_events(cls, state: Mapping[str, Any]) -> list[dict[str, Any]]:
        return [e for e in state.get("diamond_events", []) if not e.get("voided")]

    @classmethod
    def _rebuild_in_place(cls, state: dict[str, Any]) -> None:
        rebuilt = DiamondStateFoundation.rebuild(state, state.get("diamond_events", []))
        state.clear()
        state.update(rebuilt)

    @classmethod
    def undo(cls, state: dict[str, Any]) -> DiamondEventResult:
        """Void the most recent contributing event and rebuild -- 'undo the
        last thing that happened', not an operator-chosen arbitrary event
        (that's void_event/correct_event, below)."""
        contributing = cls._contributing_events(state)
        if not contributing:
            return DiamondEventResult("NO_EVENTS_TO_UNDO", state, {})
        target = contributing[-1]
        DiamondStateFoundation.void_event(state, target["event_id"])
        cls._rebuild_in_place(state)
        return DiamondEventResult("OK", state, {"undone_event_id": target["event_id"]})

    @classmethod
    def redo(cls, state: dict[str, Any]) -> DiamondEventResult:
        """Un-void the most recently voided event (ledger order) and
        rebuild."""
        voided = [e for e in state.get("diamond_events", []) if e.get("voided")]
        if not voided:
            return DiamondEventResult("NO_EVENTS_TO_REDO", state, {})
        target = voided[-1]
        for event in state["diamond_events"]:
            if event["event_id"] == target["event_id"]:
                event["voided"] = False
                break
        cls._rebuild_in_place(state)
        return DiamondEventResult("OK", state, {"redone_event_id": target["event_id"]})

    @classmethod
    def void_event(cls, state: dict[str, Any], event_id: str, *, reason: str = "") -> DiamondEventResult:
        """Sec.15.2 EVENT_VOIDED: 'References original event; original no
        longer contributes to reduced state.' Targets a SPECIFIC event (not
        necessarily the most recent) -- e.g. an operator correcting a play
        recorded several batters ago."""
        found = DiamondStateFoundation.void_event(state, event_id)
        if not found:
            return DiamondEventResult("EVENT_NOT_FOUND", state, {})
        cls._rebuild_in_place(state)
        return DiamondEventResult("OK", state, {"voided_event_id": event_id, "reason": reason})

    @classmethod
    def correct_event(
        cls, state: dict[str, Any], event_id: str, replacement_payload: Mapping[str, Any], *, reason: str = ""
    ) -> DiamondEventResult:
        """Sec.15.2 EVENT_CORRECTED: 'References original and supplies
        replacement payload/event.' COR-01: 'Scorer corrects runner
        destination -> Original event retained; correction recomputes
        bases/score/stats.' Voids the original (kept in the ledger, not
        deleted) and appends a new event of the SAME type carrying the
        corrected payload, referencing the original -- then rebuilds, so
        every canonical field downstream of the correction (bases, score,
        stats) is recomputed from the corrected fact, not patched by hand."""
        events = state.get("diamond_events", [])
        original = next((e for e in events if e.get("event_id") == event_id), None)
        if original is None:
            return DiamondEventResult("EVENT_NOT_FOUND", state, {})
        DiamondStateFoundation.void_event(state, event_id)
        new_event = DiamondStateFoundation.append_event(state, original["event_type"], replacement_payload)
        new_event["corrects_event_id"] = event_id
        cls._rebuild_in_place(state)
        return DiamondEventResult(
            "OK", state, {"corrected_event_id": event_id, "new_event_id": new_event["event_id"], "reason": reason}
        )
