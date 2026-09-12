"""Regulation / run-rule / walk-off / time-limit / tiebreaker evaluation
(CSRN_NFHS_Baseball_Softball_Rules_Engine_Spec_2026 Sec.11). "Do not create
a universal NFHS mercy rule" -- every threshold comes from the active
ruleset's runRules (empty at the NFHS-generic tier this round ships;
MHSAA's real numbers are P6, gated on the owner's own handbook
confirmation). This module only ever proposes a GAME_END_CANDIDATE; per
Sec.11.2 "the scorer/umpire can confirm official termination when the
local procedure requires it" -- finalizing the game is a separate,
explicit operator action (diamond_event_service / at_bat_rules_service,
this round or P2), never automatic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import ruleset_service
from diamond_state_service import DiamondStateFoundation


@dataclass(frozen=True)
class GameEndResult:
    code: str
    state: dict[str, Any]
    data: dict[str, Any]

    @property
    def ok(self) -> bool:
        return self.code == "OK"


class GameEndEvaluator:
    @classmethod
    def _sport(cls, state: Mapping[str, Any]) -> str:
        return str(state.get("sport", "baseball") or "baseball").lower()

    @classmethod
    def _ruleset(cls, state: Mapping[str, Any]) -> Mapping[str, Any]:
        return ruleset_service.active_ruleset(state, sport=cls._sport(state))

    @classmethod
    def evaluate(cls, state: Mapping[str, Any]) -> dict[str, Any] | None:
        """Sec.11.1 evaluation order (walk-off first, then run-rule, then
        regulation). Call after every finalized play and every half-inning
        boundary. Pure read -- never mutates state, never finalizes the
        game."""
        candidate = cls._walk_off_candidate(state)
        if candidate:
            return candidate
        candidate = cls._run_rule_candidate(state)
        if candidate:
            return candidate
        candidate = cls._regulation_candidate(state)
        if candidate:
            return candidate
        return None

    @classmethod
    def _walk_off_candidate(cls, state: Mapping[str, Any]) -> dict[str, Any] | None:
        # Sec.7.3: home takes the lead in the bottom of the final scheduled
        # inning (or an extra inning) -> candidate immediately, do not wait
        # for three outs.
        half = str(state.get("inning_half", "TOP")).upper()
        if not half.startswith("B"):
            return None
        inning = int(state.get("inning", 1))
        scheduled = int(cls._ruleset(state).get("regulation", {}).get("scheduledInnings", 7))
        if inning < scheduled:
            return None
        home = int(state.get("home_score", 0))
        visitor = int(state.get("visitor_score", 0))
        if home <= visitor:
            return None
        return {"reason": "WALK_OFF", "inning": inning, "half": "BOTTOM"}

    @classmethod
    def _run_rule_candidate(cls, state: Mapping[str, Any]) -> dict[str, Any] | None:
        # Sec.11.2 algorithm: for each threshold, if the run differential is
        # met at or after the earliest eligible inning AND the trailing team
        # has completed the required turn at bat, it's a candidate. "Turn
        # complete" is evaluated at the half-inning boundary (this is called
        # right after InningService.close_half_inning(), so inning/half
        # already reflect the post-transition situation):
        #   - home leading (visitor trailing): visitor's turn in `earliest`
        #     is complete once we've reached BOTTOM of `earliest` (or later)
        #     -- END-01: home leads after visitor completes top 5.
        #   - visitor leading (home trailing): home's turn in `earliest`
        #     is only complete once we've moved past it entirely (inning >
        #     earliest) -- END-02: home receives its required bottom-half
        #     opportunity before termination, even though visitor already
        #     led entering the bottom half.
        home = int(state.get("home_score", 0))
        visitor = int(state.get("visitor_score", 0))
        diff = abs(home - visitor)
        if diff == 0 or home == visitor:
            return None
        inning = int(state.get("inning", 1))
        half = str(state.get("inning_half", "TOP")).upper()
        trailing = "visitor" if home > visitor else "home"
        for threshold in cls._ruleset(state).get("runRules") or []:
            run_differential = int(threshold.get("runDifferential", 0))
            earliest = int(threshold.get("earliestCompletedInning", 0))
            if diff < run_differential or inning < earliest:
                continue
            if trailing == "visitor":
                turn_complete = inning > earliest or (inning == earliest and half.startswith("B"))
            else:
                turn_complete = inning > earliest
            if turn_complete:
                return {
                    "reason": "RUN_RULE",
                    "thresholdId": threshold.get("id", ""),
                    "inning": inning,
                    "trailingTeam": trailing,
                }
        return None

    @classmethod
    def _regulation_candidate(cls, state: Mapping[str, Any]) -> dict[str, Any] | None:
        # Sec.11.1: "trailing team has completed its required turn at bat;
        # if tied, continue according to tiebreaker/extra-inning policy."
        home = int(state.get("home_score", 0))
        visitor = int(state.get("visitor_score", 0))
        if home == visitor:
            return None  # extras -- never a regulation candidate while tied
        inning = int(state.get("inning", 1))
        half = str(state.get("inning_half", "TOP")).upper()
        scheduled = int(cls._ruleset(state).get("regulation", {}).get("scheduledInnings", 7))
        trailing = "visitor" if home > visitor else "home"
        if trailing == "visitor":
            turn_complete = inning > scheduled or (inning == scheduled and half.startswith("B"))
        else:
            turn_complete = inning > scheduled
        if turn_complete:
            return {"reason": "REGULATION", "inning": inning}
        return None

    @classmethod
    def seed_tiebreaker_runner(
        cls, state: dict[str, Any], player_id: str
    ) -> GameEndResult:
        """Sec.11.3: only when the active profile's tieBreaker.mode is
        RUNNER_ON_SECOND, the score is tied, and play has moved past
        regulation. Sec.9.4/Sec.11.3 mandate this as a first-class event
        (TIEBREAKER_RUNNER_PLACED), never a silent base mutation --
        seededRunnerSelection (which player) is the caller's decision
        (PREVIOUS_BATTER / PROFILE_DEFINED / MANUAL per the profile); this
        evaluator only enforces the structural eligibility."""
        ruleset = cls._ruleset(state)
        tie_breaker = ruleset.get("tieBreaker") or {}
        if str(tie_breaker.get("mode", "NONE")).upper() != "RUNNER_ON_SECOND":
            return GameEndResult("TIEBREAKER_NOT_ACTIVE", state, {})
        scheduled = int(ruleset.get("regulation", {}).get("scheduledInnings", 7))
        starts_at = int(tie_breaker.get("startsAtInning") or (scheduled + 1))
        inning = int(state.get("inning", 1))
        if inning < starts_at:
            return GameEndResult("NOT_YET_ELIGIBLE", state, {})
        if int(state.get("home_score", 0)) != int(state.get("visitor_score", 0)):
            return GameEndResult("NOT_TIED", state, {})
        base = "second"
        if (state.get("base_runners") or {}).get(base):
            return GameEndResult("BASE_OCCUPIED", state, {})
        payload = {"base": base, "playerId": player_id}
        DiamondStateFoundation.apply_tiebreaker_runner_placed(state, payload)
        event = DiamondStateFoundation.append_event(state, "TIEBREAKER_RUNNER_PLACED", payload)
        return GameEndResult("OK", state, {"event": event})
