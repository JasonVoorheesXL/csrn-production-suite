"""Basketball rules orchestration (docs/BASKETBALL_ENGINE_SCOPING_PLAN.md
Sec.2: "shot() (2/3, made/missed -> score + possession), foul() (type +
shooter -> team-foul accumulation, bonus check, foul-out check, FT
award), free_throw(), possession() (incl. alternating-possession arrow)".
Mirrors the combined role of baseball's rules_validator.py +
at_bat_rules_service.py + game_end_evaluator.py: validates structurally,
applies via hoops_state_service's single structural interpreter per event
type (so a live call and a later replay always agree), closes the period
when the clock reaches 0 (hoops_period_service), and re-evaluates
game-end candidacy after every finalized play.

Sec.1's "record the ruling, don't officiate" principle, same as every
other CSRN sport engine: this module never decides whether a foul
happened, what type it was, made-vs-missed, or whether a basket counts --
those are the operator's/official's call, passed in as payload fields.
What it DOES compute (Sec.3.2 "auto" column) are the bookkeeping
consequences of an already-decided foul type: whether it counts toward
the team-foul/bonus total, whether it counts toward the player's personal
total (and therefore a foul-out), and a PROPOSED free-throw count from
foul type + bonus situation -- proposed, not applied: the caller still
records each actual free-throw attempt via free_throw(), same as the
scoping doc's own "engine proposes... operator confirms" wording (Sec.5.1
event table, "Foul" row).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import ruleset_service
from hoops_period_service import HoopsPeriodService
from hoops_state_service import HoopsStateFoundation

SEVERITIES = ("HARD_ERROR", "SOFT_WARNING", "NEEDS_RULING", "INFO")

# Sec.5.1's foul-type vocabulary and its standard NFHS bookkeeping
# consequence -- a rulebook fact (which totals a KNOWN foul type
# contributes to), not a judgment about whether the foul happened. All of
# these count toward the player's personal-foul total; "technical" is the
# one type governed by the ruleset's own technical_counts_toward_personal
# flag instead of being unconditional (see _personal_counts()). NFHS:
# technical fouls do NOT count toward the team-foul/bonus total (Sec.3.2);
# every other type does.
_FOUL_TYPES: tuple[str, ...] = (
    "personal", "shooting", "offensive", "loose_ball",
    "technical", "flagrant_1", "flagrant_2", "intentional",
)
_COUNTS_TOWARD_TEAM_FOULS: frozenset[str] = frozenset(_FOUL_TYPES) - {"technical"}


@dataclass(frozen=True)
class HoopsResult:
    code: str
    state: dict[str, Any]
    data: dict[str, Any]

    @property
    def ok(self) -> bool:
        return self.code == "OK"


@dataclass(frozen=True)
class ValidationMessage:
    severity: str
    code: str
    message: str


class HoopsRulesService:
    # --- ruleset access ----------------------------------------------------

    @classmethod
    def _sport(cls, state: Mapping[str, Any]) -> str:
        return str(state.get("sport", "basketball") or "basketball").lower()

    @classmethod
    def active_ruleset(cls, state: Mapping[str, Any]) -> Mapping[str, Any]:
        return ruleset_service.active_ruleset(state, sport=cls._sport(state))

    # --- validation (Sec.3.1's validator severity examples) -----------------

    @classmethod
    def validate_on_floor(cls, hoops: Mapping[str, Any], team: str, player_ids: list[str]) -> list[ValidationMessage]:
        # "6 players on the floor with the clock running" (HARD_ERROR).
        if len(player_ids) > 5 and bool(hoops.get("clock_running")):
            return [ValidationMessage(
                "HARD_ERROR", "SIX_PLAYERS_ON_FLOOR",
                f"{team} would have {len(player_ids)} players on the floor while the clock is running; at most 5.",
            )]
        return []

    @classmethod
    def validate_timeout(cls, hoops: Mapping[str, Any], team: str) -> list[ValidationMessage]:
        # "negative timeouts" (HARD_ERROR).
        remaining = int(hoops.get(f"{team}_timeouts", 0))
        if remaining <= 0:
            return [ValidationMessage(
                "HARD_ERROR", "NEGATIVE_TIMEOUTS",
                f"{team} has no timeouts remaining.",
            )]
        return []

    @classmethod
    def validate_foul(cls, hoops: Mapping[str, Any], team: str, bonus_rule: Mapping[str, Any]) -> list[ValidationMessage]:
        # "a 6th team foul in a period with bonus == NONE -- profile
        # mismatch" (SOFT_WARNING): `team` is the team ABOUT TO BE
        # CHARGED with a foul -- its opponent should already be in the
        # bonus (DOUBLE) once `team` reaches the threshold, since a
        # team's fouls send its OPPONENT to the line, not itself. If the
        # opponent's bonus is still NONE despite `team` already being at
        # or past the threshold, either the ruleset's threshold is
        # unusual, or something upstream didn't recompute bonus when it
        # should have -- surfaced as a warning, not blocked.
        current = int(hoops.get(f"{team}_team_fouls", 0))
        threshold = int(bonus_rule.get("threshold", 5)) if bonus_rule.get("type") == "TWO_SHOT_ON_FIFTH_FOUL" else None
        opponent = "visitor" if team == "home" else "home"
        if threshold is not None and current + 1 > threshold and hoops.get(f"{opponent}_bonus") == "NONE":
            return [ValidationMessage(
                "SOFT_WARNING", "BONUS_NOT_REFLECTED",
                f"{team} is about to record team foul #{current + 1} (bonus threshold {threshold}) "
                f"but {opponent}'s bonus is still NONE -- profile mismatch, recorded as-is.",
            )]
        return []

    @classmethod
    def has_hard_error(cls, messages: list[ValidationMessage]) -> bool:
        return any(message.severity == "HARD_ERROR" for message in messages)

    # --- free-throw proposal (Sec.5.1: "engine proposes... operator confirms") --

    @classmethod
    def propose_free_throw_count(
        cls,
        foul_type: str,
        *,
        is_shooting_foul: bool = False,
        shot_points: int = 2,
        and_one: bool = False,
        bonus_state: str = "NONE",
        ruleset: Mapping[str, Any] | None = None,
    ) -> int:
        """A proposed count only -- see module docstring. Covers the
        NFHS-standard cases the scoping doc confirms as plain structural
        fact: a technical foul awards ruleset.technical.shots_awarded (2);
        a shooting foul on a missed shot awards shots equal to the shot's
        own point value (2 or 3); a made-basket-plus-foul ("and-one")
        awards exactly 1; flagrant/intentional fouls award 2 (Sec.4.3, not
        yet MHSAA-confirmed but the current NFHS baseline); a non-shooting
        foul awards free throws only once the fouled team is in the
        bonus -- 2 for DOUBLE, 1 for ONE_AND_ONE (the ONE_AND_ONE case
        proposes only the FIRST attempt; whether a second is shot is
        conditional on the first result, which this pure function has no
        way to know -- the caller records the second attempt, if any, as
        its own free_throw() call), 0 for NONE (no free throws at all)."""
        ruleset = ruleset or {}
        if foul_type == "technical":
            return int(ruleset.get("technical", {}).get("shots_awarded", 2))
        if foul_type in ("flagrant_1", "flagrant_2", "intentional"):
            return 2
        if is_shooting_foul:
            return 1 if and_one else int(shot_points)
        if bonus_state == "DOUBLE":
            return 2
        if bonus_state == "ONE_AND_ONE":
            return 1
        return 0

    # --- orchestration -------------------------------------------------------

    @classmethod
    def _after_play(cls, state: dict[str, Any]) -> dict[str, Any]:
        """Common tail for every play/foul/free-throw. Unlike baseball's
        at_bat_rules_service._after_play() (which closes the half-inning
        FIRST, then evaluates game-end candidacy using the already-
        advanced inning/half), basketball evaluates game-end candidacy
        BEFORE attempting to close the period: once the clock reaches 0 in
        the final regulation period (or an OT period) with a decided
        score, there IS no well-defined next period to transition to --
        hoops_period_service.close_period() deliberately raises rather
        than guess at one (see its own _next_period_label() comments). So
        a decided-score period-end proposes a GAME_END_CANDIDATE and
        leaves the period open (awaiting confirm_game_end()); anything
        else that reaches 0 (mid-game, or tied heading into overtime)
        closes the period/advances to OT as usual."""
        ruleset = cls.active_ruleset(state)
        period_result = None
        candidate = None
        if HoopsPeriodService.period_is_over(state):
            candidate = cls.evaluate_game_end(state, ruleset)
            if candidate is None:
                period_result = HoopsPeriodService.close_period(state, ruleset)
        hoops = state.setdefault("hoops", {})
        hoops["game_end_candidate"] = candidate
        return {
            "period_closed": bool(period_result and period_result.ok),
            "period_event": period_result.data.get("event") if period_result and period_result.ok else None,
            "game_end_candidate": candidate,
        }

    @classmethod
    def shot(cls, state: dict[str, Any], payload: Mapping[str, Any]) -> HoopsResult:
        """payload: {team, made, points (2|3), shooterId?, assistId?, andOne?}."""
        hoops = state.setdefault("hoops", {})
        HoopsStateFoundation.apply_shot(state, hoops, payload)
        event = HoopsStateFoundation.append_event(hoops, "SHOT", payload)
        tail = cls._after_play(state)
        return HoopsResult("OK", state, {"event": event, **tail})

    @classmethod
    def free_throw(cls, state: dict[str, Any], payload: Mapping[str, Any]) -> HoopsResult:
        """payload: {team, made, shooterId?, attemptNumber?, ofAttempts?}."""
        hoops = state.setdefault("hoops", {})
        HoopsStateFoundation.apply_free_throw(state, hoops, payload)
        event = HoopsStateFoundation.append_event(hoops, "FREE_THROW", payload)
        tail = cls._after_play(state)
        return HoopsResult("OK", state, {"event": event, **tail})

    @classmethod
    def rebound(cls, state: dict[str, Any], payload: Mapping[str, Any]) -> HoopsResult:
        """payload: {team, playerId?, kind}."""
        hoops = state.setdefault("hoops", {})
        HoopsStateFoundation.apply_rebound(state, hoops, payload)
        event = HoopsStateFoundation.append_event(hoops, "REBOUND", payload)
        return HoopsResult("OK", state, {"event": event})

    @classmethod
    def turnover(cls, state: dict[str, Any], payload: Mapping[str, Any]) -> HoopsResult:
        """payload: {team, playerId?}."""
        hoops = state.setdefault("hoops", {})
        HoopsStateFoundation.apply_turnover(state, hoops, payload)
        event = HoopsStateFoundation.append_event(hoops, "TURNOVER", payload)
        return HoopsResult("OK", state, {"event": event})

    @classmethod
    def held_ball(cls, state: dict[str, Any], payload: Mapping[str, Any]) -> HoopsResult:
        """Sec.5.1 'Held ball / jump situation' -> flips possession_arrow."""
        hoops = state.setdefault("hoops", {})
        HoopsStateFoundation.apply_held_ball(state, hoops, payload)
        event = HoopsStateFoundation.append_event(hoops, "HELD_BALL", payload)
        return HoopsResult("OK", state, {"event": event, "possession_arrow": hoops.get("possession_arrow")})

    @classmethod
    def foul(cls, state: dict[str, Any], payload: Mapping[str, Any]) -> HoopsResult:
        """payload: {team, playerId?, foulType}. Computes
        countsTowardTeam/countsTowardPersonal from foulType + the active
        ruleset (never guessed -- see _COUNTS_TOWARD_TEAM_FOULS and the
        ruleset's own technical_counts_toward_personal flag), applies via
        hoops_state_service.apply_foul() (bonus + foul-out are derived
        there, not here), and returns a PROPOSED free-throw count
        (propose_free_throw_count()) as INFO for the caller to act on --
        this method never records a free throw itself."""
        foul_type = str(payload.get("foulType", ""))
        if foul_type not in _FOUL_TYPES:
            raise ValueError(f"unknown foulType: {foul_type!r}")
        team = str(payload.get("team", ""))
        ruleset = cls.active_ruleset(state)
        hoops = state.setdefault("hoops", {})

        messages = cls.validate_foul(hoops, team, ruleset.get("fouls", {}).get("bonus_rule", {})) if team else []

        counts_toward_team = foul_type in _COUNTS_TOWARD_TEAM_FOULS
        technical_counts_toward_personal = bool(ruleset.get("fouls", {}).get("technical_counts_toward_personal"))
        counts_toward_personal = foul_type != "technical" or technical_counts_toward_personal

        applied_payload = dict(payload)
        applied_payload["countsTowardTeam"] = counts_toward_team
        applied_payload["countsTowardPersonal"] = counts_toward_personal
        if counts_toward_team:
            applied_payload["bonusRule"] = dict(ruleset.get("fouls", {}).get("bonus_rule", {}))
        if counts_toward_personal:
            applied_payload["foulOutThreshold"] = int(ruleset.get("fouls", {}).get("personal_foul_disqualification", 5))

        HoopsStateFoundation.apply_foul(state, hoops, applied_payload)
        event = HoopsStateFoundation.append_event(hoops, "FOUL", applied_payload)

        # Free throws for a non-shooting foul go to the FOULED team, based
        # on ITS bonus status (which reflects the fouling team's -- `team`
        # here -- own foul count; see apply_foul()'s bonus comment).
        opponent_bonus = str(hoops.get(f"{HoopsStateFoundation.opposite(team)}_bonus", "NONE")) if team in ("home", "visitor") else "NONE"
        proposed_free_throws = cls.propose_free_throw_count(
            foul_type,
            is_shooting_foul=bool(payload.get("isShootingFoul")),
            shot_points=int(payload.get("shotPoints", 2)),
            and_one=bool(payload.get("andOne")),
            bonus_state=opponent_bonus,
            ruleset=ruleset,
        )

        tail = cls._after_play(state)
        player_id = str(payload.get("playerId", ""))
        fouled_out = player_id in hoops.get("disqualified", [])
        return HoopsResult(
            "OK", state,
            {"messages": messages, "event": event, "free_throws_proposed": proposed_free_throws,
             "fouled_out": fouled_out, **tail},
        )

    # --- game end (mirrors game_end_evaluator.GameEndEvaluator) --------------

    @classmethod
    def evaluate_game_end(cls, state: Mapping[str, Any], ruleset: Mapping[str, Any] | None = None) -> dict[str, Any] | None:
        """Sec.11-equivalent for basketball: a candidate only once the
        clock has reached 0 in the last regulation period (or any OT
        period) AND the score is not tied. Pure read -- never mutates
        state, never finalizes the game (Sec.11.2's baseball precedent:
        'the scorer/umpire can confirm official termination' is a
        separate, explicit call -- confirm_game_end() below)."""
        ruleset = ruleset if ruleset is not None else cls.active_ruleset(state)
        if int(state.get("clock_seconds", 0)) > 0:
            return None
        period = str(state.get("period", ""))
        labels = HoopsPeriodService.regulation_labels(ruleset)
        is_last_regulation = period == labels[-1]
        is_overtime = period == "OT" or (period.startswith("OT") and period[2:].isdigit())
        if not is_last_regulation and not is_overtime:
            return None
        home = int(state.get("home_score", 0))
        visitor = int(state.get("visitor_score", 0))
        if home == visitor:
            return None  # tied -- goes to (another) overtime, never a candidate
        return {"reason": "REGULATION" if is_last_regulation else "OVERTIME", "period": period}

    @classmethod
    def confirm_game_end(cls, state: dict[str, Any], reason: str) -> HoopsResult:
        """Sec.11.2 equivalent: an explicit, separate operator action --
        a GAME_END_CANDIDATE never finalizes a game on its own."""
        hoops = state.setdefault("hoops", {})
        hoops["official_end_reason"] = reason
        state["status"] = "completed"
        return HoopsResult("OK", state, {"official_end_reason": reason})
