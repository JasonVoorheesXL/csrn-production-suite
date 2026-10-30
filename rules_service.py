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
        # ball_spot is screen-fixed (LEFT/RIGHT), so flipping the ends changes
        # which team's yard line it names. "screen" (default) leaves the ball
        # where it is on the field -- right when the ball was placed where it
        # really is and only the arrow was wrong. "yard_line" mirrors it so it
        # keeps naming the same team's yard line (LEFT 28 -> RIGHT 28).
        ball = str(incoming.get("ball") or "screen").lower()
        if team not in self.VALID_TEAMS or direction not in self.VALID_DIRECTIONS or ball not in {"screen", "yard_line"}:
            return RulesResult("INVALID_DIRECTION", {})

        with self._transaction_lock:
            state = copy.deepcopy(dict(self._load_state()))
            duplicate = duplicate_result(state, command_id)
            if duplicate is not None:
                return RulesResult("OK", duplicate)
            flips = str(state.get(f"{team}_direction", "") or "").lower() != direction
            if flips and ball == "yard_line" and state.get("ball_spot"):
                state["ball_spot"] = CanonicalStateFoundation.mirror_spot(state["ball_spot"], state)
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
            # load_state() hands back a private, freshly normalized copy; a
            # second deep copy of a multi-MB late-game state is pure cost.
            state = dict(self._load_state())
            blocked = self._phase_block(state, team, kind)
            if blocked is not None:
                return blocked
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

            blocked = self._role_block(state, team, kind)
            if blocked is not None:
                return blocked
            blocked = self._stale_start_block(state, incoming, kind)
            if blocked is not None:
                return blocked

            # Opt-in (the console's play form asks for it): stop before saving
            # a play that looks like it was entered against a wrong drive arrow,
            # so the statistician can flip the arrow or confirm.
            if incoming.get("direction_check") and not incoming.get("direction_confirmed"):
                warning = self.direction_warning(state, incoming, team=team, kind=kind)
                if warning is not None:
                    return RulesResult("DIRECTION_SUSPECT", warning)

            ledger = state.pop("recent_commands", None)
            self._push_history(state)
            if isinstance(state.get("history"), list):
                state["history"] = state["history"][-50:]
            if ledger is not None:
                state["recent_commands"] = ledger
            resolved = self._resolve_play(state, incoming, team=team, kind=kind)
            if isinstance(resolved, RulesResult):
                return resolved
            event, play, team_mismatch_players = resolved
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
            for mismatch in team_mismatch_players:
                get_runtime_diagnostics().record(
                    "SERVER_RULES_PLAYER_TEAM_MISMATCH",
                    command_id=command_id_for_log,
                    play_id=play.get("play_id", ""),
                    play_number=play.get("play_number", ""),
                    **mismatch,
                )
            return RulesResult("OK", result_data)
        finally:
            self._transaction_lock.release()

    # A loss is normal; a run of them is how a wrong drive arrow shows up (every
    # gain is saved as a loss). Warn on the third loss in a row, or the second
    # when together they lose this much.
    DIRECTION_SUSPECT_STREAK = 3
    DIRECTION_SUSPECT_TWO_PLAY_LOSS = 15

    @staticmethod
    def _kneel_like(kind: str, player_number: Any, yards: int) -> bool:
        """A TEAM run losing a yard or two: a victory-formation kneel entered
        without the Kneel box (that is how stat crews write it)."""
        return kind == "run" and not str(player_number or "").strip() and -2 <= yards < 0

    def direction_warning(
        self,
        state: Mapping[str, Any],
        incoming: Mapping[str, Any],
        *,
        team: str,
        kind: str,
    ) -> dict[str, Any] | None:
        """Why this play-form entry looks like the drive arrow is wrong, or None.

        Spots are screen-fixed (LEFT/RIGHT) and yards are derived from the
        team's drive direction, so a wrong arrow turns every gain into a loss
        and sends kicks backwards. Flagged: a kickoff or punt that lands behind
        the kicker, and a run/pass loss that continues a streak of losses by the
        same offense in the same quarter (sacks and kneels are expected losses
        and neither count nor break the streak; 0-yard plays are skipped)."""
        length = self._field_length(state)
        direction = self.team_direction(state, team)
        drives = "RIGHT" if direction == 1 else "LEFT"
        team_name = str(state.get(f"{team}_team") or team.title())
        start = self.spot_to_coord(
            incoming.get("start_spot") or state.get("ball_spot") or (length // 2), state
        )
        base = {
            "error": "DIRECTION_SUSPECT",
            "team": team,
            "team_name": team_name,
            "team_direction": drives.lower(),
        }
        if kind in {"kickoff", "punt"}:
            landing_value = incoming.get("landing_spot")
            if landing_value in (None, "") or incoming.get("blocked"):
                return None
            distance = (self.spot_to_coord(landing_value, state) - start) * direction
            if distance >= 0:
                return None
            return {
                **base,
                "reason": "kick_backwards",
                "yards": distance,
                "flipped_yards": -distance,
                "message": (
                    f"This {kind} lands {-distance} yards BEHIND the kicker: {team_name} is set to drive "
                    f"{drives}. If the arrow is wrong, flip it and the kick becomes {-distance} yards."
                ),
            }
        if kind not in {"run", "pass"}:
            return None
        outcome = str(incoming.get("pass_outcome", "") or "complete").lower()
        if kind == "pass" and outcome in {"incomplete", "spike", "interception", "sack"}:
            return None
        if incoming.get("kneel") or incoming.get("fumble_lost"):
            return None
        end_value = incoming.get("end_spot")
        end = self.spot_to_coord(end_value if end_value not in (None, "") else start, state)
        yards = (end - start) * direction
        if yards >= 0:
            return None
        if self._kneel_like(kind, incoming.get("player_number"), yards):
            return None
        losses = [yards]
        quarter = str(state.get("quarter", "") or "")
        for prior in reversed(list(state.get("plays") or [])):
            if not isinstance(prior, Mapping) or prior.get("undone"):
                continue
            if (
                str(prior.get("play_type", "") or "").lower() not in {"run", "pass"}
                or str(prior.get("offense", "") or "").lower() != team
                or str(prior.get("quarter", "") or "") != quarter
                or prior.get("turnover")
            ):
                break
            if str(prior.get("label", "") or "").lower() == "sack" or prior.get("kneel"):
                continue
            try:
                kneel_yards = int(prior.get("yards") or 0)
            except (TypeError, ValueError):
                kneel_yards = 0
            if self._kneel_like(str(prior.get("play_type", "")).lower(), prior.get("player_number"), kneel_yards):
                continue
            try:
                prior_yards = int(prior.get("yards") or 0)
            except (TypeError, ValueError):
                prior_yards = 0
            if prior_yards > 0:
                break
            if prior_yards < 0:
                losses.append(prior_yards)
            if len(losses) >= self.DIRECTION_SUSPECT_STREAK:
                break
        suspect = len(losses) >= self.DIRECTION_SUSPECT_STREAK or (
            len(losses) >= 2 and -sum(losses) >= self.DIRECTION_SUSPECT_TWO_PLAY_LOSS
        )
        if not suspect:
            return None
        listed = ", ".join(str(value) for value in reversed(losses))
        return {
            **base,
            "reason": "loss_streak",
            "yards": yards,
            "flipped_yards": -yards,
            "losses": list(reversed(losses)),
            "message": (
                f"{team_name} would have {len(losses)} losses in a row ({listed}) driving {drives}. "
                f"If the arrow is wrong, flip it and this play becomes +{-yards} yards."
            ),
        }

    def _resolve_play(
        self,
        state: dict[str, Any],
        incoming: Mapping[str, Any],
        *,
        team: str,
        kind: str,
        replay: Mapping[str, Any] | None = None,
    ) -> "RulesResult | tuple[dict[str, Any], dict[str, Any], list[dict[str, str]]]":
        """Apply one football play to ``state`` and build its event + play record.

        The single source of play semantics, shared by live entry (``play``)
        and by re-entering a past play (``reenter``). ``replay`` carries the
        original identity (play_number, play_id, event_id, created_at) of a play
        being re-run at its place in history: the ids are kept, the play counter
        is left alone, no spotlight fires, and the live-only ejection check is
        skipped (eligibility is derived from the whole game, not that moment).
        """
        roles = CanonicalStateFoundation.team_roles(state)
        spotlight = self._show_player_spotlight if replay is None else (lambda *a, **k: None)
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
            if bool(incoming.get("touchback")):
                # Downed in its own end zone: touchback, ball at its own 20.
                own_goal = 0 if gaining_direction == 1 else length
                return_end = own_goal + gaining_direction * 20
            turnover_return_yards = max(0, (return_end - turnover_spot) * gaining_direction)
            turnover_touchdown = (
                (gaining_direction == 1 and return_end == length)
                or (gaining_direction == -1 and return_end == 0)
            )
            yards = 0 if outcome == "interception" else (turnover_spot - start) * direction
            # "Fumbled at": the officials credit the gain to where the ball
            # came loose; the recovery spot only starts the return.
            fumble_value = incoming.get("fumble_spot")
            if turnover_type == "fumble_recovery" and fumble_value not in (None, ""):
                yards = (self.spot_to_coord(fumble_value, state) - start) * direction
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
                "tackler",
            )
        }
        # A punt downed by the kicking team has no return: the returner
        # fields are ignored outright so nobody is credited with one.
        punt_downed = kind == "punt" and bool(incoming.get("downed"))
        if punt_downed:
            numbers["returner"] = ""
        # Own-team fumble recovery: the carrier fumbles and a *teammate*
        # recovers (no turnover). Possession and the ball never change
        # hands, but credit for the yardage from the recovery spot on -- and
        # any touchdown -- belongs to the recoverer, not the original
        # carrier. Only meaningful on a live run/pass that ended in a
        # normal result; a lost fumble already has its own returner fields.
        handler_number = numbers["receiver"] if kind == "pass" else numbers["player"]
        # A lateral (backward pass) to a teammate splits the yardage the same
        # way: the handler keeps the yards to the lateral spot, the teammate
        # gets the rest (and any touchdown).
        lateral = kind in {"run", "pass"} and bool(incoming.get("lateral")) and not bool(incoming.get("fumble"))
        own_recovery = bool(
            kind in {"run", "pass"}
            and ((bool(incoming.get("fumble")) and not bool(incoming.get("fumble_lost"))) or lateral)
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
            # The tackle is made by the defense on a scrimmage play, by the
            # kicking team on a return, and by the original offense after a
            # turnover.
            "tackler": self._resolve(
                state,
                team if kind in {"kickoff", "punt"} or turnover else self.opposite(team),
                numbers["tackler"],
            ),
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
        team_mismatch_players: list[dict[str, str]] = []
        for role in required_roles:
            permitted_team = roles.defense if role == "sacker" else roles.offense
            ref = refs[role]
            if replay is None and not EligibilityService.is_eligible(
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
            # An unknown number is recorded and surfaced as unresolved. That
            # includes a number that only resolves on the OTHER team: it used
            # to be hard-rejected (PLAYER_TEAM_MISMATCH), but a blank jersey on
            # the permitted team's roster looks exactly the same, and rejecting
            # dropped real plays (2026-10-09: 7 Columbus plays lost, 52 of 90
            # Columbus jerseys blank in rosters.json). The play records with
            # this role unresolved and is flagged in team_mismatch_players so
            # the number can be corrected post-game.
            wrong_team_ref = self._resolve(state, other_team, numbers[role])
            if wrong_team_ref.get("resolved"):
                team_mismatch_players.append(
                    {
                        "role": role,
                        "number": numbers[role],
                        "permitted_team": permitted_team,
                        "resolved_team": other_team,
                        "resolved_name": str(wrong_team_ref.get("name", "") or "").strip(),
                    }
                )
        # A browser-supplied name that is the other team's player at that
        # number would credit the play to the wrong person; keep it #number only.
        wrong_team_names = {
            mismatch["role"]: mismatch["resolved_name"].lower()
            for mismatch in team_mismatch_players
            if mismatch["resolved_name"]
        }
        names = {}
        for role in refs:
            supplied_name = str(incoming.get(f"{role}_name", "") or "").strip()
            if role in wrong_team_names and supplied_name.lower() == wrong_team_names[role]:
                supplied_name = ""
            names[role] = str(refs[role].get("name", "") or supplied_name).strip()
        if punt_downed:
            names["returner"] = ""

        kicker_label = (
            self._display(numbers["kicker"], names["kicker"])
            if numbers["kicker"] or names["kicker"]
            else self._team_fallback(state, team)
        )
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
                    f"Kickoff by {kicker_label} out of bounds at "
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
                    f"Kickoff by {kicker_label} out of bounds at "
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
            # Downed is exclusive of touchback / fair catch / muff (the
            # console clears the others when it is checked).
            touchback = bool(incoming.get("touchback")) and not punt_downed
            # A ruleset with no fair catch (Canadian) ignores the signal
            # outright -- the returner must run it or concede a single.
            fair_catch = bool(incoming.get("fair_catch")) and not self._no_fair_catch(state) and not punt_downed
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
            muffed_punt = bool(incoming.get("muffed_punt")) and not punt_downed
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
            if punt_downed:
                end = landing
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
                f"{label} by {kicker_label} "
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
                if bool(incoming.get("return_out_of_bounds")) and not touchdown:
                    description += ", out of bounds"
            elif punt_downed:
                description += ", downed by the kicking team"
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
                spotlight(
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
                    spotlight(
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
                    spotlight(
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
                spotlight(
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
                spotlight(
                    state,
                    team=self.opposite(team),
                    number=numbers["sacker"],
                    name=names["sacker"],
                    player_ref=refs["sacker"],
                    position="",
                    detail=self.register_text(description, state),
                    graphic_type="sack",
                    eyebrow="SACK",
                    defensive=True,
                )

        if replay is not None:
            play_number = self._bounded_int(replay.get("play_number", 1), 1, minimum=1, maximum=999999)
            play_id = str(replay.get("play_id", ""))
            event_id = str(replay.get("event_id", ""))
        else:
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

        # A flag on the play: the play stands and the foul is enforced in the
        # same event (one undo removes both). A score or turnover wiped out by
        # a foul is a no play, which the console records as a penalty alone.
        flag = self._play_flag(incoming)
        flag_result: dict[str, Any] | None = None
        if flag is not None:
            blocked = self._flag_block(
                flag, kind=kind, touchdown=touchdown, safety=safety,
                turnover=turnover and turnover_type != "downs",
                gaining_team=turnover_team if turnover and turnover_type != "downs" else "",
            )
            if blocked is not None:
                return blocked
            if flag["outcome"] == "accepted":
                if turnover_type == "downs":
                    # The accepted foul replays the down: the offense keeps the ball.
                    state["possession"] = team
                    turnover = False
                    turnover_type = ""
                    turnover_team = ""
                # After a kick or a turnover the ball belongs to a new series:
                # the foul is enforced from the result (end of the return, or
                # the spot of the foul) and the new offense gets 1st & 10. A
                # dead-ball foul after a play that earned a first down also
                # starts the new series after enforcement (NFHS).
                changed_hands = kind in {"kickoff", "punt"} or (turnover and turnover_type != "downs")
                flag_result = self._enforce_flag(
                    state, flag, before=before, from_result=changed_hands,
                    new_series=changed_hands or (flag["enforcement"] == "after_play" and first_down),
                )
                first_down = first_down and str(state.get("down", "")) == "1st"
            else:
                flag_result = {**flag, "applied": False, "enforced_yards": 0}

        turnover_touchback = turnover_type in {"interception", "fumble_recovery"} and bool(incoming.get("touchback"))
        if turnover_type == "interception":
            defender = self._display(numbers["returner"], names["returner"]) if numbers["returner"] or names["returner"] else self._team_fallback(state, self.opposite(team))
            description += f" by {defender} at {self.coord_to_spot(turnover_spot, state)}"
            if turnover_touchback:
                description += ", touchback"
            elif turnover_return_yards:
                description += f", returned {turnover_return_yards} yards to {self.coord_to_spot(return_end, state)}"
        if lateral and own_recovery:
            description += (
                f", lateral to {self._display(numbers['recoverer'], names['recoverer'])}"
                f" at {recovery_spot_text}"
            )
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
                if turnover_touchback:
                    description += ", touchback"
                elif turnover_return_yards:
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
        if numbers["tackler"] and not touchdown:
            description += f" (tackle {self._display(numbers['tackler'], names['tackler'])})"
        if flag_result is not None:
            description += self._flag_description(state, flag_result)
        description = self.register_text(description, state)

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
        created_at = (
            int(replay.get("created_at", 0) or 0) if replay is not None else int(self._now())
        )
        CanonicalStateFoundation.cap_distance_to_goal(state)
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
                "downed": punt_downed,
                "recoverer_number": numbers["recoverer"] if own_recovery else "",
                "recoverer_name": names["recoverer"] if own_recovery else "",
                "recovery_spot": recovery_spot_text,
                "recovery_yards": recovery_yards if own_recovery else 0,
            "lateral": bool(lateral and own_recovery),
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
            # Display enrichment (state_service._enrich_play and the
            # console's resolvedPlayDisplay) keys its completion rewrite
            # off this; without it every pass read as "complete".
            "pass_outcome": (
                outcome if outcome in {"incomplete", "spike", "interception", "sack"} else "complete"
            ) if kind == "pass" else "",
            "yards": yards,
            "first_down": first_down,
            "penalty": copy.deepcopy(flag_result) if flag_result is not None else None,
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
            "downed": punt_downed,
            "recoverer_number": numbers["recoverer"] if own_recovery else "",
            "recoverer_name": names["recoverer"] if own_recovery else "",
            "recovery_spot": recovery_spot_text,
            "recovery_yards": recovery_yards if own_recovery else 0,
            "lateral": bool(lateral and own_recovery),
            "tackler_number": numbers["tackler"] if not touchdown else "",
            "tackler_name": names["tackler"] if not touchdown else "",
            "fumble_spot": (
                self.coord_to_spot(self.spot_to_coord(incoming.get("fumble_spot"), state), state)
                if turnover_type == "fumble_recovery" and incoming.get("fumble_spot") not in (None, "")
                else ""
            ),
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
            "team_mismatch_players": copy.deepcopy(team_mismatch_players),
            "landing_spot": (
                self.coord_to_spot(landing, state)
                if kind in {"kickoff", "punt"}
                else ""
            ),
            "fumble": bool(incoming.get("fumble")),
            "fumble_lost": bool(incoming.get("fumble_lost")),
            "kneel": bool(incoming.get("kneel")),
            # What the statistician entered, so Edit can re-open this play in
            # the play form and re-run it through this method (reenter()).
            "entry": self._entry_record(incoming, team=team, kind=kind, start=start, numbers=numbers, state=state),
            "undone": False,
        }
        return event, play, team_mismatch_players

    # --- Edit = re-enter -------------------------------------------------------
    #
    # Editing a play re-runs it through _resolve_play() at its place in history
    # and then re-runs every later event, so spots, downs, possession, scoring,
    # the result text and player credit all re-derive exactly as if the play had
    # been entered right the first time.

    ENTRY_ROLES = ("player", "passer", "receiver", "sacker", "kicker", "returner", "recoverer", "tackler")
    ENTRY_SPOTS = ("start_spot", "end_spot", "landing_spot", "turnover_spot", "return_end_spot", "recovery_spot", "fumble_spot")
    ENTRY_FLAGS = (
        "kneel", "fumble", "fumble_lost", "muffed_punt", "downed", "out_of_bounds",
        "touchback", "fair_catch", "blocked", "kick_out_of_bounds", "lateral", "return_out_of_bounds",
    )
    ENTRY_TEXT = ("pass_outcome", "out_of_bounds_choice", "clock", "notes")
    # Where the game is (period, clock, ends, the on-air graphic) -- never
    # re-derived; each event keeps what was recorded and the live state wins.
    REPLAY_LIVE_FIELDS = (
        "quarter", "clock_seconds", "clock_visible", "clock_running", "clock_started_at",
        "broadcast_phase", "home_direction", "visitor_direction", "player_graphic",
    )
    # Re-derived by the replay unless something outside the event history
    # (Quick Correction, a period transition) set them between two events.
    REPLAY_CARRIED_FIELDS = (
        "possession", "down", "distance", "ball_spot",
        "special_game_phase", "kicking_team", "receiving_team",
    )
    REPLAY_SCORE_FIELDS = ("home_score", "visitor_score")
    # A later event recorded under a different possession / special phase than
    # the replay now reaches can't be re-run without guessing.
    REPLAY_CHECKED_FIELDS = ("possession", "special_game_phase")
    # Payload keys that are about the request, not the play.
    _REQUEST_KEYS = frozenset({"source", "note", "command_id", "client_id", "expected_revision", "base_revision"})

    def _entry_record(
        self,
        incoming: Mapping[str, Any],
        *,
        team: str,
        kind: str,
        start: int,
        numbers: Mapping[str, str],
        state: Mapping[str, Any],
    ) -> dict[str, Any]:
        entry: dict[str, Any] = {"team": team, "play_type": kind}
        for key in self.ENTRY_SPOTS:
            value = incoming.get(key)
            if key == "turnover_spot" and value in (None, ""):
                value = incoming.get("interception_spot")
            entry[key] = "" if value in (None, "") else self.coord_to_spot(self.spot_to_coord(value, state), state)
        entry["start_spot"] = self.coord_to_spot(start, state)
        for role in self.ENTRY_ROLES:
            entry[f"{role}_number"] = str(numbers.get(role, "") or "")
            entry[f"{role}_name"] = str(incoming.get(f"{role}_name", "") or "").strip()
        for key in self.ENTRY_FLAGS:
            entry[key] = bool(incoming.get(key))
        for key in self.ENTRY_TEXT:
            entry[key] = str(incoming.get(key, "") or "")
        flag = self._play_flag(incoming)
        if flag is not None:
            entry["flag"] = flag
        return entry

    FLAG_ENFORCEMENTS = ("spot_of_foul", "end_of_play", "after_play")

    @classmethod
    def _play_flag(cls, incoming: Mapping[str, Any]) -> dict[str, Any] | None:
        """The penalty attached to a run/pass, normalized; None when there is none.

        enforcement: spot_of_foul (with spot) or end_of_play replay the
        down from the line to gain set before it; after_play is a dead-ball
        foul enforced from the succeeding spot with the down counted.
        """
        raw = incoming.get("flag")
        if not isinstance(raw, Mapping) or not str(raw.get("name", "") or "").strip():
            return None
        enforcement = str(raw.get("enforcement", "") or "").lower()
        return {
            "team": str(raw.get("team", "") or "").lower(),
            "unit": str(raw.get("unit", "") or "General"),
            "name": str(raw.get("name")).strip(),
            "yards": raw.get("yards", ""),
            "outcome": "declined" if str(raw.get("outcome", "") or "").lower() == "declined" else "accepted",
            "enforcement": enforcement if enforcement in cls.FLAG_ENFORCEMENTS else "end_of_play",
            "spot": str(raw.get("spot", "") or ""),
            "half_distance": bool(raw.get("half_distance")),
            "automatic_first_down": bool(raw.get("automatic_first_down")),
            "loss_of_down": bool(raw.get("loss_of_down")),
        }

    def _flag_block(
        self, flag: Mapping[str, Any], *, kind: str, touchdown: bool, safety: bool, turnover: bool,
        gaining_team: str = "",
    ) -> "RulesResult | None":
        if flag["team"] not in self.VALID_TEAMS:
            return RulesResult("FLAG_INVALID", {"message": "Choose which team the flag is on."})
        if kind not in {"run", "pass", "kickoff", "punt"}:
            return RulesResult(
                "FLAG_NOT_SUPPORTED",
                {"message": "Flags can be attached to a run, pass, kickoff or punt. Record other fouls with the Penalty button."},
            )
        # A foul by the team that gained the ball (during its return) leaves
        # the turnover standing; only a foul by the team that lost it wipes it out.
        turnover_wiped = turnover and flag["team"] != gaining_team
        if flag["outcome"] == "accepted" and (touchdown or safety or turnover_wiped):
            return RulesResult(
                "FLAG_NEEDS_NO_PLAY",
                {"message": "A score or turnover wiped out by a penalty is a no play: choose 'No play' in the flag section."},
            )
        if flag["outcome"] == "accepted" and flag["enforcement"] == "spot_of_foul" and not flag["spot"]:
            return RulesResult("FLAG_SPOT_REQUIRED", {"message": "Set the spot of the foul."})
        return None

    def _enforce_flag(
        self, state: dict[str, Any], flag: Mapping[str, Any], *, before: Mapping[str, Any],
        from_result: bool = False, new_series: bool = False,
    ) -> dict[str, Any]:
        from penalty_service import PenaltyService

        enforcement = flag["enforcement"]
        spot = flag["spot"] if enforcement == "spot_of_foul" else str(state.get("ball_spot", "") or "")
        unit = flag["unit"]
        if from_result and unit in {"Offensive", "Defensive"}:
            # The ball changed hands: offense/defense now follow the new possession.
            unit = "Offensive" if flag["team"] == str(state.get("possession", "") or "") else "Defensive"
        result = PenaltyService.enforce(
            state,
            selected_team=flag["team"],
            requested_unit=unit,
            name=flag["name"],
            yards=flag["yards"],
            outcome="accepted",
            spot_to_coord=lambda value: self.spot_to_coord(value, state),
            coord_to_spot=lambda coord: self.coord_to_spot(coord, state),
            team_direction=self.team_direction,
            enforcement_spot=spot,
            half_distance=flag["half_distance"],
            automatic_first_down=flag["automatic_first_down"],
            loss_of_down=flag["loss_of_down"],
            series_before=None if enforcement == "after_play" or from_result else {
                "down": before.get("down"),
                "distance": before.get("distance"),
                "ball_spot": before.get("ball_spot"),
            },
            new_series=new_series,
        )
        return {
            **dict(flag),
            "applied": bool(result.get("applied")),
            "unit": result.get("unit", flag["unit"]),
            "enforced_yards": int(result.get("enforced_yards", 0) or 0),
            "enforcement_spot": result.get("enforcement_spot", spot),
            "result_spot": result.get("result_spot", state.get("ball_spot", "")),
            "automatic_first_down": bool(result.get("automatic_first_down")),
            "loss_of_down": bool(result.get("loss_of_down")),
        }

    def _flag_description(self, state: Mapping[str, Any], flag: Mapping[str, Any]) -> str:
        team_name = str(state.get(f"{flag.get('team', '')}_team") or flag.get("team", "")).strip()
        if not flag.get("applied"):
            return f", penalty on {team_name}: {flag.get('name')}, declined"
        where = {
            "spot_of_foul": f"from the spot of the foul ({flag.get('enforcement_spot')})",
            "end_of_play": "from the end of the play",
            "after_play": "after the play",
        }.get(str(flag.get("enforcement")), "")
        return (
            f", penalty on {team_name}: {flag.get('name')}, {flag.get('enforced_yards', 0)} yards {where}"
            f", ball at {flag.get('result_spot')}"
        )

    @classmethod
    def entry_from_play(
        cls,
        play: Mapping[str, Any],
        event: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """The play-form inputs behind a stored play.

        Plays recorded since edit-by-re-entry carry them verbatim (``entry``);
        older plays are reconstructed from the record and its result text."""
        stored = play.get("entry")
        if isinstance(stored, Mapping) and stored.get("play_type"):
            return copy.deepcopy(dict(stored))
        kind = str(play.get("play_type", "") or "").lower()
        kick = kind not in {"run", "pass"}
        result = str(play.get("result", "") or "")
        lowered = result.lower()
        automation = (event or {}).get("automation")
        if not isinstance(automation, Mapping):
            automation = {}
        team = str((play.get("kicking_team") if kick else play.get("offense")) or "").lower()
        outcome = str(play.get("pass_outcome") or automation.get("pass_outcome") or "").lower()
        if kind == "pass" and not outcome:
            label = str(play.get("label", "") or "").lower()
            outcome = (
                "interception" if "interception" in label
                else "sack" if label == "sack"
                else "spike" if label == "spike"
                else "incomplete" if "incomplete" in label
                else "complete"
            )
        turnover = bool(play.get("turnover")) and str(play.get("turnover_type", "") or "") not in {"", "downs"}
        entry: dict[str, Any] = {
            "team": team,
            "play_type": kind,
            "start_spot": str(play.get("ball_spot", "") or ""),
            "end_spot": str(play.get("end_spot", "") or ""),
            "landing_spot": str(play.get("landing_spot", "") or "") if kick else "",
            "turnover_spot": str(play.get("turnover_spot", "") or "") if turnover and not kick else "",
            "return_end_spot": str(play.get("return_end_spot", "") or "") if turnover and not kick else "",
            "recovery_spot": str(play.get("recovery_spot", "") or ""),
            "pass_outcome": outcome if kind == "pass" else "",
        }
        for role in cls.ENTRY_ROLES:
            entry[f"{role}_number"] = str(play.get(f"{role}_number", "") or "")
            entry[f"{role}_name"] = str(play.get(f"{role}_name", "") or "")
        if kind == "run":
            # player_number holds the returner on a defensive-return touchdown.
            if turnover and play.get("touchdown"):
                match = re.match(r"^#(\w+)", result)
                entry["player_number"] = match.group(1) if match else ""
                entry["player_name"] = ""
        else:
            entry["player_number"] = ""
            entry["player_name"] = ""
        for key in cls.ENTRY_FLAGS:
            entry[key] = bool(play.get(key))
        entry["touchback"] = bool(play.get("touchback")) or (kick and "— touchback" in lowered)
        entry["fair_catch"] = bool(play.get("fair_catch")) or (kick and "— fair catch" in lowered)
        entry["blocked"] = bool(play.get("blocked")) or (kick and "— blocked" in lowered)
        oob = kind == "kickoff" and str(play.get("label", "") or "") == "Kickoff Out of Bounds"
        entry["kick_out_of_bounds"] = oob
        entry["out_of_bounds_choice"] = (
            "" if not oob
            else "rekick" if "re-kick" in lowered
            else "spot_plus_5" if "plus a 5-yard penalty" in lowered
            else "25_yard_line"
        )
        entry["clock"] = str(play.get("clock", "") or "")
        entry["notes"] = str(play.get("notes", "") or "")
        flag = cls._play_flag({"flag": play.get("penalty")})
        if flag is not None:
            entry["flag"] = flag
        return entry

    def _phase_block(self, state: Mapping[str, Any], team: str, kind: str) -> "RulesResult | None":
        phase = str(state.get("special_game_phase", "") or "").lower()
        kicking_team = str(state.get("kicking_team", "") or "").lower()
        if phase == "pending_try":
            return RulesResult(
                "SPECIAL_PHASE_REQUIRES_RESOLUTION",
                {"phase": phase, "message": "The XP/2PT try is still pending. Record the try first."},
            )
        if phase == "kickoff" and (kind != "kickoff" or (kicking_team and team != kicking_team)):
            return RulesResult(
                "SPECIAL_PHASE_REQUIRES_KICKOFF",
                {"phase": phase, "kicking_team": kicking_team,
                 "message": "A kickoff is pending. Record the kickoff first."},
            )
        if phase == "free_kick" and (kind not in {"kickoff", "punt"} or (kicking_team and team != kicking_team)):
            return RulesResult(
                "SPECIAL_PHASE_REQUIRES_FREE_KICK",
                {"phase": phase, "kicking_team": kicking_team,
                 "message": "A free kick is pending. Record the free kick first."},
            )
        if kind == "kickoff" and phase not in {"kickoff", "free_kick"}:
            # A kickoff only follows a score, the start of a half or a free-kick
            # situation; one submitted mid-series is a stale or duplicate form.
            return RulesResult(
                "KICKOFF_NOT_PENDING",
                {"phase": phase, "message": "No kickoff is pending. The play was not recorded."},
            )
        return None

    @staticmethod
    def _role_block(state: Mapping[str, Any], team: str, kind: str) -> "RulesResult | None":
        roles = CanonicalStateFoundation.team_roles(state)
        phase = str(state.get("special_game_phase", "") or "").lower()
        scrimmage_punt = kind == "punt" and phase not in {"kickoff", "free_kick"}
        if (kind in {"run", "pass"} or scrimmage_punt) and team != roles.offense:
            return RulesResult(
                "TEAM_ROLE_MISMATCH",
                {
                    "message": "Offensive plays (run, pass, punt) must be entered for the team in possession.",
                    "submitted_team": team,
                    "offense": roles.offense,
                    "defense": roles.defense,
                },
            )
        return None

    STALE_CHECK_PLAY_TYPES = frozenset({"run", "pass", "punt"})

    def _stale_start_block(
        self, state: Mapping[str, Any], incoming: Mapping[str, Any], kind: str
    ) -> "RulesResult | None":
        """Refuse a play whose form opened on a ball spot that has since moved.

        Only clients that say whether the start spot was hand-corrected
        (``start_spot_corrected``) are checked; a corrected start is the
        statistician's deliberate fix and is honoured as sent.
        """
        if kind not in self.STALE_CHECK_PLAY_TYPES or "start_spot_corrected" not in incoming:
            return None
        if bool(incoming.get("start_spot_corrected")):
            return None
        submitted = incoming.get("start_spot")
        current = state.get("ball_spot")
        if submitted in (None, "") or current in (None, ""):
            return None
        if self.spot_to_coord(submitted, state) == self.spot_to_coord(current, state):
            return None
        return RulesResult(
            "STALE_PLAY_FORM",
            {
                "ball_spot": str(current),
                "submitted_start_spot": str(submitted),
                "message": (
                    f"The ball is now at {current}, not {submitted}. The start spot was updated; "
                    "check the end spot and record the play again."
                ),
            },
        )

    @classmethod
    def _carry_gap(
        cls,
        running: dict[str, Any],
        previous_after: Mapping[str, Any],
        next_before: Mapping[str, Any],
    ) -> None:
        """Move the replay from one event to the next across whatever happened
        between them outside the event history (period transitions, Quick
        Correction): those changes are re-applied, everything else carries."""
        ends_changed = any(
            field in previous_after and field in next_before
            and str(previous_after[field] or "").lower() != str(next_before[field] or "").lower()
            for field in ("home_direction", "visitor_direction")
        )
        CanonicalStateFoundation._follow_recorded_ends(running, next_before)
        for field in cls.REPLAY_CARRIED_FIELDS:
            if field not in previous_after or field not in next_before:
                continue
            expected = previous_after[field]
            if field == "ball_spot" and ends_changed:
                expected = CanonicalStateFoundation.mirror_spot(expected, running)
            if str(next_before[field] or "") != str(expected or ""):
                running[field] = copy.deepcopy(next_before[field])
        for field in cls.REPLAY_SCORE_FIELDS:
            if field in previous_after and field in next_before:
                running[field] = int(running.get(field, 0) or 0) + cls._points(next_before, previous_after, field)
        for field in cls.REPLAY_LIVE_FIELDS:
            if field in next_before:
                running[field] = copy.deepcopy(next_before[field])

    @staticmethod
    def _points(later: Mapping[str, Any], earlier: Mapping[str, Any], field: str) -> int:
        try:
            return int(later.get(field) or 0) - int(earlier.get(field) or 0)
        except (TypeError, ValueError):
            return 0

    @classmethod
    def _apply_recorded_event(
        cls,
        running: dict[str, Any],
        before: Mapping[str, Any],
        after: Mapping[str, Any],
    ) -> None:
        """Replay a non-play event (try, field goal, penalty, ...): the fields
        it changed are applied as recorded, scores as the points it added."""
        for field in CanonicalStateFoundation.snapshot({}):
            if field in cls.REPLAY_LIVE_FIELDS or field not in after:
                continue
            if field in before and after.get(field) == before.get(field):
                continue
            if field in cls.REPLAY_SCORE_FIELDS and field in before:
                running[field] = int(running.get(field, 0) or 0) + cls._points(after, before, field)
            else:
                running[field] = copy.deepcopy(after[field])

    @classmethod
    def _replayed_snapshot(
        cls,
        derived: Mapping[str, Any],
        recorded: Mapping[str, Any],
    ) -> dict[str, Any]:
        """A re-derived before/after snapshot that keeps the recorded period,
        clock and ends (what a later edit needs to read the play the right way)."""
        snapshot = copy.deepcopy(dict(derived))
        for field in cls.REPLAY_LIVE_FIELDS:
            if field in recorded:
                snapshot[field] = copy.deepcopy(recorded[field])
        return snapshot

    @staticmethod
    def _conflict(code: str, message: str, event: Mapping[str, Any], **extra: Any) -> "RulesResult":
        return RulesResult(
            code,
            {
                "error": code,
                "message": message,
                "event_id": str(event.get("id", "")),
                "play_number": event.get("play_number", ""),
                **extra,
            },
        )

    @staticmethod
    def _flipped_ends(snapshot: Mapping[str, Any]) -> dict[str, Any]:
        flipped = copy.deepcopy(dict(snapshot))
        for field in ("home_direction", "visitor_direction"):
            value = str(flipped.get(field, "") or "").lower()
            if value in {"left", "right"}:
                flipped[field] = "left" if value == "right" else "right"
        return flipped

    def repair_direction(self, event_id: str, payload: Mapping[str, Any] | None) -> RulesResult:
        """Re-run plays that were entered with the drive arrow the wrong way.

        Every event from ``event_id`` through ``payload["last_event_id"]`` is
        replayed with both teams' directions flipped. Spots are screen-fixed and
        stay where they were set on the field, so each gain that was saved as a
        loss becomes a gain again (and kicks that went "backwards" go forward);
        downs, first downs, possession and scoring re-derive. Later events then
        replay as for an edit, with the ends they were recorded with. Same
        conflict rule as reenter(): nothing is saved if a later event can no
        longer be replayed."""
        incoming = dict(payload or {})
        last_event_id = str(incoming.get("last_event_id") or event_id)
        return self.reenter(event_id, incoming, flip_through=last_event_id)

    def reenter(
        self,
        event_id: str,
        payload: Mapping[str, Any] | None,
        *,
        flip_through: str | None = None,
    ) -> RulesResult:
        """Edit a recorded play by re-entering it through the play form.

        ``payload`` is a play-form submission (the same fields ``play()`` takes)
        plus an optional correction ``note``. The play is re-run through
        _resolve_play() from the state recorded just before it, then every later
        event is re-run in order: later plays from their own entries (a start
        spot that followed the ball follows the corrected ball; end spots, which
        were set on the field, stay where they were), other events by the
        changes they recorded. Nothing is saved if a later event can no longer
        be replayed (EDIT_CONFLICTS_WITH_LATER_EVENTS).

        ``flip_through`` (see repair_direction()) re-runs the target play from
        its own entry instead of ``payload``, and every event from it through
        that event id with both drive directions flipped.
        """
        incoming = dict(payload or {})
        command_id = command_id_from(incoming)
        with self._transaction_lock:
            state = copy.deepcopy(dict(self._load_state()))
            duplicate = duplicate_result(state, command_id)
            if duplicate is not None:
                return RulesResult("OK", duplicate)
            source = str(incoming.get("source", "statistician") or "statistician").lower()
            if not self._source_allowed(state, source):
                return RulesResult("CONTROL_SOURCE_LOCKED", copy.deepcopy(dict(self._locked_payload(state))))
            events = list(state.get("events") or [])
            plays = list(state.get("plays") or [])
            timeline = [row for row in events if isinstance(row, dict) and not row.get("undone")]
            timeline.sort(key=lambda row: (int(row.get("play_number", 0) or 0), int(row.get("created_at", 0) or 0)))
            target_index = next(
                (index for index, row in enumerate(timeline) if str(row.get("id", "")) == str(event_id)),
                None,
            )
            if target_index is None:
                return RulesResult("EVENT_NOT_FOUND", {"error": "EVENT_NOT_FOUND"})
            valid_kinds = self._valid_play_types(state)

            def rules_play_row(event: Mapping[str, Any]) -> dict[str, Any] | None:
                if str(event.get("event", "")).upper() != "PLAY":
                    return None
                ev_id = str(event.get("id", ""))
                ev_play_id = str(event.get("play_id", "") or "")
                row = next(
                    (
                        row for row in plays
                        if isinstance(row, dict) and not row.get("undone")
                        and (
                            str(row.get("event_id", "")) == ev_id
                            or (ev_play_id and str(row.get("play_id", "")) == ev_play_id)
                        )
                    ),
                    None,
                )
                if row and str(row.get("play_type", "")).lower() in valid_kinds:
                    return row
                return None

            target = timeline[target_index]
            target_play = rules_play_row(target)
            if target_play is None:
                return self._conflict(
                    "NOT_A_RULES_PLAY",
                    "Only run, pass, punt and kickoff plays are re-entered; edit this event with the event form.",
                    target,
                )
            flip_last_index = -1
            if flip_through is not None:
                flip_last_index = next(
                    (index for index, row in enumerate(timeline) if str(row.get("id", "")) == str(flip_through)),
                    -1,
                )
                if flip_last_index < target_index:
                    return RulesResult(
                        "INVALID_REPAIR_RANGE",
                        {
                            "error": "INVALID_REPAIR_RANGE",
                            "message": "Pick the last play of the run that was entered with the arrow the wrong way (at or after the first one).",
                        },
                    )
                target_entry = self.entry_from_play(target_play, target)
                team = str(target_entry.get("team", "")).lower()
                kind = str(target_entry.get("play_type", "")).lower()
            else:
                team = str(incoming.get("team", "")).lower()
                kind = str(incoming.get("play_type", "")).lower()
                target_entry = {key: value for key, value in incoming.items() if key not in self._REQUEST_KEYS}
            if team not in self.VALID_TEAMS or kind not in valid_kinds:
                return RulesResult("INVALID_PLAY", {"error": "INVALID_PLAY"})
            target_entry["team"] = team
            target_entry["play_type"] = kind
            target_entry.setdefault("clock", str(target_play.get("clock", "") or ""))

            def flipped(index: int, snapshot: Mapping[str, Any]) -> dict[str, Any]:
                if target_index <= index <= flip_last_index:
                    return self._flipped_ends(snapshot)
                return copy.deepcopy(dict(snapshot))

            def leave_flip(previous_original_after: Mapping[str, Any]) -> None:
                # Leaving the flipped run: the ends after it are what they were
                # recorded as, and the change back is not a change of ends (the
                # ball does not mirror), so the replay just takes the recorded ends.
                for field in ("home_direction", "visitor_direction"):
                    if field in previous_original_after:
                        running[field] = previous_original_after[field]

            running = copy.deepcopy(state)
            running.update(flipped(target_index, target.get("before") or {}))
            replaced_events: dict[str, dict[str, Any]] = {}
            replaced_plays: dict[str, dict[str, Any]] = {}
            previous_after: Mapping[str, Any] = {}
            previous_original_after: Mapping[str, Any] = {}
            previous_flipped = False
            for offset, event in enumerate(timeline[target_index:]):
                index = target_index + offset
                recorded_before = flipped(index, event.get("before") or {})
                recorded_after = flipped(index, event.get("after") or {})
                is_flipped = index <= flip_last_index
                later = offset > 0
                if later:
                    if previous_flipped and not is_flipped:
                        leave_flip(previous_original_after)
                        previous_after = previous_original_after
                    self._carry_gap(running, previous_after, recorded_before)
                    for field in self.REPLAY_CHECKED_FIELDS:
                        if field in recorded_before and str(running.get(field) or "") != str(recorded_before.get(field) or ""):
                            what = "possession" if field == "possession" else "the try / kickoff sequence"
                            return self._conflict(
                                "EDIT_CONFLICTS_WITH_LATER_EVENTS",
                                (
                                    f"This edit changes {what} before play {event.get('play_number', '?')} "
                                    f"({event.get('label') or event.get('event', 'event')}), which was recorded "
                                    "for the original result. Undo the later plays first, or edit the latest play."
                                ),
                                event,
                                field=field,
                                recorded=recorded_before.get(field),
                                replayed=running.get(field),
                            )
                row = rules_play_row(event) if later else target_play
                if row is None:
                    before_snapshot = self._replayed_snapshot(
                        {field: running.get(field) for field in recorded_before}, recorded_before
                    )
                    self._apply_recorded_event(running, recorded_before, recorded_after)
                    rewritten = copy.deepcopy(event)
                    rewritten["before"] = before_snapshot
                    rewritten["after"] = self._replayed_snapshot(
                        {field: running.get(field) for field in recorded_after}, recorded_after
                    )
                    replaced_events[str(event.get("id", ""))] = rewritten
                    previous_after = recorded_after
                    previous_original_after = copy.deepcopy(dict(event.get("after") or {}))
                    previous_flipped = is_flipped
                    continue
                if later:
                    entry = self.entry_from_play(row, event)
                    if str(row.get("ball_spot", "") or "") == str(recorded_before.get("ball_spot", "") or ""):
                        # The start spot followed the ball; let it follow the corrected ball.
                        entry["start_spot"] = ""
                else:
                    entry = target_entry
                entry_team = str(entry.get("team", "")).lower()
                entry_kind = str(entry.get("play_type", "")).lower()
                blocked = self._phase_block(running, entry_team, entry_kind) or self._role_block(
                    running, entry_team, entry_kind
                )
                resolved: Any = None
                if blocked is None:
                    resolved = self._resolve_play(
                        running,
                        entry,
                        team=entry_team,
                        kind=entry_kind,
                        replay={
                            "play_number": row.get("play_number", event.get("play_number", 1)),
                            "play_id": row.get("play_id", event.get("play_id", "")),
                            "event_id": event.get("id", ""),
                            "created_at": event.get("created_at", row.get("created_at", 0)),
                        },
                    )
                    if isinstance(resolved, RulesResult):
                        blocked = resolved
                if blocked is not None:
                    if not later:
                        data = dict(blocked.data or {})
                        data.setdefault("error", blocked.code)
                        return RulesResult(blocked.code, data)
                    return self._conflict(
                        "EDIT_CONFLICTS_WITH_LATER_EVENTS",
                        f"Play {event.get('play_number', '?')} can no longer be replayed after this edit ({blocked.code}).",
                        event,
                        replay_error=blocked.code,
                    )
                new_event, new_play, _mismatches = resolved
                merged_event = {**copy.deepcopy(event), **new_event}
                merged_event["source"] = event.get("source", new_event.get("source"))
                merged_event["before"] = self._replayed_snapshot(new_event["before"], recorded_before)
                merged_event["after"] = self._replayed_snapshot(new_event["after"], recorded_after)
                merged_play = {**copy.deepcopy(row), **new_play}
                merged_play.pop("invalid_during_special_phase", None)
                replaced_events[str(event.get("id", ""))] = merged_event
                replaced_plays[str(row.get("play_id", ""))] = merged_play
                previous_after = recorded_after
                previous_original_after = copy.deepcopy(dict(event.get("after") or {}))
                previous_flipped = is_flipped

            # Across to the live state: whatever happened since the last event
            # (a period break, Quick Correction) still stands. A repair never
            # changes the live drive direction.
            if previous_flipped:
                leave_flip(previous_original_after)
                previous_after = previous_original_after
            self._carry_gap(running, previous_after, state)
            for field in self.REPLAY_CARRIED_FIELDS + self.REPLAY_SCORE_FIELDS:
                if field in running:
                    state[field] = copy.deepcopy(running[field])
            state["events"] = [
                replaced_events.get(str(row.get("id", "")), row) if isinstance(row, dict) else row
                for row in events
            ]
            state["plays"] = [
                replaced_plays.get(str(row.get("play_id", "")), row)
                if isinstance(row, dict) and not row.get("undone") else row
                for row in plays
            ]
            last_event = state.get("last_event")
            last_id = str(last_event.get("id", "")) if isinstance(last_event, Mapping) else ""
            if last_id in replaced_events:
                state["last_event"] = copy.deepcopy(replaced_events[last_id])
            state["player_eligibility"] = EligibilityService.derive(state)

            new_target_event = replaced_events[str(target.get("id", ""))]
            new_target_play = replaced_plays[str(target_play.get("play_id", ""))]
            replayed = len(timeline) - target_index - 1
            repair = flip_through is not None
            corrections = list(state.get("correction_log") or [])
            corrections.append(
                {
                    "id": f"COR-{int(self._now() * 1000)}",
                    "kind": "direction_repair" if repair else "play_edit",
                    **(
                        {
                            "last_event_id": str(timeline[flip_last_index].get("id", "")),
                            "flipped_events": flip_last_index - target_index + 1,
                        }
                        if repair else {}
                    ),
                    "operator": source,
                    "event_id": str(target.get("id", "")),
                    "before": copy.deepcopy(target),
                    "after": copy.deepcopy(new_target_event),
                    "play_before": copy.deepcopy(target_play),
                    "play_after": copy.deepcopy(new_target_play),
                    "replayed_events": replayed,
                    "note": str(incoming.get("note", "") or "")[:200],
                    "created_at": int(self._now()),
                }
            )
            state["correction_log"] = corrections[-500:]
            revision = assign_next_revision(state)
            metadata = command_metadata(
                incoming, action="direction_repair" if repair else f"play_edit:{kind}", state_revision=revision
            )
            result_data = attach_metadata(
                {
                    "state": command_result_state(state),
                    "play": copy.deepcopy(new_target_play),
                    "event": copy.deepcopy(new_target_event),
                    "replayed_events": replayed,
                },
                metadata,
            )
            remember_command(state, command_id, metadata=metadata, result=result_data)
            self._save_state(state)
            return RulesResult("OK", result_data)

    def _resolve(self, state: dict[str, Any], team: str, number: str) -> dict[str, Any]:
        result = self._resolve_player(state, team, number)
        return copy.deepcopy(dict(result or {}))

    _SCREEN_SPOT = re.compile(r"\b(LEFT|RIGHT) (GOAL|\d+)\b")
    _FOR_YARDS = re.compile(r"\bfor (-?\d+) yards\b")
    _ONE_YARDS = re.compile(r"(?<![\d-])1 yards\b")

    @classmethod
    def team_spot(cls, state: Mapping[str, Any], spot: str) -> str:
        """A screen spot ("RIGHT 5") as the officials say it ("MT 5").

        The left half of the field belongs to the team defending the left
        goal, which is the team driving right.
        """
        match = cls._SCREEN_SPOT.fullmatch(str(spot or "").strip().upper())
        if not match:
            return str(spot or "")
        left_team = "home" if cls.team_direction(state, "home") == 1 else "visitor"
        team = left_team if match.group(1) == "LEFT" else cls.opposite(left_team)
        name = (
            str(state.get(f"{team}_abbreviation") or "").strip()
            or str(state.get(f"{team}_team") or team.title()).strip()
        )
        return f"{name} goal line" if match.group(2) == "GOAL" else f"{name} {match.group(2)}"

    @classmethod
    def yards_phrase(cls, yards: int) -> str:
        if yards == 0:
            return "no gain"
        if yards < 0:
            return f"a loss of {-yards} yard{'' if yards == -1 else 's'}"
        return f"{yards} yard{'' if yards == 1 else 's'}"

    @classmethod
    def register_text(cls, description: str, state: Mapping[str, Any]) -> str:
        """Register wording: team yard lines, "1 yard", "a loss of 3 yards"."""
        text = cls._SCREEN_SPOT.sub(lambda m: cls.team_spot(state, m.group(0)), str(description or ""))

        def for_yards(match: re.Match[str]) -> str:
            yards = int(match.group(1))
            if " sacked " in f" {text} " and yards > 0:
                return f"for a gain of {cls.yards_phrase(yards)}"
            return f"for {cls.yards_phrase(yards)}"

        text = cls._FOR_YARDS.sub(for_yards, text)
        return cls._ONE_YARDS.sub("1 yard", text)

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







