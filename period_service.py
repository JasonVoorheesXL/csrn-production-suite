from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Mapping

from canonical_state_service import CanonicalStateFoundation


@dataclass(frozen=True)
class PeriodResult:
    code: str
    state: dict[str, Any]
    data: dict[str, Any]

    @property
    def ok(self) -> bool:
        return self.code == "OK"


class PeriodService:
    """Canonical football period lifecycle reducer.

    This service mutates only the supplied state copy. Persistence/history/source
    authority remain owned by GameOperationsService.
    """

    VALID_TEAMS = {"home", "visitor"}

    # Period structure + quarter length, sourced once from the football
    # ruleset (US/MS/MHSAA). Literals are the frozen fallback + golden anchor.
    _QUARTERS_FALLBACK = ("1", "2", "3", "4", "OT")
    _QUARTER_SECONDS_FALLBACK = 720
    _period_cache: dict[str, Any] | None = None

    @classmethod
    def _period(cls) -> dict[str, Any]:
        if cls._period_cache is None:
            quarters = list(cls._QUARTERS_FALLBACK)
            seconds = cls._QUARTER_SECONDS_FALLBACK
            try:
                import ruleset_service

                period = ruleset_service.resolve(
                    country="US", region="MS", association="MHSAA", sport="football"
                ).get("period", {})
                if isinstance(period.get("quarters"), list) and period["quarters"]:
                    quarters = [str(q).strip().upper() for q in period["quarters"]]
                if isinstance(period.get("quarter_length_seconds"), int):
                    seconds = int(period["quarter_length_seconds"])
            except Exception:
                quarters = list(cls._QUARTERS_FALLBACK)
                seconds = cls._QUARTER_SECONDS_FALLBACK
            cls._period_cache = {"quarters": quarters, "quarter_seconds": seconds}
        return cls._period_cache

    @classmethod
    def _quarter(cls, value: Any) -> str:
        text = str(value or "1").strip().upper()
        valid = cls._period()["quarters"]
        return text if text in valid else valid[0]

    @staticmethod
    def _swap_directions(state: dict[str, Any]) -> None:
        home = str(state.get("home_direction", "right") or "right").lower()
        visitor = str(state.get("visitor_direction", "left") or "left").lower()
        state["home_direction"] = "left" if home == "right" else "right"
        state["visitor_direction"] = "left" if visitor == "right" else "right"

    @classmethod
    def _stop_clock(cls, state: dict[str, Any], *, reset: bool = False) -> None:
        state["clock_running"] = False
        state["clock_started_at"] = 0
        if reset:
            state["clock_seconds"] = cls._period()["quarter_seconds"]

    @classmethod
    def _period_hold_reason(cls, state: Mapping[str, Any]) -> str:
        phase = str(state.get("special_game_phase", "") or "").lower()
        if phase == "pending_try":
            return "PENDING_TRY"
        admin = state.get("penalty_administration")
        if isinstance(admin, Mapping) and bool(admin.get("untimed_down")):
            return "UNTIMED_DOWN"
        if bool(state.get("untimed_down_pending")):
            return "UNTIMED_DOWN"
        return ""

    @classmethod
    def _opening_kicking_team(cls, state: Mapping[str, Any]) -> str:
        explicit = str(state.get("opening_kicking_team", "") or "").lower()
        if explicit in cls.VALID_TEAMS:
            return explicit
        plays = state.get("plays")
        if isinstance(plays, list):
            for play in plays:
                if not isinstance(play, Mapping) or bool(play.get("undone")):
                    continue
                if str(play.get("play_type", "") or "").lower() == "kickoff":
                    team = str(play.get("offense", "") or "").lower()
                    if team in cls.VALID_TEAMS:
                        return team
        return ""

    @classmethod
    def _second_half_receiver(cls, state: Mapping[str, Any], requested: Any = "") -> str:
        team = str(requested or state.get("second_half_receiving_team", "") or "").lower()
        if team in cls.VALID_TEAMS:
            return team
        # The team that kicked the opening kickoff receives to start the second half.
        return cls._opening_kicking_team(state)

    @classmethod
    def transition(
        cls,
        state: Mapping[str, Any],
        action: Any,
        *,
        second_half_receiving_team: Any = "",
        overtime_possession: Any = "",
        overtime_spot: Any = "",
    ) -> PeriodResult:
        current = copy.deepcopy(dict(state))
        command = str(action or "").strip().lower()
        quarter = cls._quarter(current.get("quarter"))

        if command == "end_quarter":
            hold = cls._period_hold_reason(current)
            if hold:
                current["period_state"] = "held"
                current["period_hold_reason"] = hold
                return PeriodResult(
                    "PERIOD_HELD",
                    current,
                    {"reason": hold, "quarter": quarter},
                )

            cls._stop_clock(current)
            current["period_hold_reason"] = ""
            current["awaiting_period_decision"] = False

            if quarter == "1":
                cls._swap_directions(current)
                current["quarter"] = "2"
                current["period_state"] = "quarter"
                cls._stop_clock(current, reset=True)
                return PeriodResult("OK", current, {"transition": "Q1_TO_Q2"})

            if quarter == "2":
                current["broadcast_phase"] = "halftime"
                current["period_state"] = "halftime"
                current["halftime_pending_second_half"] = True
                current["scorebug_visible"] = True
                return PeriodResult("OK", current, {"transition": "Q2_TO_HALFTIME"})

            if quarter == "3":
                cls._swap_directions(current)
                current["quarter"] = "4"
                current["period_state"] = "quarter"
                cls._stop_clock(current, reset=True)
                return PeriodResult("OK", current, {"transition": "Q3_TO_Q4"})

            # Q4 and overtime end explicitly require an operator decision.
            current["period_state"] = "q4_complete" if quarter == "4" else "overtime_complete"
            current["awaiting_period_decision"] = True
            return PeriodResult(
                "OK",
                current,
                {
                    "transition": "Q4_COMPLETE" if quarter == "4" else "OVERTIME_COMPLETE",
                    "decision_required": True,
                    "tied": int(current.get("home_score", 0) or 0) == int(current.get("visitor_score", 0) or 0),
                },
            )

        if command == "start_second_half":
            if str(current.get("broadcast_phase", "") or "").lower() != "halftime":
                return PeriodResult("INVALID_PERIOD_ACTION", current, {"message": "Second half can start only from halftime."})
            receiver = cls._second_half_receiver(current, second_half_receiving_team)
            if receiver not in cls.VALID_TEAMS:
                return PeriodResult(
                    "SECOND_HALF_RECEIVER_REQUIRED",
                    current,
                    {"message": "Select the team receiving the second-half kickoff."},
                )
            kicker = CanonicalStateFoundation.opposite(receiver)
            cls._swap_directions(current)
            current["quarter"] = "3"
            current["broadcast_phase"] = "live"
            current["period_state"] = "quarter"
            current["halftime_pending_second_half"] = False
            current["second_half_receiving_team"] = receiver
            current["opening_kicking_team"] = cls._opening_kicking_team(current)
            cls._stop_clock(current, reset=True)
            CanonicalStateFoundation.enter_kickoff(current, kicker)
            current["scorebug_visible"] = True
            return PeriodResult(
                "OK",
                current,
                {"transition": "HALFTIME_TO_Q3_KICKOFF", "kicking_team": kicker, "receiving_team": receiver},
            )

        if command == "start_overtime":
            if str(current.get("period_state", "") or "") not in {"q4_complete", "overtime_complete"}:
                return PeriodResult("INVALID_PERIOD_ACTION", current, {"message": "Overtime can start only after regulation or an overtime period is complete."})
            team = str(overtime_possession or "").lower()
            spot = str(overtime_spot or "").strip()
            if team not in cls.VALID_TEAMS or not spot:
                return PeriodResult(
                    "OVERTIME_SETUP_REQUIRED",
                    current,
                    {"message": "Select overtime possession and an association-approved starting spot."},
                )
            current["quarter"] = "OT"
            current["broadcast_phase"] = "live"
            current["period_state"] = "overtime"
            current["awaiting_period_decision"] = False
            current["possession"] = team
            current["down"] = "1st"
            current["distance"] = "10"
            current["ball_spot"] = spot
            CanonicalStateFoundation.clear_special_phase(current)
            cls._stop_clock(current)
            current["clock_visible"] = False
            current["scorebug_visible"] = True
            current["overtime_number"] = int(current.get("overtime_number", 0) or 0) + 1
            return PeriodResult(
                "OK",
                current,
                {"transition": "START_OVERTIME", "overtime_number": current["overtime_number"]},
            )

        if command == "final_game":
            if str(current.get("period_state", "") or "") not in {"q4_complete", "overtime_complete"}:
                return PeriodResult("INVALID_PERIOD_ACTION", current, {"message": "Final game can be confirmed only after Q4 or overtime is complete."})
            cls._stop_clock(current)
            current["broadcast_phase"] = "final"
            current["period_state"] = "final"
            current["awaiting_period_decision"] = False
            current["scorebug_visible"] = False
            current["status"] = "completed"
            return PeriodResult("OK", current, {"transition": "FINAL_GAME"})

        if command == "clear_untimed_down":
            current["untimed_down_pending"] = False
            admin = current.get("penalty_administration")
            if isinstance(admin, dict):
                admin = copy.deepcopy(admin)
                admin["untimed_down"] = False
                current["penalty_administration"] = admin
            if str(current.get("period_state", "")) == "held":
                current["period_state"] = "quarter"
                current["period_hold_reason"] = ""
            return PeriodResult("OK", current, {"transition": "UNTIMED_DOWN_CLEARED"})

        return PeriodResult("INVALID_PERIOD_ACTION", current, {})
