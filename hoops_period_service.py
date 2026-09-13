"""Period lifecycle (docs/BASKETBALL_ENGINE_SCOPING_PLAN.md Sec.2:
"Period lifecycle: quarters or halves (profile-driven) -> OT periods;
period-foul reset (NFHS quarter fouls); clock reset; end-of-period
possession-arrow handling."). Mirrors inning_service.InningService's role
for baseball's half-innings.

Ruleset-aware (unlike hoops_state_service, which never imports
ruleset_service): this module reads period.format/count/length_seconds/
ot_length_seconds and fouls.team_foul_scope from the active profile and
resolves what "the next period" means, then hands the STRUCTURAL
transition to hoops_state_service.apply_period_transition() -- the single
place that logic lives, same split diamond's inning_service/
diamond_state_service use.

Team-foul reset scope: this round only ever ships fouls.team_foul_scope=
"quarter" (basketball/us-nfhs.json, P0). "half" and "game" scope are
handled generically below (a straightforward reading of the ruleset
field), but have never been exercised against a real ruleset document --
flagged here, not silently assumed correct.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from hoops_state_service import HoopsStateFoundation

# Ordinal period labels for quarters vs halves formats. OT periods are
# handled separately (not part of either tuple) since their count is
# open-ended (ruleset's overtime.ot_count_cap, possibly null == unlimited).
_QUARTER_LABELS: tuple[str, ...] = ("1", "2", "3", "4")
_HALF_LABELS: tuple[str, ...] = ("H1", "H2")


@dataclass(frozen=True)
class PeriodResult:
    code: str
    state: dict[str, Any]
    data: dict[str, Any]

    @property
    def ok(self) -> bool:
        return self.code == "OK"


class HoopsPeriodService:
    @classmethod
    def regulation_labels(cls, ruleset: Mapping[str, Any]) -> tuple[str, ...]:
        period_format = str(ruleset.get("period", {}).get("format", "quarters"))
        count = int(ruleset.get("period", {}).get("count", 4))
        if period_format == "halves":
            labels = _HALF_LABELS
        elif period_format == "quarters":
            labels = _QUARTER_LABELS
        else:
            raise ValueError(f"unknown period.format: {period_format!r}")
        if count != len(labels):
            # The scoping doc's own ruleset shape ties count to format
            # (4 quarters / 2 halves) -- a ruleset claiming otherwise is a
            # genuine authoring inconsistency, not something to silently
            # paper over by truncating/extending the label tuple.
            raise ValueError(
                f"ruleset period.count={count} does not match "
                f"period.format={period_format!r} ({len(labels)} expected)"
            )
        return labels

    @classmethod
    def start_game(cls, state: dict[str, Any], ruleset: Mapping[str, Any]) -> PeriodResult:
        """Sets up the first period from the active ruleset: period_format,
        the first period's label and length, a fresh shot clock (if the
        profile enables one), timeout allotments (full+short combined --
        see hoops_state_service module docstring's HOOPS_OVERLAY_CONTRACT
        note: the wire only ever wants one combined remaining-count per
        team, so that's the only thing modeled here; which of a team's
        remaining timeouts is "full" vs "short" is not tracked -- flagged
        as a deliberate simplification, not an oversight), and zeroed team/
        player fouls."""
        hoops = state.setdefault("hoops", {})
        labels = cls.regulation_labels(ruleset)
        period_cfg = ruleset.get("period", {})
        length = int(period_cfg.get("length_seconds", 0))

        HoopsStateFoundation.set_period_format(hoops, str(period_cfg.get("format", "quarters")))
        state["period"] = labels[0]
        HoopsStateFoundation.set_period_length(hoops, length)
        state["clock_seconds"] = length
        state["clock_running"] = False
        state["clock_started_at"] = 0

        shot_clock_cfg = ruleset.get("shot_clock", {})
        if bool(shot_clock_cfg.get("enabled")):
            HoopsStateFoundation.set_shot_clock(
                hoops, int(shot_clock_cfg.get("length_seconds") or 0), running=False, visible=True,
            )
        else:
            HoopsStateFoundation.set_shot_clock(hoops, None, running=False, visible=False)

        timeouts_cfg = ruleset.get("timeouts", {})
        combined = int(timeouts_cfg.get("full", 0)) + int(timeouts_cfg.get("short", 0))
        HoopsStateFoundation.set_timeouts(hoops, "home", combined)
        HoopsStateFoundation.set_timeouts(hoops, "visitor", combined)

        HoopsStateFoundation.reset_team_fouls(hoops)
        hoops["player_fouls"] = {}
        hoops["disqualified"] = []
        return PeriodResult("OK", state, {"period": labels[0], "period_length_seconds": length})

    @classmethod
    def period_is_over(cls, state: Mapping[str, Any]) -> bool:
        return int(state.get("clock_seconds", 0)) <= 0

    @classmethod
    def _next_period_label(
        cls, state: Mapping[str, Any], ruleset: Mapping[str, Any],
    ) -> str:
        current = str(state.get("period", ""))
        labels = cls.regulation_labels(ruleset)
        if current in labels:
            index = labels.index(current)
            if index + 1 < len(labels):
                return labels[index + 1]
            # Last regulation period just ended.
            home = int(state.get("home_score", 0))
            visitor = int(state.get("visitor_score", 0))
            if home == visitor:
                return "OT"
            raise ValueError(
                "regulation just ended with a decided score -- the caller "
                "must check GameEndEvaluator-equivalent logic in "
                "hoops_rules_service before calling close_period() again; "
                "this function only ever proposes the NEXT period, and "
                "there isn't one when the game is over."
            )
        if current == "OT" or (current.startswith("OT") and current[2:].isdigit()):
            home = int(state.get("home_score", 0))
            visitor = int(state.get("visitor_score", 0))
            if home != visitor:
                raise ValueError(
                    "overtime just ended with a decided score -- see the "
                    "regulation-end ValueError above; same caller "
                    "responsibility."
                )
            ot_number = 1 if current == "OT" else int(current[2:])
            cap = ruleset.get("overtime", {}).get("ot_count_cap")
            if cap is not None and ot_number >= int(cap):
                raise ValueError(
                    f"ruleset overtime.ot_count_cap={cap} reached -- no next "
                    "OT period to propose; this is a genuinely unmodeled "
                    "situation (the scoping doc never specifies what "
                    "happens at the cap) and is deliberately raised rather "
                    "than guessed at."
                )
            return f"OT{ot_number + 1}"
        raise ValueError(f"unrecognized current period: {current!r}")

    @classmethod
    def close_period(cls, state: dict[str, Any], ruleset: Mapping[str, Any]) -> PeriodResult:
        """Sec.2: period lifecycle -> OT; period-foul reset; clock reset.
        Refuses to close early -- the caller is responsible for calling
        this only once the clock has actually reached 0, same guard-then-
        mutate discipline as inning_service.close_half_inning(). Raises
        (rather than silently no-oping) if there is no well-defined next
        period -- see _next_period_label()'s own comments for why that's
        the caller's job to have already ruled out via game-end evaluation."""
        if not cls.period_is_over(state):
            return PeriodResult("NOT_OVER", state, {"clock_seconds": state.get("clock_seconds", 0)})

        hoops = state.setdefault("hoops", {})
        next_period = cls._next_period_label(state, ruleset)
        is_overtime = next_period == "OT" or next_period.startswith("OT")
        if is_overtime:
            length = int(ruleset.get("overtime", {}).get("length_seconds", 0))
        else:
            length = int(ruleset.get("period", {}).get("length_seconds", 0))

        scope = str(ruleset.get("fouls", {}).get("team_foul_scope", "quarter"))
        # "quarter" (the only scope any shipped ruleset uses) resets every
        # period, OT included. "half"/"game" are read straight from the
        # field but have no shipped ruleset exercising them -- see module
        # docstring.
        reset_fouls = scope == "quarter" or (
            scope == "half" and str(ruleset.get("period", {}).get("format")) == "halves"
        )

        shot_clock_cfg = ruleset.get("shot_clock", {})
        shot_clock_enabled = bool(shot_clock_cfg.get("enabled"))
        payload = {
            "nextPeriod": next_period,
            "nextPeriodLengthSeconds": length,
            "resetTeamFouls": reset_fouls,
            # Shot clock resets to the profile's full length (if enabled)
            # entering every new period, same as the game clock -- not
            # left at whatever it happened to read when the old period's
            # clock hit 0.
            "shotClockSeconds": int(shot_clock_cfg.get("length_seconds") or 0) if shot_clock_enabled else None,
            "shotClockVisible": shot_clock_enabled,
        }
        HoopsStateFoundation.apply_period_transition(state, hoops, payload)
        event = HoopsStateFoundation.append_event(hoops, "PERIOD_TRANSITION", payload)
        return PeriodResult("OK", state, {"event": event, "period": next_period, "is_overtime": is_overtime})
