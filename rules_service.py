from __future__ import annotations

import copy
import re
import time
import threading
from time import perf_counter
from dataclasses import dataclass
from typing import Any, Callable, Mapping

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

    @staticmethod
    def spot_to_coord(value: Any) -> int:
        """Canonical field coordinate: 0=left goal line, 100=right goal line."""
        text = str(value or "").strip().lower()
        if text in {"left goal", "left_goal", "home goal", "home_goal", "0"}:
            return 0
        if text in {
            "right goal",
            "right_goal",
            "visitor goal",
            "visitor_goal",
            "100",
        }:
            return 100
        if text == "50":
            return 50
        match = re.match(r"^(left|right|home|visitor)\s*(\d{1,2})$", text)
        if match:
            side = match.group(1)
            yard = max(0, min(49, int(match.group(2))))
            return yard if side in {"left", "home"} else 100 - yard
        try:
            return max(0, min(100, int(float(text))))
        except (TypeError, ValueError):
            return 50

    @staticmethod
    def coord_to_spot(coord: Any) -> str:
        try:
            normalized = max(0, min(100, int(coord)))
        except (TypeError, ValueError):
            normalized = 50
        if normalized == 0:
            return "LEFT GOAL"
        if normalized == 100:
            return "RIGHT GOAL"
        if normalized == 50:
            return "50"
        return (
            f"LEFT {normalized}"
            if normalized < 50
            else f"RIGHT {100 - normalized}"
        )

    @staticmethod
    def team_direction(state: Mapping[str, Any], team: str) -> int:
        default = "right" if team == "home" else "left"
        direction = str(state.get(f"{team}_direction", default)).lower()
        return 1 if direction == "right" else -1

    @staticmethod
    def opposite(team: str) -> str:
        return "visitor" if team == "home" else "home"

    @staticmethod
    def advance_down(down: Any) -> str:
        order = ["1st", "2nd", "3rd", "4th"]
        try:
            return order[min(3, order.index(str(down)) + 1)]
        except ValueError:
            return "1st"

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
        if team not in self.VALID_TEAMS or kind not in self.VALID_PLAY_TYPES:
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
            start = self.spot_to_coord(
                incoming.get("start_spot") or state.get("ball_spot") or 50
            )
            end_value = incoming.get("end_spot")
            end = self.spot_to_coord(
                end_value if end_value not in (None, "") else start
            )
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
                    or self.coord_to_spot(end)
                )
                turnover_spot = self.spot_to_coord(spot_value)
                return_value = incoming.get("return_end_spot")
                return_end = self.spot_to_coord(
                    return_value if return_value not in (None, "") else self.coord_to_spot(turnover_spot)
                )
                gaining_direction = self.team_direction(state, turnover_team)
                turnover_return_yards = max(0, (return_end - turnover_spot) * gaining_direction)
                turnover_touchdown = (
                    (gaining_direction == 1 and return_end == 100)
                    or (gaining_direction == -1 and return_end == 0)
                )
                yards = 0 if outcome == "interception" else (turnover_spot - start) * direction
                end = return_end
            touchdown = (not turnover) and ((direction == 1 and end == 100) or (
                direction == -1 and end == 0
            ))
            safety = (direction == 1 and end == 0) or (
                direction == -1 and end == 100
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
                )
            }
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
            else:
                receiving = self.opposite(team)
                state["possession"] = receiving
                CanonicalStateFoundation.clear_special_phase(state)
                landing_value = incoming.get("landing_spot")
                landing = self.spot_to_coord(
                    landing_value if landing_value not in (None, "") else end
                )
                touchback = bool(incoming.get("touchback"))
                fair_catch = bool(incoming.get("fair_catch"))
                blocked = bool(incoming.get("blocked"))
                if touchback:
                    receiving_direction = self.team_direction(state, receiving)
                    end = 20 if receiving_direction == 1 else 80
                kick_distance = abs(landing - start)
                return_direction = self.team_direction(state, receiving)
                return_yards = max(0, (end - landing) * return_direction)
                touchdown = bool(
                    not touchback
                    and not fair_catch
                    and numbers["returner"]
                    and (
                        (return_direction == 1 and end == 100)
                        or (return_direction == -1 and end == 0)
                    )
                )
                if touchdown:
                    state[f"{receiving}_score"] = (
                        int(state.get(f"{receiving}_score", 0) or 0) + 6
                    )
                    CanonicalStateFoundation.enter_pending_try(state, receiving)
                else:
                    state["ball_spot"] = self.coord_to_spot(end)
                    state["down"] = "1st"
                    state["distance"] = "10"
                self._stop_clock(state)
                label = "Kickoff" if kind == "kickoff" else "Punt"
                description = (
                    f"{label} by #{numbers['kicker'] or '?'} "
                    f"landed at {self.coord_to_spot(landing)}"
                )
                if numbers["returner"] and not fair_catch and not touchback:
                    returner = self._display(
                        numbers["returner"],
                        names["returner"],
                    )
                    description += (
                        f", returned by {returner} for {return_yards} yards "
                        f"to {self.coord_to_spot(end)}"
                    )
                else:
                    description += f", ball at {self.coord_to_spot(end)}"
                description += (
                    " â€” touchback"
                    if touchback
                    else " â€” fair catch"
                    if fair_catch
                    else " â€” blocked"
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

            if kind in {"run", "pass"}:
                if turnover:
                    state["possession"] = turnover_team
                    state["down"] = "1st"
                    state["distance"] = "10"
                    if turnover_touchdown:
                        state[f"{turnover_team}_score"] = int(state.get(f"{turnover_team}_score", 0)) + 6
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
                    state[f"{team}_score"] = int(state.get(f"{team}_score", 0)) + 6
                    CanonicalStateFoundation.enter_pending_try(state, team)
                    self._stop_clock(state)
                    is_pass_reception = kind == "pass" and outcome == "complete"
                    td_role = "receiver" if is_pass_reception else "player"
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
                            f"{yards}-yard touchdown "
                            + ("reception" if kind == "pass" else "run")
                        ),
                        # Only a pass-reception touchdown has a separate QB to
                        # credit -- run TDs and the punt/kickoff-return and
                        # turnover-return branches (their own
                        # _show_player_spotlight() calls above) have no
                        # passer role at all.
                        passer_name=names["passer"] if is_pass_reception else "",
                    )
                elif safety:
                    other = self.opposite(team)
                    state[f"{other}_score"] = int(state.get(f"{other}_score", 0)) + 2
                    CanonicalStateFoundation.enter_free_kick(state, team)
                    self._stop_clock(state)
                else:
                    first_down = yards >= distance
                    if first_down:
                        state["down"] = "1st"
                        state["distance"] = "10"
                    else:
                        state["down"] = self.advance_down(old_down)
                        state["distance"] = str(max(1, distance - yards))
                        if old_down == "4th":
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
                    state["ball_spot"] = self.coord_to_spot(end)

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
                description += f" by {defender} at {self.coord_to_spot(turnover_spot)}"
                if turnover_return_yards:
                    description += f", returned {turnover_return_yards} yards to {self.coord_to_spot(return_end)}"
            if bool(incoming.get("fumble")):
                description += ", fumble" + (
                    " lost" if bool(incoming.get("fumble_lost")) else " recovered"
                )
                if bool(incoming.get("fumble_lost")):
                    recoverer = self._display(numbers["returner"], names["returner"]) if numbers["returner"] or names["returner"] else self._team_fallback(state, self.opposite(team))
                    description += f", recovered by {recoverer} at {self.coord_to_spot(turnover_spot)}"
                    if turnover_return_yards:
                        description += f", returned {turnover_return_yards} yards to {self.coord_to_spot(return_end)}"
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
                else numbers["receiver"]
                if kind == "pass" and outcome == "complete"
                else numbers["player"]
            )
            td_name = (
                names["returner"]
                if turnover_touchdown
                else names["returner"]
                if touchdown and kind in {"kickoff", "punt"}
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
                    "turnover_spot": self.coord_to_spot(turnover_spot) if turnover else "",
                    "return_end_spot": self.coord_to_spot(return_end) if turnover else "",
                    "return_yards": turnover_return_yards if turnover else (return_yards if kind in {"kickoff", "punt"} else 0),
                    "turnover_player_number": numbers["returner"] if turnover else "",
                    "turnover_player_name": names["returner"] if turnover else "",
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
                        self.coord_to_spot(landing)
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
                "ball_spot": self.coord_to_spot(start),
                "end_spot": self.coord_to_spot(end),
                "play_type": kind,
                "result": description,
                "yards": yards,
                "first_down": first_down,
                "touchdown": touchdown,
                "turnover": turnover,
                "turnover_type": turnover_type,
                "turnover_team": turnover_team,
                "turnover_spot": self.coord_to_spot(turnover_spot) if turnover else "",
                "return_end_spot": self.coord_to_spot(return_end) if turnover else "",
                "return_yards": turnover_return_yards if turnover else (return_yards if kind in {"kickoff", "punt"} else 0),
                "turnover_player_number": numbers["returner"] if turnover else "",
                "turnover_player_name": names["returner"] if turnover else "",
                "safety": safety,
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
                    self.coord_to_spot(landing)
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







