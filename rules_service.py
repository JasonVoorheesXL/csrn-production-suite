from __future__ import annotations

import copy
import re
import time
import threading
from time import perf_counter
from dataclasses import dataclass
from typing import Any, Callable, Mapping

import ruleset_service
from canonical_state_service import CanonicalStateFoundation
from eligibility_service import EligibilityService
from runtime_diagnostics_service import get_runtime_diagnostics
from live_command_service import (
    assign_next_revision,
    attach_metadata,
    command_result_state,
    command_id_from,
    command_metadata,
    duplicate_result,
    remember_command,
)


@dataclass(frozen=True)
class RulesResult:
    code: str
    data: dict[str, Any]

    @property
    def ok(self) -> bool:
        return self.code == "OK"


class RulesService:
    """Football rules-engine boundary independent of Flask and persistence details."""

    VALID_TEAMS = {"home", "visitor"}
    VALID_DIRECTIONS = {"left", "right"}
    # Frozen fallback + golden anchor. The live set is _valid_play_types(),
    # which the ruleset can widen (Canadian "field_goal"); NFHS never does.
    VALID_PLAY_TYPES = {"run", "pass", "kickoff", "punt"}
    SNAPSHOT_FIELDS = (
        "home_score",
        "visitor_score",
        "possession",
        "down",
        "distance",
        "ball_spot",
        "quarter",
        "clock_seconds",
        "clock_running",
        "clock_visible",
        "clock_started_at",
        "home_direction",
        "visitor_direction",
        "broadcast_phase",
        "special_game_phase",
        "kicking_team",
        "receiving_team",
        "player_graphic",
    )

    def __init__(
        self,
        *,
        load_state: Callable[[], Mapping[str, Any]],
        save_state: Callable[[Mapping[str, Any]], Any],
        push_history: Callable[[dict[str, Any]], None],
        source_allowed: Callable[[dict[str, Any], str], bool],
        locked_payload: Callable[[dict[str, Any]], Mapping[str, Any]],
        resolve_player: Callable[[dict[str, Any], str, Any], Mapping[str, Any]],
        show_player_graphic: Callable[..., Any],
        transaction_lock: Any,
        now: Callable[[], float] = time.time,
    ) -> None:
        self._load_state = load_state
        self._save_state = save_state
        self._push_history = push_history
        self._source_allowed = source_allowed
        self._locked_payload = locked_payload
        self._resolve_player = resolve_player
        self._show_player_graphic = show_player_graphic
        self._transaction_lock = transaction_lock
        self._now = now

    # Field geometry, from the football ruleset (US/MS/MHSAA). length_yards
    # is the goal-line-to-goal-line coordinate span (100 NFHS / 110
    # Canadian). The literal is the frozen fallback + golden anchor.
    _FIELD_GEOMETRY_FALLBACK = {
        "length_yards": 100,
        "end_zone_depth_yards": 10,
        "red_zone_yards": 20,
    }
    # Every derived value below is resolved from ruleset_service.active_
    # ruleset() (the game's jurisdiction, generic US base when absent --
    # identical engine values to us-ms-mhsaa, so a no-op today) and cached
    # keyed by the resolved ruleset id. The *_FALLBACK literals are the
    # frozen anchor used only if the ruleset engine raises.
    _field_geometry_cache: dict[str, dict[str, int]] = {}

    @classmethod
    def _field_geometry(cls, state: Mapping[str, Any] | None = None) -> dict[str, int]:
        rid = ruleset_service.active_ruleset_id(state)
        if rid not in cls._field_geometry_cache:
            try:
                cls._field_geometry_cache[rid] = (
                    ruleset_service.field_geometry(ruleset_service.active_ruleset(state))
                    or dict(cls._FIELD_GEOMETRY_FALLBACK)
                )
            except Exception:
                cls._field_geometry_cache[rid] = dict(cls._FIELD_GEOMETRY_FALLBACK)
        return cls._field_geometry_cache[rid]

    @classmethod
    def _field_length(cls, state: Mapping[str, Any] | None = None) -> int:
        return int(cls._field_geometry(state).get("length_yards", 100) or 100)

    # Point values + accepted play types, from the same football ruleset.
    # The literals are the frozen fallback + golden anchor.
    _SCORING_FALLBACK = {
        "touchdown": 6,
        "field_goal": 3,
        "safety": 2,
        "convert_kick": 1,
        "convert_major": 2,
        "single": 1,
    }
    _scoring_cache: dict[str, dict[str, int]] = {}
    _valid_play_types_cache: dict[str, set[str]] = {}
    _no_fair_catch_cache: dict[str, bool] = {}

    @classmethod
    def _scoring(cls, state: Mapping[str, Any] | None = None) -> dict[str, int]:
        rid = ruleset_service.active_ruleset_id(state)
        if rid not in cls._scoring_cache:
            try:
                cls._scoring_cache[rid] = (
                    ruleset_service.scoring_values(ruleset_service.active_ruleset(state))
                    or dict(cls._SCORING_FALLBACK)
                )
            except Exception:
                cls._scoring_cache[rid] = dict(cls._SCORING_FALLBACK)
        return cls._scoring_cache[rid]

    @classmethod
    def _valid_play_types(cls, state: Mapping[str, Any] | None = None) -> set[str]:
        rid = ruleset_service.active_ruleset_id(state)
        if rid not in cls._valid_play_types_cache:
            try:
                cls._valid_play_types_cache[rid] = (
                    ruleset_service.valid_play_types(ruleset_service.active_ruleset(state))
                    or set(cls.VALID_PLAY_TYPES)
                )
            except Exception:
                cls._valid_play_types_cache[rid] = set(cls.VALID_PLAY_TYPES)
        return cls._valid_play_types_cache[rid]

    @classmethod
    def _no_fair_catch(cls, state: Mapping[str, Any] | None = None) -> bool:
        rid = ruleset_service.active_ruleset_id(state)
        if rid not in cls._no_fair_catch_cache:
            try:
                cls._no_fair_catch_cache[rid] = ruleset_service.no_fair_catch(
                    ruleset_service.active_ruleset(state)
                )
            except Exception:
                cls._no_fair_catch_cache[rid] = False
        return cls._no_fair_catch_cache[rid]

    @classmethod
    def spot_to_coord(cls, value: Any, state: Mapping[str, Any] | None = None) -> int:
        """Canonical field coordinate: 0=left goal line, length=right goal
        line (length is the ruleset field length, 100 NFHS / 110 Canadian)."""
        length = cls._field_length(state)
        mid = length // 2
        text = str(value or "").strip().lower()
        if text in {"left goal", "left_goal", "home goal", "home_goal", "0"}:
            return 0
        if text in {
            "right goal",
            "right_goal",
            "visitor goal",
            "visitor_goal",
            str(length),
        }:
            return length
        if text == str(mid):
            return mid
        match = re.match(r"^(left|right|home|visitor)\s*(\d{1,3})$", text)
        if match:
            side = match.group(1)
            yard = max(0, min(mid - 1, int(match.group(2))))
            return yard if side in {"left", "home"} else length - yard
        try:
            return max(0, min(length, int(float(text))))
        except (TypeError, ValueError):
            return mid

    @classmethod
    def coord_to_spot(cls, coord: Any, state: Mapping[str, Any] | None = None) -> str:
        length = cls._field_length(state)
        mid = length // 2
        try:
            normalized = max(0, min(length, int(coord)))
        except (TypeError, ValueError):
            normalized = mid
        if normalized == 0:
            return "LEFT GOAL"
        if normalized == length:
            return "RIGHT GOAL"
        if normalized == mid:
            return str(mid)
        return (
            f"LEFT {normalized}"
            if normalized < mid
            else f"RIGHT {length - normalized}"
        )

    @staticmethod
    def team_direction(state: Mapping[str, Any], team: str) -> int:
        default = "right" if team == "home" else "left"
        direction = str(state.get(f"{team}_direction", default)).lower()
        return 1 if direction == "right" else -1

    @staticmethod
    def opposite(team: str) -> str:
        return "visitor" if team == "home" else "home"

    # The down cycle -- active ruleset, cached by id (see _field_geometry).
    # 3 downs is Canadian; every US ruleset resolves ["1st".."4th"].
    _DOWNS_SEQUENCE_FALLBACK = ["1st", "2nd", "3rd", "4th"]
    _downs_sequence_cache: dict[str, list[str]] = {}

    @classmethod
    def _downs_sequence(cls, state: Mapping[str, Any] | None = None) -> list[str]:
        rid = ruleset_service.active_ruleset_id(state)
        if rid not in cls._downs_sequence_cache:
            try:
                cls._downs_sequence_cache[rid] = (
                    ruleset_service.downs_sequence(ruleset_service.active_ruleset(state))
                    or list(cls._DOWNS_SEQUENCE_FALLBACK)
                )
            except Exception:
                cls._downs_sequence_cache[rid] = list(cls._DOWNS_SEQUENCE_FALLBACK)
        return cls._downs_sequence_cache[rid]

    @classmethod
    def advance_down(cls, down: Any, state: Mapping[str, Any] | None = None) -> str:
        # wrap=False keeps the last down where it is (no phantom fresh series
        # on a failed final down); the caller applies turnover-on-downs.
        return ruleset_service.next_down(
            str(down), cls._downs_sequence(state), wrap=False
        )

    @staticmethod
    def _bounded_int(
        value: Any,
        fallback: int,
        minimum: int = 0,
        maximum: int = 3599,
    ) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = fallback
        return max(minimum, min(maximum, parsed))

    def clock_control(self, payload: Mapping[str, Any] | None) -> RulesResult:
        incoming = dict(payload or {})
        command_id = command_id_from(incoming)
        with self._transaction_lock:
            state = copy.deepcopy(dict(self._load_state()))
            duplicate = duplicate_result(state, command_id)
            if duplicate is not None:
                return RulesResult("OK", duplicate)
            action = str(incoming.get("action", "")).lower()
            seconds = self._bounded_int(state.get("clock_seconds", 720), 720)

            if action == "start":
                state["clock_running"] = True
                state["clock_started_at"] = int(self._now())
            elif action == "stop":
                state["clock_running"] = False
                state["clock_started_at"] = 0
            elif action == "set":
                seconds = self._bounded_int(incoming.get("seconds"), seconds)
            elif action == "adjust":
                delta = self._bounded_int(
                    incoming.get("delta"),
                    0,
                    minimum=-3599,
                    maximum=3599,
                )
                seconds = self._bounded_int(seconds + delta, seconds)
            elif action == "reset":
                reset_value = incoming.get("seconds", 720) or 720
                seconds = self._bounded_int(reset_value, 720)
                state["clock_running"] = False
                state["clock_started_at"] = 0

            state["clock_seconds"] = seconds
            if "visible" in incoming:
                state["clock_visible"] = bool(incoming.get("visible"))
            revision = assign_next_revision(state)
            metadata = command_metadata(
                incoming,
                action=f"clock_control:{action or 'noop'}",
                state_revision=revision,
            )
            result_data = attach_metadata({"state": copy.deepcopy(state)}, metadata)
            remember_command(state, command_id, metadata=metadata, result=result_data)
            self._save_state(state)
            return RulesResult("OK", result_data)

    def field_direction(self, payload: Mapping[str, Any] | None) -> RulesResult:
        incoming = dict(payload or {})
        command_id = command_id_from(incoming)
        team = str(incoming.get("team") or "home").lower()
        direction = str(
            incoming.get("direction")
            or incoming.get("home_direction")
            or "right"
        ).lower()
        if team not in self.VALID_TEAMS or direction not in self.VALID_DIRECTIONS:
            return RulesResult("INVALID_DIRECTION", {})

        with self._transaction_lock:
            state = copy.deepcopy(dict(self._load_state()))
            duplicate = duplicate_result(state, command_id)
            if duplicate is not None:
                return RulesResult("OK", duplicate)
            state[f"{team}_direction"] = direction
            state[f"{self.opposite(team)}_direction"] = (
                "left" if direction == "right" else "right"
            )
            revision = assign_next_revision(state)
            metadata = command_metadata(
                incoming,
                action="field_direction",
                state_revision=revision,
            )
            result_data = attach_metadata({"state": copy.deepcopy(state)}, metadata)
            remember_command(state, command_id, metadata=metadata, result=result_data)
            self._save_state(state)
            return RulesResult("OK", result_data)

    def play(self, payload: Mapping[str, Any] | None) -> RulesResult:
        incoming = dict(payload or {})
        team = str(incoming.get("team", "")).lower()
        kind = str(incoming.get("play_type", "")).lower()
        if team not in self.VALID_TEAMS or kind not in self._valid_play_types():
            return RulesResult("INVALID_PLAY", {})

        lock_started = perf_counter()
        self._transaction_lock.acquire()
        lock_wait_ms = round((perf_counter() - lock_started) * 1000, 2)
        command_id_for_log = command_id_from(incoming)
        get_runtime_diagnostics().record(
            "SERVER_RULES_LOCK",
            command_id=command_id_for_log,
            client_id=str(incoming.get("client_id", "") or ""),
            wait_ms=lock_wait_ms,
            contended=lock_wait_ms > 25,
            thread=threading.current_thread().name,
        )
        try:
            state = copy.deepcopy(dict(self._load_state()))
            phase = str(state.get("special_game_phase", "") or "").lower()
            kicking_team = str(state.get("kicking_team", "") or "").lower()
            if phase == "pending_try":
                return RulesResult("SPECIAL_PHASE_REQUIRES_RESOLUTION", {"phase": phase})
            if phase == "kickoff" and (kind != "kickoff" or (kicking_team and team != kicking_team)):
                return RulesResult("SPECIAL_PHASE_REQUIRES_KICKOFF", {"phase": phase, "kicking_team": kicking_team})
            if phase == "free_kick" and (kind not in {"kickoff", "punt"} or (kicking_team and team != kicking_team)):
                return RulesResult("SPECIAL_PHASE_REQUIRES_FREE_KICK", {"phase": phase, "kicking_team": kicking_team})
            if not str(state.get("broadcast_id", "")).strip():
                return RulesResult("NO_ACTIVE_BROADCAST", {})
            command_id = command_id_from(incoming)
            duplicate = duplicate_result(state, command_id)
            if duplicate is not None:
                return RulesResult("OK", duplicate)
            if not self._source_allowed(state, "statistician"):
                return RulesResult(
                    "CONTROL_SOURCE_LOCKED",
                    copy.deepcopy(dict(self._locked_payload(state))),
                )

            roles = CanonicalStateFoundation.team_roles(state)
            if kind in {"run", "pass"} and team != roles.offense:
                return RulesResult(
                    "TEAM_ROLE_MISMATCH",
                    {
                        "message": "Offensive plays must be entered for the team in possession.",
                        "submitted_team": team,
                        "offense": roles.offense,
                        "defense": roles.defense,
                    },
                )

            outcome = str(incoming.get("pass_outcome", "") or "").lower()
            kneel = bool(incoming.get("kneel"))


            ledger = state.pop("recent_commands", None)
            self._push_history(state)
            if isinstance(state.get("history"), list):
                state["history"] = state["history"][-50:]
            if ledger is not None:
                state["recent_commands"] = ledger
            before = {
                field: copy.deepcopy(state.get(field))
                for field in self.SNAPSHOT_FIELDS
            }
            length = self._field_length(state)
            td_points = self._scoring(state).get("touchdown", 6)
            safety_points = self._scoring(state).get("safety", 2)
            start = self.spot_to_coord(
                incoming.get("start_spot") or state.get("ball_spot") or (length // 2), state)
            end_value = incoming.get("end_spot")
            end = self.spot_to_coord(
                end_value if end_value not in (None, "") else start, state)
            direction = self.team_direction(state, team)
            yards = (end - start) * direction
            old_down = str(state.get("down", "1st"))
            old_distance = str(state.get("distance", "10"))
            try:
                distance = (
                    10
                    if old_distance in {"Off", "Goal", ""}
                    else max(1, int(old_distance))
                )
            except ValueError:
                distance = 10

            outcome = str(incoming.get("pass_outcome", "")).lower()
            turnover = bool(incoming.get("fumble_lost")) or outcome == "interception"
            turnover_type = (
                "interception" if outcome == "interception"
                else "fumble_recovery" if bool(incoming.get("fumble_lost"))
                else ""
            )
            turnover_team = self.opposite(team) if turnover else ""
            turnover_spot = end
            return_end = end
            turnover_return_yards = 0
            turnover_touchdown = False
            if turnover:
                spot_value = (
                    incoming.get("turnover_spot")
                    or incoming.get("interception_spot")
                    or incoming.get("recovery_spot")
                    or self.coord_to_spot(end, state)
                )
                turnover_spot = self.spot_to_coord(spot_value, state)
                return_value = incoming.get("return_end_spot")
                return_end = self.spot_to_coord(
                    return_value if return_value not in (None, "") else self.coord_to_spot(turnover_spot, state), state)
                gaining_direction = self.team_direction(state, turnover_team)
                turnover_return_yards = max(0, (return_end - turnover_spot) * gaining_direction)
                turnover_touchdown = (
                    (gaining_direction == 1 and return_end == length)
                    or (gaining_direction == -1 and return_end == 0)
                )
                yards = 0 if outcome == "interception" else (turnover_spot - start) * direction
                end = return_end
            touchdown = (not turnover) and ((direction == 1 and end == length) or (
                direction == -1 and end == 0
            ))
            safety = (direction == 1 and end == 0) or (
                direction == -1 and end == length
            )
            first_down = False
            label = kind.title()
            description = ""

            numbers = {
                role: str(incoming.get(f"{role}_number", "")).strip()
                for role in (
                    "player",
                    "passer",
                    "receiver",
                    "sacker",
                    "kicker",
                    "returner",
                    "recoverer",
                )
            }
            # Own-team fumble recovery: the carrier fumbles and a *teammate*
            # recovers (no turnover). Possession and the ball never change
            # hands, but credit for the yardage from the recovery spot on -- and
            # any touchdown -- belongs to the recoverer, not the original
            # carrier. Only meaningful on a live run/pass that ended in a
            # normal result; a lost fumble already has its own returner fields.
            handler_number = numbers["receiver"] if kind == "pass" else numbers["player"]
            own_recovery = bool(
                kind in {"run", "pass"}
                and bool(incoming.get("fumble"))
                and not bool(incoming.get("fumble_lost"))
                and outcome not in {"incomplete", "spike", "interception"}
                and numbers["recoverer"]
                and numbers["recoverer"] != handler_number
            )
            refs = {
                "player": self._resolve(state, team, numbers["player"]),
                "passer": self._resolve(state, team, numbers["passer"]),
                "receiver": self._resolve(state, team, numbers["receiver"]),
                "sacker": self._resolve(
                    state,
                    self.opposite(team),
                    numbers["sacker"],
                ),
                "kicker": self._resolve(state, team, numbers["kicker"]),
                "returner": self._resolve(
                    state,
                    self.opposite(team),
                    numbers["returner"],
                ),
                "recoverer": self._resolve(state, team, numbers["recoverer"]),
            }
            # Server-side player/team validation is authoritative. A jersey sent
            # for an offensive/defensive role must resolve on the canonical team
            # for that role; browser filtering alone is never trusted.
            required_roles = []
            if kind == "run" and numbers["player"]:
                required_roles.append("player")
            if kind == "pass":
                if numbers["passer"]:
                    required_roles.append("passer")
                if numbers["receiver"]:
                    required_roles.append("receiver")
                if outcome == "sack" and numbers["sacker"]:
                    required_roles.append("sacker")
            if own_recovery:
                required_roles.append("recoverer")
            for role in required_roles:
                permitted_team = roles.defense if role == "sacker" else roles.offense
                ref = refs[role]
                if not EligibilityService.is_eligible(
                    state,
                    permitted_team,
                    player_id=ref.get("player_id", ""),
                    number=ref.get("number") or numbers[role],
                    name=ref.get("name", ""),
                    resolve_player=self._resolve_player,
                ):
                    return RulesResult(
                        "PLAYER_INELIGIBLE",
                        {
                            "message": f"Player #{numbers[role]} is unavailable because of a recorded ejection.",
                            "role": role,
                            "number": numbers[role],
                            "team": permitted_team,
                        },
                    )
                if ref.get("resolved"):
                    continue
                other_team = roles.offense if role == "sacker" else roles.defense
                # Preserve the established unresolved-jersey workflow: an unknown
                # number may still be recorded and surfaced as unresolved. Reject
                # only when the same submitted jersey definitively resolves on the
                # non-permitted team.
                wrong_team_ref = self._resolve(state, other_team, numbers[role])
                if wrong_team_ref.get("resolved"):
                    return RulesResult(
                        "PLAYER_TEAM_MISMATCH",
                        {
                            "message": f"Player #{numbers[role]} is not eligible for the requested {role} role.",
                            "role": role,
                            "number": numbers[role],
                            "permitted_team": permitted_team,
                            "resolved_team": other_team,
                        },
                    )
            names = {
                role: str(refs[role].get("name", "") or incoming.get(f"{role}_name", "")).strip()
                for role in refs
            }

            landing = end
            kick_distance = 0
            return_yards = 0
            muffed_punt = False
            muff_recovered_by_kicking_team = False

            if kind == "run":
                kneel = bool(incoming.get("kneel"))
                label = "Kneel" if kneel else "Run"
                runner = self._display(numbers["player"], names["player"]) if numbers["player"] or names["player"] else self._team_fallback(state, team)
                description = f"{runner} {'kneel' if kneel else 'run'} for {yards} yards"
            elif kind == "pass":
                passer = self._display(numbers["passer"], names["passer"]) if numbers["passer"] or names["passer"] else self._team_fallback(state, team)
                receiver = self._display(numbers["receiver"], names["receiver"]) if numbers["receiver"] or names["receiver"] else self._team_fallback(state, team)
                if outcome in {"incomplete", "spike"}:
                    end = start
                    yards = 0
                    label = "Spike" if outcome == "spike" else "Incomplete Pass"
                    description = (
                        f"{passer} spike"
                        if outcome == "spike"
                        else (
                            f"{passer} pass incomplete, intended for {receiver}"
                            if numbers["receiver"] or names["receiver"]
                            else f"{passer} pass incomplete"
                        )
                    )
                elif outcome == "interception":
                    label = "Interception"
                    description = f"{passer} pass intercepted"
                elif outcome == "sack":
                    sacker = self._display(numbers["sacker"], names["sacker"]) if numbers["sacker"] or names["sacker"] else self._team_fallback(state, self.opposite(team))
                    label = "Sack"
                    description = f"{passer} sacked by {sacker} for {yards} yards"
                else:
                    label = "Pass"
                    if numbers["passer"] or names["passer"]:
                        description = (
                            f"{passer} complete to {receiver} for {yards} yards"
                            if numbers["receiver"] or names["receiver"]
                            else f"{passer} completes a pass for {yards} yards"
                        )
                    else:
                        team_name = self._team_fallback(state, team)
                        description = (
                            f"{team_name} complete a pass to {receiver} for {yards} yards"
                            if numbers["receiver"] or names["receiver"]
                            else f"{team_name} complete a pass for {yards} yards"
                        )
            elif kind == "kickoff" and bool(incoming.get("kick_out_of_bounds")):
                # A free kick that goes out of bounds between the goal lines
                # untouched by the receiving team is a foul on the kicking
                # team (NFHS "Free Kick Out-of-Bounds"; confirmed against the
                # SDHSAA/Demetriou NFHS-NCAA rules-differences summary, docs/
                # VIEWER_FEEDBACK_20260926.md item 4). This is a kickoff-only
                # infraction -- a scrimmage-kick punt going out of bounds is
                # ordinary and already handled by the return branch below --
                # so it is deliberately its own sibling branch, not folded
                # into the shared kickoff/punt return logic. R gets to choose
                # the enforcement, same as the operator UI already asks for a
                # receiving-team choice on the other special-enforcement fouls
                # (e.g. second-half kickoff direction).
                receiving = self.opposite(team)
                landing_value = incoming.get("landing_spot")
                if landing_value in (None, ""):
                    return RulesResult(
                        "OUT_OF_BOUNDS_SPOT_REQUIRED",
                        {"message": "Enter the spot where the kickoff went out of bounds."},
                    )
                landing = self.spot_to_coord(landing_value, state)
                oob_choice = str(incoming.get("out_of_bounds_choice", "") or "").lower()
                if oob_choice not in {"25_yard_line", "rekick", "spot_plus_5"}:
                    return RulesResult(
                        "OUT_OF_BOUNDS_CHOICE_REQUIRED",
                        {
                            "message": "Select how the receiving team wants the kickoff out-of-bounds foul enforced.",
                            "choices": ["25_yard_line", "rekick", "spot_plus_5"],
                        },
                    )
                kick_distance = abs(landing - start)
                return_yards = 0
                muffed_punt = False
                muff_recovered_by_kicking_team = False
                if oob_choice == "rekick":
                    # Team K re-kicks 5 yards behind the previous spot; the ball never changes hands.
                    end = max(0, min(length, start - 5 * direction))
                    state["possession"] = team
                    state["kicking_team"] = team
                    state["special_game_phase"] = "kickoff"
                    state["ball_spot"] = self.coord_to_spot(end, state)
                    label = "Kickoff Out of Bounds"
                    description = (
                        f"Kickoff by #{numbers['kicker'] or '?'} out of bounds at "
                        f"{self.coord_to_spot(landing, state)} — {self._team_fallback(state, receiving)} "
                        f"choose a re-kick, 5-yard penalty from {self.coord_to_spot(start, state)}"
                    )
                else:
                    if oob_choice == "25_yard_line":
                        end = max(0, min(length, start + 25 * direction))
                        enforcement_note = f"{self._team_fallback(state, receiving)} take the ball 25 yards from the previous spot"
                    else:  # spot_plus_5
                        end = max(0, min(length, landing + 5 * direction))
                        enforcement_note = (
                            f"{self._team_fallback(state, receiving)} take the ball at "
                            f"{self.coord_to_spot(landing, state)} plus a 5-yard penalty"
                        )
                    state["possession"] = receiving
                    CanonicalStateFoundation.clear_special_phase(state)
                    state["ball_spot"] = self.coord_to_spot(end, state)
                    state["down"] = "1st"
                    state["distance"] = "10"
                    label = "Kickoff Out of Bounds"
                    description = (
                        f"Kickoff by #{numbers['kicker'] or '?'} out of bounds at "
                        f"{self.coord_to_spot(landing, state)} — {enforcement_note}, "
                        f"ball at {self.coord_to_spot(end, state)}"
                    )
                self._stop_clock(state)
            else:
                receiving = self.opposite(team)
                state["possession"] = receiving
                CanonicalStateFoundation.clear_special_phase(state)
                landing_value = incoming.get("landing_spot")
                landing = self.spot_to_coord(
                    landing_value if landing_value not in (None, "") else end, state)
                touchback = bool(incoming.get("touchback"))
                # A ruleset with no fair catch (Canadian) ignores the signal
                # outright -- the returner must run it or concede a single.
                fair_catch = bool(incoming.get("fair_catch")) and not self._no_fair_catch(state)
                blocked = bool(incoming.get("blocked"))
                # A muffed punt is its own outcome, distinct from a generic
                # fumble: the returning team bobbles the catch, and if the
                # KICKING team recovers it, possession never actually
                # transfers to the receiving team at all -- unlike a normal
                # punt, whose possession flip a few lines above is
                # unconditional. Recorded separately (turnover_type
                # "muff_recovery") so it never reports as a plain fumble
                # recovery, and so it isn't silently double-counted as a
                # generic Fumble/Fumble-lost turnover the way it used to be
                # (that generic pair was computed earlier for every play
                # kind, punts included, and was never reset for this branch).
                muffed_punt = bool(incoming.get("muffed_punt"))
                muff_recovered_by_kicking_team = muffed_punt and bool(
                    incoming.get("fumble_lost")
                )
                turnover = muff_recovered_by_kicking_team
                turnover_type = "muff_recovery" if muff_recovered_by_kicking_team else ""
                turnover_team = team if muff_recovered_by_kicking_team else ""
                if muff_recovered_by_kicking_team:
                    state["possession"] = team
                if touchback:
                    receiving_direction = self.team_direction(state, receiving)
                    # Touchback to the receiving team's own 20; mirrored to
                    # (length - 20) when they drive the other way.
                    touchback_yard = 20
                    end = (
                        touchback_yard
                        if receiving_direction == 1
                        else length - touchback_yard
                    )
                kick_distance = abs(landing - start)
                return_direction = self.team_direction(state, receiving)
                return_yards = max(0, (end - landing) * return_direction)
                turnover_spot = end
                return_end = end
                turnover_return_yards = 0
                touchdown = bool(
                    not touchback
                    and not fair_catch
                    and not muff_recovered_by_kicking_team
                    and numbers["returner"]
                    and (
                        (return_direction == 1 and end == length)
                        or (return_direction == -1 and end == 0)
                    )
                )
                if touchdown:
                    state[f"{receiving}_score"] = (
                        int(state.get(f"{receiving}_score", 0) or 0) + td_points
                    )
                    CanonicalStateFoundation.enter_pending_try(state, receiving)
                else:
                    state["ball_spot"] = self.coord_to_spot(end, state)
                    state["down"] = "1st"
                    state["distance"] = "10"
                self._stop_clock(state)
                label = "Kickoff" if kind == "kickoff" else "Punt"
                description = (
                    f"{label} by #{numbers['kicker'] or '?'} "
                    f"landed at {self.coord_to_spot(landing, state)}"
                )
                if muffed_punt:
                    description += ", muffed by the receiving team"
                    if muff_recovered_by_kicking_team:
                        description += (
                            f", recovered by the kicking team at "
                            f"{self.coord_to_spot(end, state)}"
                        )
                    else:
                        description += (
                            f", recovered by the receiving team at "
                            f"{self.coord_to_spot(end, state)}"
                        )
                elif numbers["returner"] and not fair_catch and not touchback:
                    returner = self._display(
                        numbers["returner"],
                        names["returner"],
                    )
                    description += (
                        f", returned by {returner} for {return_yards} yards "
                        f"to {self.coord_to_spot(end, state)}"
                    )
                else:
                    description += f", ball at {self.coord_to_spot(end, state)}"
                description += (
                    " — touchback"
                    if touchback
                    else " — fair catch"
                    if fair_catch
                    else " — blocked"
                    if blocked
                    else ""
                )
                if touchdown:
                    description += ", touchdown"
                    label = (
                        "Kickoff Return Touchdown"
                        if kind == "kickoff"
                        else "Punt Return Touchdown"
                    )
                    self._show_player_spotlight(
                        state,
                        team=receiving,
                        number=numbers["returner"],
                        name=names["returner"],
                        player_ref=refs["returner"],
                        position="Returner",
                        detail=f"{return_yards}-yard {kind} return",
                    )

            recovery_yards = 0
            recovery_spot_text = ""
            if own_recovery and not turnover:
                recovery_value = incoming.get("recovery_spot")
                recovery_coord = self.spot_to_coord(
                    recovery_value if recovery_value not in (None, "") else end, state)
                # Yards gained from where the teammate recovered it to the end
                # of the play; the carrier keeps (yards - recovery_yards).
                recovery_yards = (end - recovery_coord) * direction
                recovery_spot_text = self.coord_to_spot(recovery_coord, state)
            else:
                own_recovery = False

            if kind in {"run", "pass"}:
                if turnover:
                    state["possession"] = turnover_team
                    state["down"] = "1st"
                    state["distance"] = "10"
                    if turnover_touchdown:
                        state[f"{turnover_team}_score"] = int(state.get(f"{turnover_team}_score", 0)) + td_points
                        CanonicalStateFoundation.enter_pending_try(state, turnover_team)
                        touchdown = True
                        self._show_player_spotlight(
                            state,
                            team=turnover_team,
                            number=numbers["returner"],
                            name=names["returner"],
                            player_ref=refs["returner"],
                            position="",
                            detail=(
                                f"{turnover_return_yards}-yard "
                                + (
                                    "interception"
                                    if turnover_type == "interception"
                                    else "fumble"
                                )
                                + " return"
                            ),
                        )
                    elif outcome != "sack":
                        # A plain turnover (no return touchdown) never
                        # triggered a defensive spotlight either -- only the
                        # touchdown case above did. A sack that also happens
                        # to be a fumble is credited via the SACK spotlight
                        # below instead, so the same play doesn't fire two
                        # spotlights.
                        self._show_player_spotlight(
                            state,
                            team=turnover_team,
                            number=numbers["returner"],
                            name=names["returner"],
                            player_ref=refs["returner"],
                            position="",
                            detail=description,
                            graphic_type="turnover",
                            eyebrow="TURNOVER",
                            defensive=True,
                        )
                    self._stop_clock(state)
                elif touchdown:
                    state[f"{team}_score"] = int(state.get(f"{team}_score", 0)) + td_points
                    CanonicalStateFoundation.enter_pending_try(state, team)
                    self._stop_clock(state)
                    is_pass_reception = kind == "pass" and outcome == "complete"
                    td_role = "receiver" if is_pass_reception else "player"
                    if own_recovery:
                        td_role = "recoverer"
                    td_number = numbers[td_role]
                    td_name = names[td_role]
                    self._show_player_spotlight(
                        state,
                        team=team,
                        number=td_number,
                        name=td_name,
                        player_ref=refs[td_role],
                        position="",
                        detail=(
                            f"{recovery_yards}-yard touchdown after fumble recovery"
                            if own_recovery
                            else f"{yards}-yard touchdown "
                            + ("reception" if kind == "pass" else "run")
                        ),
                        # Only a pass-reception touchdown has a separate QB to
                        # credit -- run TDs and the punt/kickoff-return and
                        # turnover-return branches (their own
                        # _show_player_spotlight() calls above) have no
                        # passer role at all.
                        passer_name=(
                            names["passer"] if is_pass_reception and not own_recovery else ""
                        ),
                    )
                elif safety:
                    other = self.opposite(team)
                    state[f"{other}_score"] = int(state.get(f"{other}_score", 0)) + safety_points
                    CanonicalStateFoundation.enter_free_kick(state, team)
                    self._stop_clock(state)
                else:
                    first_down = yards >= distance
                    if first_down:
                        state["down"] = "1st"
                        state["distance"] = "10"
                    else:
                        state["down"] = self.advance_down(old_down, state)
                        state["distance"] = str(max(1, distance - yards))
                        if ruleset_service.is_terminal_down(
                            old_down, self._downs_sequence(state)
                        ):
                            state["possession"] = self.opposite(team)
                            state["down"] = "1st"
                            state["distance"] = "10"
                            self._stop_clock(state)
                            turnover = True
                            turnover_type = "downs"
                            turnover_team = self.opposite(team)
                            turnover_spot = end
                            return_end = end
                            turnover_return_yards = 0
                    if outcome in {"incomplete", "spike"} or bool(
                        incoming.get("out_of_bounds")
                    ):
                        self._stop_clock(state)
                if not touchdown and not safety:
                    state["ball_spot"] = self.coord_to_spot(end, state)

                if kind == "pass" and outcome == "sack":
                    # A sack recorded through the statistician's play form
                    # (this method, not EventService.trigger()) never fired
                    # the spotlight at all -- confirmed against a real sack
                    # tonight (Jaraylon Washington) that correctly updated
                    # the stats-based Defensive Leader sidebar box but never
                    # showed the center spotlight card, because nothing here
                    # ever called _show_player_spotlight() for a sack.
                    self._show_player_spotlight(
                        state,
                        team=self.opposite(team),
                        number=numbers["sacker"],
                        name=names["sacker"],
                        player_ref=refs["sacker"],
                        position="",
                        detail=description,
                        graphic_type="sack",
                        eyebrow="SACK",
                        defensive=True,
                    )

            play_number = self._bounded_int(
                state.get("next_play_number", 1),
                1,
                minimum=1,
                maximum=999999,
            )
            state["next_play_number"] = play_number + 1
            token = re.sub(
                r"[^A-Za-z0-9]+",
                "-",
                str(state.get("broadcast_id") or "GAME"),
            ).strip("-") or "GAME"
            play_id = f"{token}-{play_number:04d}"
            event_id = f"evt-{int(self._now() * 1000)}-{play_number}"

            if turnover_type == "interception":
                defender = self._display(numbers["returner"], names["returner"]) if numbers["returner"] or names["returner"] else self._team_fallback(state, self.opposite(team))
                description += f" by {defender} at {self.coord_to_spot(turnover_spot, state)}"
                if turnover_return_yards:
                    description += f", returned {turnover_return_yards} yards to {self.coord_to_spot(return_end, state)}"
            if bool(incoming.get("fumble")):
                description += ", fumble" + (
                    " lost" if bool(incoming.get("fumble_lost")) else " recovered"
                )
                if own_recovery:
                    description += (
                        f" by {self._display(numbers['recoverer'], names['recoverer'])}"
                        f" at {recovery_spot_text}"
                    )
                if bool(incoming.get("fumble_lost")):
                    recoverer = self._display(numbers["returner"], names["returner"]) if numbers["returner"] or names["returner"] else self._team_fallback(state, self.opposite(team))
                    description += f", recovered by {recoverer} at {self.coord_to_spot(turnover_spot, state)}"
                    if turnover_return_yards:
                        description += f", returned {turnover_return_yards} yards to {self.coord_to_spot(return_end, state)}"
            if turnover_type == "downs":
                description += ", turnover on downs"
            if turnover_touchdown:
                description += ", defensive touchdown"
                label = (
                    "Interception Return Touchdown"
                    if turnover_type == "interception"
                    else "Fumble Return Touchdown"
                )
            elif touchdown and kind in {"run", "pass"}:
                description += ", touchdown"
                label = "Touchdown Pass" if kind == "pass" else "Touchdown Run"
            elif first_down:
                description += ", first down"

            scoring_team = (
                turnover_team if turnover_touchdown
                else self.opposite(team) if touchdown and kind in {"kickoff", "punt"}
                else team
            )
            td_number = (
                numbers["returner"]
                if turnover_touchdown
                else numbers["returner"]
                if touchdown and kind in {"kickoff", "punt"}
                else numbers["recoverer"]
                if touchdown and own_recovery
                else numbers["receiver"]
                if kind == "pass" and outcome == "complete"
                else numbers["player"]
            )
            td_name = (
                names["returner"]
                if turnover_touchdown
                else names["returner"]
                if touchdown and kind in {"kickoff", "punt"}
                else names["recoverer"]
                if touchdown and own_recovery
                else names["receiver"]
                if kind == "pass" and outcome == "complete"
                else names["player"]
            )
            created_at = int(self._now())
            after = {
                field: copy.deepcopy(state.get(field))
                for field in self.SNAPSHOT_FIELDS
            }
            event = {
                "id": event_id,
                "play_id": play_id,
                "play_number": play_number,
                "broadcast_id": state.get("broadcast_id", ""),
                "team": scoring_team,
                "team_name": state.get(
                    f"{scoring_team}_team",
                    scoring_team.title(),
                ),
                "event": "PLAY",
                "label": label,
                "description": description,
                "quarter": state.get("quarter", "1"),
                "source": "statistician",
                "created_at": created_at,
                "score_delta": 6 if touchdown else 2 if safety else 0,
                "before": before,
                "after": after,
                "automation": {
                    "play_type": kind,
                    "yards": str(yards),
                    "pass_outcome": outcome,
                    "fumble": bool(incoming.get("fumble")),
                    "fumble_lost": bool(incoming.get("fumble_lost")),
                    "turnover": turnover,
                    "turnover_type": turnover_type,
                    "turnover_team": turnover_team,
                    "turnover_spot": self.coord_to_spot(turnover_spot, state) if turnover else "",
                    "return_end_spot": self.coord_to_spot(return_end, state) if turnover else "",
                    "return_yards": turnover_return_yards if turnover else (return_yards if kind in {"kickoff", "punt"} else 0),
                    "turnover_player_number": (
                        ""
                        if muff_recovered_by_kicking_team
                        else numbers["returner"] if turnover else ""
                    ),
                    "turnover_player_name": (
                        ""
                        if muff_recovered_by_kicking_team
                        else names["returner"] if turnover else ""
                    ),
                    "muffed_punt": muffed_punt,
                    "recoverer_number": numbers["recoverer"] if own_recovery else "",
                    "recoverer_name": names["recoverer"] if own_recovery else "",
                    "recovery_spot": recovery_spot_text,
                    "recovery_yards": recovery_yards if own_recovery else 0,
                    "touchdown": touchdown,
                    "safety": safety,
                    "player_name": (
                        td_name if touchdown else names["player"] or names["receiver"]
                    ),
                    "player_number": (
                        td_number
                        if touchdown
                        else numbers["player"] or numbers["receiver"]
                    ),
                    "sacker_number": numbers["sacker"],
                    "landing_spot": (
                        self.coord_to_spot(landing, state)
                        if kind in {"kickoff", "punt"}
                        else ""
                    ),
                    "kick_distance": (
                        kick_distance if kind in {"kickoff", "punt"} else 0
                    ),
                    "special_teams_return_yards": (
                        return_yards if kind in {"kickoff", "punt"} else 0
                    ),
                },
                "media_trigger": {
                    "key": f"touchdown_{scoring_team}" if touchdown else "",
                    "assigned": bool(touchdown and (td_number or td_name)),
                    "graphics": (
                        "player_touchdown"
                        if touchdown and (td_number or td_name)
                        else None
                    ),
                    "audio": None,
                    "video": None,
                },
            }
            play = {
                "play_id": play_id,
                "play_number": play_number,
                "event_id": event_id,
                "broadcast_id": state.get("broadcast_id", ""),
                "quarter": str(state.get("quarter", "1")),
                "clock": str(incoming.get("clock", "")),
                "offense": (
                    self.opposite(team) if kind in {"kickoff", "punt"} else team
                ),
                "defense": team if kind in {"kickoff", "punt"} else self.opposite(team),
                "kicking_team": team if kind in {"kickoff", "punt"} else "",
                "down": old_down,
                "distance": old_distance,
                "ball_spot": self.coord_to_spot(start, state),
                "end_spot": self.coord_to_spot(end, state),
                "play_type": kind,
                "result": description,
                "yards": yards,
                "first_down": first_down,
                "touchdown": touchdown,
                "turnover": turnover,
                "turnover_type": turnover_type,
                "turnover_team": turnover_team,
                "turnover_spot": self.coord_to_spot(turnover_spot, state) if turnover else "",
                "return_end_spot": self.coord_to_spot(return_end, state) if turnover else "",
                "return_yards": turnover_return_yards if turnover else (return_yards if kind in {"kickoff", "punt"} else 0),
                "turnover_player_number": (
                    ""
                    if muff_recovered_by_kicking_team
                    else numbers["returner"] if turnover else ""
                ),
                "turnover_player_name": (
                    ""
                    if muff_recovered_by_kicking_team
                    else names["returner"] if turnover else ""
                ),
                "safety": safety,
                "muffed_punt": muffed_punt,
                "recoverer_number": numbers["recoverer"] if own_recovery else "",
                "recoverer_name": names["recoverer"] if own_recovery else "",
                "recovery_spot": recovery_spot_text,
                "recovery_yards": recovery_yards if own_recovery else 0,
                "notes": str(incoming.get("notes", "")),
                "created_by": "statistician",
                "created_at": created_at,
                "label": label,
                "player_number": (
                    numbers["returner"]
                    if kind in {"kickoff", "punt"}
                    else numbers["returner"]
                    if turnover_touchdown
                    else numbers["player"] or numbers["receiver"]
                ),
                "player_name": (
                    names["returner"]
                    if kind in {"kickoff", "punt"}
                    else names["returner"]
                    if turnover_touchdown
                    else names["player"] or names["receiver"]
                ),
                "passer_number": numbers["passer"],
                "passer_name": names["passer"],
                "receiver_number": numbers["receiver"],
                "receiver_name": names["receiver"],
                "intended_receiver_number": numbers["receiver"] if kind == "pass" and outcome == "incomplete" else "",
                "intended_receiver_name": names["receiver"] if kind == "pass" and outcome == "incomplete" else "",
                "sacker_number": numbers["sacker"],
                "sacker_name": names["sacker"],
                "kicker_number": numbers["kicker"],
                "kicker_name": names["kicker"],
                "returner_number": numbers["returner"],
                "returner_name": names["returner"],
                "unresolved_players": [
                    role
                    for role, ref in refs.items()
                    if ref.get("number") and not ref.get("resolved")
                ],
                "landing_spot": (
                    self.coord_to_spot(landing, state)
                    if kind in {"kickoff", "punt"}
                    else ""
                ),
                "fumble": bool(incoming.get("fumble")),
                "fumble_lost": bool(incoming.get("fumble_lost")),
                "kneel": bool(incoming.get("kneel")),
                "undone": False,
            }
            state["events"] = (list(state.get("events") or []) + [event])[-500:]
            state["plays"] = (list(state.get("plays") or []) + [play])[-500:]
            state["last_event"] = event
            state["status"] = "live"
            state["broadcast_phase"] = "live"
            revision = assign_next_revision(state)
            metadata = command_metadata(
                incoming,
                action=f"rules_play:{kind}",
                state_revision=revision,
            )
            result_data = attach_metadata(
                {
                    "state": command_result_state(state),
                    "play": copy.deepcopy(play),
                },
                metadata,
            )
            remember_command(
                state,
                command_id,
                metadata=metadata,
                result=result_data,
            )
            self._save_state(state)
            return RulesResult("OK", result_data)
        finally:
            self._transaction_lock.release()


    def _resolve(self, state: dict[str, Any], team: str, number: str) -> dict[str, Any]:
        result = self._resolve_player(state, team, number)
        return copy.deepcopy(dict(result or {}))

    @staticmethod
    def _display(number: str, name: str) -> str:
        if number:
            return f"#{number} {name}".strip()
        return name or "?"

    @staticmethod
    def _team_fallback(state: Mapping[str, Any], team: str) -> str:
        identity = state.get(f"{team}_identity", {})
        if isinstance(identity, Mapping):
            mascot = str(identity.get("mascot") or identity.get("nickname") or "").strip()
            if mascot:
                return mascot
        return str(state.get(f"{team}_team") or team.title()).strip()

    @staticmethod
    def _stop_clock(state: dict[str, Any]) -> None:
        state["clock_running"] = False
        state["clock_started_at"] = 0

    def _show_player_spotlight(
        self,
        state: dict[str, Any],
        *,
        team: str,
        number: str,
        name: str,
        player_ref: Mapping[str, Any],
        position: str,
        detail: str,
        graphic_type: str = "touchdown",
        eyebrow: str = "TOUCHDOWN",
        defensive: bool = False,
        passer_name: str = "",
    ) -> None:
        if not number and not name:
            return
        roster = {
            "id": str(player_ref.get("roster_id", "")),
            "school_id": state.get(f"{team}_school_id", ""),
            "sport": str(state.get("sport") or "Football"),
            "players": [],
        }
        player = {
            "id": str(player_ref.get("player_id", "")),
            "number": number,
            "preferred_name": name,
            "first_name": name,
            "last_name": "",
            "position": position or str(player_ref.get("position", "") or ""),
            "headshot": str(player_ref.get("headshot", "") or ""),
            "grade": str(player_ref.get("grade", "") or ""),
            "height": str(player_ref.get("height", "") or ""),
            "weight": str(player_ref.get("weight", "") or ""),
        }
        self._show_player_graphic(
            state,
            roster,
            player,
            graphic_type,
            8,
            defensive=defensive,
            eyebrow=eyebrow,
            play_detail=detail,
            passer_name=passer_name,
        )







