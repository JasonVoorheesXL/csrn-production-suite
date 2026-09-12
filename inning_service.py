"""Half-inning lifecycle (CSRN_NFHS_Baseball_Softball_Rules_Engine_Spec_2026
Sec.7.1): start with 0 outs/empty count, close at three outs (persisting
LOB, clearing bases, swapping offense/defense, advancing the inning number
after the bottom half). Mirrors PeriodService's role for football's quarter
transitions.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from diamond_state_service import DiamondStateFoundation


@dataclass(frozen=True)
class InningResult:
    code: str
    state: dict[str, Any]
    data: dict[str, Any]

    @property
    def ok(self) -> bool:
        return self.code == "OK"


class InningService:
    @classmethod
    def half_inning_is_over(cls, state: Mapping[str, Any]) -> bool:
        return int(state.get("outs", 0)) >= 3

    @classmethod
    def close_half_inning(cls, state: dict[str, Any]) -> InningResult:
        """Sec.7.1: 'At three outs, close the half-inning, persist inning
        totals/LOB, swap offense/defense, and advance the inning number
        after the bottom half.' Refuses to close early -- the caller (at_
        bat_rules_service, after applying a plate appearance) is
        responsible for calling this only once outs have actually reached
        three, same as every other CSRN *_service guard-then-mutate shape.
        """
        if not cls.half_inning_is_over(state):
            return InningResult("NOT_OVER", state, {"outs": state.get("outs", 0)})
        payload = {"leftOnBase": DiamondStateFoundation.runners_left_on_base(state)}
        DiamondStateFoundation.apply_half_inning_transition(state, payload)
        event = DiamondStateFoundation.append_event(state, "HALF_INNING_END", payload)
        return InningResult("OK", state, {"event": event})
