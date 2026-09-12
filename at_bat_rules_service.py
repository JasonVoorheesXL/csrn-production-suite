"""Operator-facing plate-appearance boundary (CSRN_NFHS_Baseball_Softball_
Rules_Engine_Spec_2026 Sec.7.2/Sec.13.2). Validates structurally (rules_
validator), applies via diamond_state_service's single structural
interpreter (so a live call and a later replay always agree), closes the
half-inning when three outs are reached (inning_service), and re-evaluates
game-end candidacy after every finalized play (Sec.11.1, game_end_
evaluator). Mirrors GameOperationsService/PeriodService's guard-then-
mutate-then-report shape for football.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from diamond_state_service import DiamondStateFoundation
from game_end_evaluator import GameEndEvaluator
from inning_service import InningService
from rules_validator import RulesValidator


@dataclass(frozen=True)
class AtBatResult:
    code: str
    state: dict[str, Any]
    data: dict[str, Any]

    @property
    def ok(self) -> bool:
        return self.code == "OK"


class AtBatRulesService:
    @classmethod
    def _after_play(cls, state: dict[str, Any]) -> dict[str, Any]:
        """Common tail for every play/ruling: close the half-inning if
        three outs were just reached, then re-evaluate game-end candidacy
        (Sec.11.1: 'After every finalized play and every half-inning
        boundary, evaluate walk-off, regulation, run-rule, time-limit and
        suspension conditions')."""
        inning_result = None
        if InningService.half_inning_is_over(state):
            inning_result = InningService.close_half_inning(state)
        candidate = GameEndEvaluator.evaluate(state)
        state["game_end_candidate"] = candidate
        return {
            "half_inning_closed": bool(inning_result and inning_result.ok),
            "inning_event": inning_result.data.get("event") if inning_result and inning_result.ok else None,
            "game_end_candidate": candidate,
        }

    @classmethod
    def record_plate_appearance(cls, state: dict[str, Any], payload: Mapping[str, Any]) -> AtBatResult:
        messages = RulesValidator.validate_plate_appearance(state, payload)
        if RulesValidator.has_hard_error(messages):
            return AtBatResult("HARD_ERROR", state, {"messages": messages})

        DiamondStateFoundation.apply_plate_appearance(state, payload)
        event = DiamondStateFoundation.append_event(state, "PLATE_APPEARANCE", payload)
        tail = cls._after_play(state)
        return AtBatResult("OK", state, {"messages": messages, "event": event, **tail})

    @classmethod
    def record_ruling(cls, state: dict[str, Any], payload: Mapping[str, Any]) -> AtBatResult:
        """Sec.6.2 UmpireRulingPayload -- applied exactly as recorded, no
        engine judgment (acceptance test RUL-01: 'Obstruction with award to
        third -> UMPIRE_RULING moves runner to third; no engine judgment of
        deserved base')."""
        DiamondStateFoundation.apply_ruling(state, payload)
        event = DiamondStateFoundation.append_event(state, "RULING", payload)
        tail = cls._after_play(state)
        return AtBatResult("OK", state, {"event": event, **tail})

    @classmethod
    def confirm_game_end(cls, state: dict[str, Any], reason: str) -> AtBatResult:
        """Sec.11.2: 'The scorer/umpire can confirm official termination
        when the local procedure requires it.' A GAME_END_CANDIDATE never
        finalizes a game on its own -- this explicit call does."""
        state["official_game_end_reason"] = reason
        state["status"] = "completed"
        return AtBatResult("OK", state, {"official_game_end_reason": reason})
