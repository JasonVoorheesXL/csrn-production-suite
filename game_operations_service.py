from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Callable, Mapping

from period_service import PeriodService
from live_command_service import (
    assign_next_revision,
    attach_metadata,
    command_result_state,
    command_id_from,
    command_metadata,
    current_revision,
    duplicate_result,
    remember_command,
)


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
        "ball_spot_visible",
    }
    GAME_DATA_FIELDS = {"quarter", "down", "distance", "possession"}
    RESET_PRESERVED_FIELDS = (
        "broadcast_id",
        "sport",
        "season",
        "week",
        "classification",
        "home_classification",
        "home_region",
        "visitor_classification",
        "visitor_region",
        "home_pregame_record",
        "home_pregame_region_record",
        "visitor_pregame_record",
        "visitor_pregame_region_record",
        "contest_type",
        "record_policy",
        "region_game",
        "special_designations",
        "record_tracking",
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
        archive_final_state: Callable[[Mapping[str, Any]], bool] | None = None,
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
        self._archive_final_state = archive_final_state

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
            command_id = command_id_from(incoming)
            duplicate = duplicate_result(state, command_id)
            if duplicate is not None:
                return GameOperationsResult("OK", duplicate)
            source = str(
                incoming.get("source", "broadcaster") or "broadcaster"
            ).lower()
            broadcaster_override = (
                source == "broadcaster"
                and bool(incoming.get("override", False))
            )
            if not broadcaster_override and not self._source_allowed(state, source):
                return GameOperationsResult(
                    "CONTROL_SOURCE_LOCKED",
                    copy.deepcopy(dict(self._locked_payload(state))),
                )

            ledger = state.pop("recent_commands", None)
            self._push_history(state)
            if isinstance(state.get("history"), list):
                state["history"] = state["history"][-50:]
            if ledger is not None:
                state["recent_commands"] = ledger
            key = "home_score" if team == "home" else "visitor_score"
            try:
                current_score = int(state.get(key, 0) or 0)
            except (TypeError, ValueError):
                current_score = 0
            new_score = max(0, current_score + delta)
            state[key] = new_score
            if state.get("broadcast_phase") == "pregame":
                state["broadcast_phase"] = "live"
            broadcast_id = str(state.get("broadcast_id", "") or "")
            linked_status_update = False
            if broadcast_id and state.get("status") != "live":
                state["status"] = "live"
                linked_status_update = True
            revision = assign_next_revision(state)
            metadata = command_metadata(
                incoming,
                action="direct_score_adjustment",
                state_revision=revision,
            )
            correction = {
                "type": "direct_score_adjustment",
                "team": team,
                "delta": delta,
                "old_score": current_score,
                "new_score": new_score,
                "source": source,
                "reason": str(incoming.get("reason", incoming.get("note", "")) or "")[:200],
                "command_id": command_id,
                "client_id": str(incoming.get("client_id", "") or ""),
                "state_revision": revision,
                "timestamp": metadata["committed_at"],
            }
            log = state.get("correction_log")
            if not isinstance(log, list):
                log = []
            state["correction_log"] = (log + [correction])[-200:]
            result_data = attach_metadata({"state": command_result_state(state)}, metadata)
            remember_command(
                state,
                command_id,
                metadata=metadata,
                result=result_data,
            )
            self._save_state(state)

            if linked_status_update:
                self._update_linked_status(broadcast_id, "live")

            return GameOperationsResult("OK", result_data)

    def set_values(
        self,
        payload: Mapping[str, Any] | None,
    ) -> GameOperationsResult:
        incoming = dict(payload or {})
        command_id = command_id_from(incoming)
        changes = {
            key: copy.deepcopy(value)
            for key, value in incoming.items()
            if key in self.ALLOWED_SET_FIELDS
        }

        with self._transaction_lock:
            state = copy.deepcopy(dict(self._load_state()))
            duplicate = duplicate_result(state, command_id)
            if duplicate is not None:
                return GameOperationsResult("OK", duplicate)
            source = str(
                incoming.get("source", "broadcaster") or "broadcaster"
            ).lower()
            period_action = str(incoming.get("period_action", "") or "").strip().lower()
            if (self.GAME_DATA_FIELDS.intersection(changes) or period_action) and not self._source_allowed(
                state,
                source,
            ):
                return GameOperationsResult(
                    "CONTROL_SOURCE_LOCKED",
                    copy.deepcopy(dict(self._locked_payload(state))),
                )

            if period_action:
                transition = PeriodService.transition(
                    state,
                    period_action,
                    second_half_receiving_team=incoming.get("second_half_receiving_team", ""),
                    overtime_possession=incoming.get("overtime_possession", ""),
                    overtime_spot=incoming.get("overtime_spot", ""),
                )
                if transition.code in {
                    "INVALID_PERIOD_ACTION",
                    "SECOND_HALF_RECEIVER_REQUIRED",
                    "OVERTIME_SETUP_REQUIRED",
                }:
                    response_state = copy.deepcopy(state)
                    response_state["period_action_code"] = transition.code
                    response_state["period_action_error"] = str(transition.data.get("message", "Period action could not be completed."))
                    return GameOperationsResult("OK", {"state": response_state, "changes": {}})

                self._push_history(state)
                state = copy.deepcopy(transition.state)
                state.pop("period_action_code", None)
                state.pop("period_action_error", None)
                revision = assign_next_revision(state)
                metadata = command_metadata(
                    incoming,
                    action=f"set_values:period:{period_action}",
                    state_revision=revision,
                )
                result_data = attach_metadata(
                    {
                        "state": copy.deepcopy(state),
                        "changes": {"period_action": period_action},
                        "period": copy.deepcopy(transition.data),
                    },
                    metadata,
                )
                remember_command(state, command_id, metadata=metadata, result=result_data)
                self._save_state(state)
                if period_action == "final_game":
                    broadcast_id = str(state.get("broadcast_id", "") or "")
                    if broadcast_id:
                        self._update_linked_status(
                            broadcast_id,
                            "completed",
                            {
                                "final_home_score": state.get("home_score", 0),
                                "final_visitor_score": state.get("visitor_score", 0),
                            },
                        )
                    self._archive_and_clear_history_if_final(state, result_data)
                return GameOperationsResult("OK", result_data)

            self._push_history(state)
            state.update(changes)
            revision = assign_next_revision(state)
            metadata = command_metadata(
                incoming,
                action="set_values",
                state_revision=revision,
            )
            result_data = attach_metadata(
                {
                    "state": copy.deepcopy(state),
                    "changes": copy.deepcopy(changes),
                },
                metadata,
            )
            remember_command(state, command_id, metadata=metadata, result=result_data)
            self._save_state(state)
            return GameOperationsResult("OK", result_data)

    def toggle_scorebug(self, payload: Mapping[str, Any] | None = None) -> GameOperationsResult:
        incoming = dict(payload or {})
        command_id = command_id_from(incoming)
        with self._transaction_lock:
            state = copy.deepcopy(dict(self._load_state()))
            duplicate = duplicate_result(state, command_id)
            if duplicate is not None:
                return GameOperationsResult("OK", duplicate)
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
            revision = assign_next_revision(state)
            metadata = command_metadata(
                incoming,
                action="toggle_scorebug",
                state_revision=revision,
            )
            result_data = attach_metadata({"state": copy.deepcopy(state)}, metadata)
            remember_command(state, command_id, metadata=metadata, result=result_data)
            self._save_state(state)
            return GameOperationsResult("OK", result_data)

    def toggle_halftime(self, payload: Mapping[str, Any] | None = None) -> GameOperationsResult:
        incoming = dict(payload or {})
        command_id = command_id_from(incoming)
        with self._transaction_lock:
            state = copy.deepcopy(dict(self._load_state()))
            duplicate = duplicate_result(state, command_id)
            if duplicate is not None:
                return GameOperationsResult("OK", duplicate)
            self._push_history(state)
            if state.get("broadcast_phase") == "halftime":
                transition = PeriodService.transition(state, "start_second_half")
                if transition.code == "SECOND_HALF_RECEIVER_REQUIRED":
                    state["quarter"] = "3"
                    state["broadcast_phase"] = "live"
                    state["period_state"] = "quarter"
                    state["halftime_pending"] = False
                    state["down"] = "1st"
                    state["distance"] = "10"
                    state["clock_running"] = False
                    state["clock_seconds"] = 720
                    state["scorebug_visible"] = True
                elif transition.code != "OK":
                    return GameOperationsResult(
                        transition.code,
                        {
                            "state": copy.deepcopy(state),
                            "message": str(transition.data.get("message", "Second half could not be started.")),
                        },
                    )
                else:
                    state = copy.deepcopy(transition.state)
            else:
                state["broadcast_phase"] = "halftime"
                # Halftime remains an on-air game state. Keep the scorebug
                # visible; the overlay replaces quarter/clock/down content with
                # a dedicated HALFTIME presentation.
                state["scorebug_visible"] = True
            revision = assign_next_revision(state)
            metadata = command_metadata(
                incoming,
                action="toggle_halftime",
                state_revision=revision,
            )
            result_data = attach_metadata({"state": copy.deepcopy(state)}, metadata)
            remember_command(state, command_id, metadata=metadata, result=result_data)
            self._save_state(state)
            return GameOperationsResult("OK", result_data)

    def _archive_and_clear_history_if_final(
        self,
        state: dict[str, Any],
        result_data: dict[str, Any],
    ) -> None:
        """Once a broadcast has just been saved as 'completed', archive its
        full state (including history) and, only if that archive is
        confirmed written to disk, clear history/events/plays from the live
        state.

        Must run inside the caller's already-held transaction lock (both
        end_game() and set_values()'s final_game branch call this from
        within `with self._transaction_lock:`), so the archive write can't
        race the background linked-snapshot writer.

        If archiving fails or can't be confirmed, live state is left
        completely untouched — history/events/plays are not cleared — and
        an "archive_error" message is attached to the response state so the
        operator sees it, instead of the data silently disappearing.
        """
        if self._archive_final_state is None:
            return
        if str(state.get("status", "")).strip().lower() != "completed":
            return

        try:
            archived = bool(self._archive_final_state(state))
            error_message = "" if archived else (
                "Broadcast archive could not be confirmed; "
                "live game history was not cleared."
            )
        except Exception as exc:
            archived = False
            error_message = f"Broadcast archive failed: {exc}"

        response_state = dict(result_data.get("state") or {})
        if archived:
            state["history"] = []
            state["events"] = []
            state["plays"] = []
            self._save_state(state)
            response_state = copy.deepcopy(state)
        else:
            response_state["archive_error"] = error_message
        result_data["state"] = response_state

    def end_game(self, payload: Mapping[str, Any] | None = None) -> GameOperationsResult:
        incoming = dict(payload or {})
        command_id = command_id_from(incoming)
        with self._transaction_lock:
            state = copy.deepcopy(dict(self._load_state()))
            duplicate = duplicate_result(state, command_id)
            if duplicate is not None:
                return GameOperationsResult("OK", duplicate)
            self._push_history(state)
            state["broadcast_phase"] = "final"
            state["scorebug_visible"] = False
            state["status"] = "completed"
            revision = assign_next_revision(state)
            metadata = command_metadata(
                incoming,
                action="end_game",
                state_revision=revision,
            )
            result_data = attach_metadata({"state": copy.deepcopy(state)}, metadata)
            remember_command(state, command_id, metadata=metadata, result=result_data)
            self._save_state(state)
            self._update_linked_status(
                state.get("broadcast_id", ""),
                "completed",
                {
                    "final_home_score": state.get("home_score", 0),
                    "final_visitor_score": state.get("visitor_score", 0),
                },
            )
            self._archive_and_clear_history_if_final(state, result_data)
            return GameOperationsResult("OK", result_data)

    def reset_data(self, payload: Mapping[str, Any] | None = None) -> GameOperationsResult:
        incoming = dict(payload or {})
        command_id = command_id_from(incoming)
        with self._transaction_lock:
            current = copy.deepcopy(dict(self._load_state()))
            duplicate = duplicate_result(current, command_id)
            if duplicate is not None:
                return GameOperationsResult("OK", duplicate)
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
            reset["state_revision"] = current_revision(current)
            revision = assign_next_revision(reset)
            metadata = command_metadata(
                incoming,
                action="reset_data",
                state_revision=revision,
            )
            result_data = attach_metadata({"state": copy.deepcopy(reset)}, metadata)
            remember_command(reset, command_id, metadata=metadata, result=result_data)
            self._save_state(reset)
            return GameOperationsResult("OK", result_data)

    def new_broadcast(self, payload: Mapping[str, Any] | None = None) -> GameOperationsResult:
        incoming = dict(payload or {})
        command_id = command_id_from(incoming)
        with self._transaction_lock:
            current = copy.deepcopy(dict(self._load_state()))
            duplicate = duplicate_result(current, command_id)
            if duplicate is not None:
                return GameOperationsResult("OK", duplicate)
            state = copy.deepcopy(dict(self._default_state()))
            state["state_revision"] = current_revision(current)
            revision = assign_next_revision(state)
            metadata = command_metadata(
                incoming,
                action="new_broadcast",
                state_revision=revision,
            )
            result_data = attach_metadata({"state": copy.deepcopy(state)}, metadata)
            remember_command(state, command_id, metadata=metadata, result=result_data)
            self._save_state(state)
            return GameOperationsResult("OK", result_data)

