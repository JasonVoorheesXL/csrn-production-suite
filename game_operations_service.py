from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Callable, Mapping


@dataclass(frozen=True)
class GameOperationsResult:
    code: str
    data: dict[str, Any]

    @property
    def ok(self) -> bool:
        return self.code == "OK"


class GameOperationsService:
    """Live game-operation boundary independent of Flask and persistence details."""

    VALID_TEAMS = {"home", "visitor"}
    VALID_SCORE_DELTAS = {-1, 1, 2, 3, 6}
    ALLOWED_SET_FIELDS = {
        "quarter",
        "down",
        "distance",
        "clock_visible",
        "possession",
        "scorebug_visible",
        "broadcast_phase",
        "ticker_visible",
        "ticker_speed",
        "ticker_pause",
    }
    GAME_DATA_FIELDS = {"quarter", "down", "distance", "possession"}
    RESET_PRESERVED_FIELDS = (
        "broadcast_id",
        "sport",
        "season",
        "week",
        "classification",
        "level",
        "division",
        "home_team",
        "visitor_team",
        "home_school_id",
        "visitor_school_id",
        "home_identity",
        "visitor_identity",
        "venue_id",
        "venue",
        "date",
        "scheduled_start",
        "visual_mode",
        "crew",
        "status",
    )

    def __init__(
        self,
        *,
        load_state: Callable[[], Mapping[str, Any]],
        save_state: Callable[[Mapping[str, Any]], Any],
        default_state: Callable[[], Mapping[str, Any]],
        push_history: Callable[[dict[str, Any]], None],
        source_allowed: Callable[[dict[str, Any], str], bool],
        locked_payload: Callable[[dict[str, Any]], Mapping[str, Any]],
        update_linked_status: Callable[..., Any],
        load_config: Callable[[], Mapping[str, Any]],
        command_scorebug_visibility: Callable[[bool], Any],
        transaction_lock: Any,
    ) -> None:
        self._load_state = load_state
        self._save_state = save_state
        self._default_state = default_state
        self._push_history = push_history
        self._source_allowed = source_allowed
        self._locked_payload = locked_payload
        self._update_linked_status = update_linked_status
        self._load_config = load_config
        self._command_scorebug_visibility = command_scorebug_visibility
        self._transaction_lock = transaction_lock

    def score(self, payload: Mapping[str, Any] | None) -> GameOperationsResult:
        incoming = dict(payload or {})
        team = str(incoming.get("team", "")).lower()
        try:
            delta = int(incoming.get("delta", 0))
        except (TypeError, ValueError):
            return GameOperationsResult("INVALID_SCORE_REQUEST", {})
        if team not in self.VALID_TEAMS or delta not in self.VALID_SCORE_DELTAS:
            return GameOperationsResult("INVALID_SCORE_REQUEST", {})

        with self._transaction_lock:
            state = copy.deepcopy(dict(self._load_state()))
            source = str(
                incoming.get("source", "broadcaster") or "broadcaster"
            ).lower()
            if not self._source_allowed(state, source):
                return GameOperationsResult(
                    "CONTROL_SOURCE_LOCKED",
                    copy.deepcopy(dict(self._locked_payload(state))),
                )

            self._push_history(state)
            key = "home_score" if team == "home" else "visitor_score"
            try:
                current_score = int(state.get(key, 0) or 0)
            except (TypeError, ValueError):
                current_score = 0
            state[key] = max(0, current_score + delta)
            if state.get("broadcast_phase") == "pregame":
                state["broadcast_phase"] = "live"
            self._save_state(state)

            broadcast_id = str(state.get("broadcast_id", "") or "")
            if broadcast_id and state.get("status") != "live":
                state["status"] = "live"
                self._save_state(state)
                self._update_linked_status(broadcast_id, "live")

            return GameOperationsResult(
                "OK",
                {"state": copy.deepcopy(state)},
            )

    def set_values(
        self,
        payload: Mapping[str, Any] | None,
    ) -> GameOperationsResult:
        incoming = dict(payload or {})
        changes = {
            key: copy.deepcopy(value)
            for key, value in incoming.items()
            if key in self.ALLOWED_SET_FIELDS
        }

        with self._transaction_lock:
            state = copy.deepcopy(dict(self._load_state()))
            source = str(
                incoming.get("source", "broadcaster") or "broadcaster"
            ).lower()
            if self.GAME_DATA_FIELDS.intersection(changes) and not self._source_allowed(
                state,
                source,
            ):
                return GameOperationsResult(
                    "CONTROL_SOURCE_LOCKED",
                    copy.deepcopy(dict(self._locked_payload(state))),
                )

            self._push_history(state)
            state.update(changes)
            self._save_state(state)
            return GameOperationsResult(
                "OK",
                {
                    "state": copy.deepcopy(state),
                    "changes": copy.deepcopy(changes),
                },
            )

    def toggle_scorebug(self) -> GameOperationsResult:
        with self._transaction_lock:
            state = copy.deepcopy(dict(self._load_state()))
            active_broadcast_id = state.get("broadcast_id", "")
            next_visible = not bool(state.get("scorebug_visible"))
            config = dict(self._load_config() or {})
            obs = config.get("obs") if isinstance(config.get("obs"), Mapping) else {}
            if bool(obs.get("controlled_commands", False)):
                try:
                    self._command_scorebug_visibility(next_visible)
                except Exception as exc:  # command adapters normalize their own failures
                    return GameOperationsResult(
                        "OBS_COMMAND_BLOCKED",
                        {"message": str(exc)},
                    )

            self._push_history(state)
            state["scorebug_visible"] = next_visible
            # Visibility must never change the selected broadcast.
            state["broadcast_id"] = active_broadcast_id
            self._save_state(state)
            return GameOperationsResult(
                "OK",
                {"state": copy.deepcopy(state)},
            )

    def toggle_halftime(self) -> GameOperationsResult:
        with self._transaction_lock:
            state = copy.deepcopy(dict(self._load_state()))
            self._push_history(state)
            if state.get("broadcast_phase") == "halftime":
                state["broadcast_phase"] = "live"
                state["quarter"] = "3"
                state["scorebug_visible"] = True
            else:
                state["broadcast_phase"] = "halftime"
                state["scorebug_visible"] = False
            self._save_state(state)
            return GameOperationsResult(
                "OK",
                {"state": copy.deepcopy(state)},
            )

    def end_game(self) -> GameOperationsResult:
        with self._transaction_lock:
            state = copy.deepcopy(dict(self._load_state()))
            self._push_history(state)
            state["broadcast_phase"] = "final"
            state["scorebug_visible"] = False
            state["status"] = "completed"
            self._save_state(state)
            self._update_linked_status(
                state.get("broadcast_id", ""),
                "completed",
                {
                    "final_home_score": state.get("home_score", 0),
                    "final_visitor_score": state.get("visitor_score", 0),
                },
            )
            return GameOperationsResult(
                "OK",
                {"state": copy.deepcopy(state)},
            )

    def reset_data(self) -> GameOperationsResult:
        with self._transaction_lock:
            current = copy.deepcopy(dict(self._load_state()))
            reset = copy.deepcopy(dict(self._default_state()))
            for field in self.RESET_PRESERVED_FIELDS:
                if field in current:
                    reset[field] = copy.deepcopy(current[field])
            broadcast_id = str(current.get("broadcast_id", "") or "")
            completed = current.get("status") == "completed"
            reset["broadcast_created"] = bool(broadcast_id)
            reset["broadcast_id"] = broadcast_id
            reset["broadcast_phase"] = "final" if completed else "pregame"
            reset["review_mode"] = completed
            reset["scorebug_visible"] = False
            self._save_state(reset)
            return GameOperationsResult(
                "OK",
                {"state": copy.deepcopy(reset)},
            )

    def new_broadcast(self) -> GameOperationsResult:
        with self._transaction_lock:
            state = copy.deepcopy(dict(self._default_state()))
            self._save_state(state)
            return GameOperationsResult(
                "OK",
                {"state": copy.deepcopy(state)},
            )
