from __future__ import annotations

import copy
import re
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping


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
        with self._transaction_lock:
            state = copy.deepcopy(dict(self._load_state()))
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
            self._save_state(state)
            return RulesResult("OK", {"state": copy.deepcopy(state)})

    def field_direction(self, payload: Mapping[str, Any] | None) -> RulesResult:
        incoming = dict(payload or {})
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
            state[f"{team}_direction"] = direction
            state[f"{self.opposite(team)}_direction"] = (
                "left" if direction == "right" else "right"
            )
            self._save_state(state)
            return RulesResult("OK", {"state": copy.deepcopy(state)})

    def play(self, payload: Mapping[str, Any] | None) -> RulesResult:
        incoming = dict(payload or {})
        team = str(incoming.get("team", "")).lower()
        kind = str(incoming.get("play_type", "")).lower()
        if team not in self.VALID_TEAMS or kind not in self.VALID_PLAY_TYPES:
            return RulesResult("INVALID_PLAY", {})

        with self._transaction_lock:
            state = copy.deepcopy(dict(self._load_state()))
            if not str(state.get("broadcast_id", "")).strip():
                return RulesResult("NO_ACTIVE_BROADCAST", {})
            if not self._source_allowed(state, "statistician"):
                return RulesResult(
                    "CONTROL_SOURCE_LOCKED",
                    copy.deepcopy(dict(self._locked_payload(state))),
                )

            self._push_history(state)
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
            touchdown = (direction == 1 and end == 100) or (
                direction == -1 and end == 0
            )
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
                runner = self._display(numbers["player"], names["player"])
                description = f"{runner} {'kneel' if kneel else 'run'} for {yards} yards"
            elif kind == "pass":
                passer = self._display(numbers["passer"], names["passer"])
                receiver = self._display(numbers["receiver"], names["receiver"])
                if outcome in {"incomplete", "spike"}:
                    end = start
                    yards = 0
                    label = "Spike" if outcome == "spike" else "Incomplete Pass"
                    description = (
                        f"{passer} spike"
                        if outcome == "spike"
                        else f"{passer} pass incomplete"
                    )
                elif outcome == "interception":
                    label = "Interception"
                    description = f"{passer} pass intercepted"
                elif outcome == "sack":
                    sacker = self._display(numbers["sacker"], names["sacker"])
                    label = "Sack"
                    description = f"{passer} sacked by {sacker} for {yards} yards"
                else:
                    label = "Pass"
                    description = f"{passer} complete to {receiver} for {yards} yards"
            else:
                receiving = self.opposite(team)
                state["possession"] = receiving
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
                    self._show_touchdown_graphic(
                        state,
                        team=receiving,
                        number=numbers["returner"],
                        name=names["returner"],
                        player_ref=refs["returner"],
                        position="Returner",
                        detail=f"{return_yards}-yard {kind} return",
                    )

            if kind in {"run", "pass"}:
                if touchdown:
                    state[f"{team}_score"] = int(state.get(f"{team}_score", 0)) + 6
                    state["down"] = "1st"
                    state["distance"] = "10"
                    self._stop_clock(state)
                    td_number = (
                        numbers["receiver"]
                        if kind == "pass" and outcome == "complete"
                        else numbers["player"]
                    )
                    td_name = (
                        names["receiver"]
                        if kind == "pass" and outcome == "complete"
                        else names["player"]
                    )
                    self._show_touchdown_graphic(
                        state,
                        team=team,
                        number=td_number,
                        name=td_name,
                        player_ref={},
                        position="",
                        detail=(
                            f"{yards}-yard touchdown "
                            + ("reception" if kind == "pass" else "run")
                        ),
                    )
                elif safety:
                    other = self.opposite(team)
                    state[f"{other}_score"] = int(state.get(f"{other}_score", 0)) + 2
                    state["possession"] = other
                    self._stop_clock(state)
                elif turnover:
                    state["possession"] = self.opposite(team)
                    state["down"] = "1st"
                    state["distance"] = "10"
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
                    if outcome in {"incomplete", "spike"} or bool(
                        incoming.get("out_of_bounds")
                    ):
                        self._stop_clock(state)
                state["ball_spot"] = self.coord_to_spot(end)

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

            if bool(incoming.get("fumble")):
                description += ", fumble" + (
                    " lost" if bool(incoming.get("fumble_lost")) else " recovered"
                )
            if touchdown and kind in {"run", "pass"}:
                description += ", touchdown"
                label = "Touchdown Pass" if kind == "pass" else "Touchdown Run"
            elif first_down:
                description += ", first down"

            scoring_team = (
                self.opposite(team)
                if touchdown and kind in {"kickoff", "punt"}
                else team
            )
            td_number = (
                numbers["returner"]
                if touchdown and kind in {"kickoff", "punt"}
                else numbers["receiver"]
                if kind == "pass" and outcome == "complete"
                else numbers["player"]
            )
            td_name = (
                names["returner"]
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
                    "return_yards": (
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
                "safety": safety,
                "notes": str(incoming.get("notes", "")),
                "created_by": "statistician",
                "created_at": created_at,
                "label": label,
                "player_number": (
                    numbers["returner"]
                    if kind in {"kickoff", "punt"}
                    else numbers["player"] or numbers["receiver"]
                ),
                "player_name": (
                    names["returner"]
                    if kind in {"kickoff", "punt"}
                    else names["player"] or names["receiver"]
                ),
                "passer_number": numbers["passer"],
                "passer_name": names["passer"],
                "receiver_number": numbers["receiver"],
                "receiver_name": names["receiver"],
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
            self._save_state(state)
            return RulesResult(
                "OK",
                {
                    "state": copy.deepcopy(state),
                    "play": copy.deepcopy(play),
                },
            )

    def _resolve(self, state: dict[str, Any], team: str, number: str) -> dict[str, Any]:
        result = self._resolve_player(state, team, number)
        return copy.deepcopy(dict(result or {}))

    @staticmethod
    def _display(number: str, name: str) -> str:
        if number:
            return f"#{number} {name}".strip()
        return name or "?"

    @staticmethod
    def _stop_clock(state: dict[str, Any]) -> None:
        state["clock_running"] = False
        state["clock_started_at"] = 0

    def _show_touchdown_graphic(
        self,
        state: dict[str, Any],
        *,
        team: str,
        number: str,
        name: str,
        player_ref: Mapping[str, Any],
        position: str,
        detail: str,
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
            "position": position,
        }
        self._show_player_graphic(
            state,
            roster,
            player,
            "touchdown",
            8,
            eyebrow="TOUCHDOWN",
            play_detail=detail,
        )
