from __future__ import annotations

import copy
from typing import Any, Callable

from flask import Blueprint, jsonify, request

from live_command_service import (
    assign_next_revision,
    attach_metadata,
    command_id_from,
    command_metadata,
    duplicate_result,
    remember_command,
)


def create_coin_toss_blueprint(
    *,
    require_auth: Callable,
    load_state: Callable[[], dict[str, Any]],
    save_state: Callable[[dict[str, Any]], None],
    public_state: Callable[[dict[str, Any]], dict[str, Any]],
    transaction_lock: Any,
    clock: Callable[[], float],
) -> Blueprint:
    routes = Blueprint("coin_toss_routes", __name__)

    def team_name(state: dict[str, Any], key: str) -> str:
        return str(state.get(f"{key}_team") or key.title())

    def other(team: str) -> str:
        return "visitor" if team == "home" else "home"

    def active_events_after(state: dict[str, Any], stamp: float) -> list[dict[str, Any]]:
        return [
            event for event in (state.get("events") or [])
            if isinstance(event, dict)
            and not event.get("undone")
            and float(event.get("created_at") or 0) > stamp
        ]

    def authority_error(state: dict[str, Any], source: str):
        authority = str(state.get("game_data_authority") or "broadcaster")
        if source != authority:
            return jsonify({
                "error": "GAME_DATA_LOCKED",
                "message": f"Coin toss setup is controlled by the {authority} console.",
            }), 409
        return None

    def eligible(state: dict[str, Any]) -> bool:
        if not state.get("broadcast_created"):
            return False
        if str(state.get("quarter") or "1") != "1":
            return False
        if int(state.get("home_score") or 0) != 0 or int(state.get("visitor_score") or 0) != 0:
            return False
        # Coin toss is a setup action and must precede a game event/play.
        if any(not event.get("undone") for event in (state.get("events") or []) if isinstance(event, dict)):
            return False
        return True

    @routes.post("/api/coin-toss")
    @require_auth
    def record_coin_toss():
        payload = request.get_json(silent=True) or {}
        command_id = command_id_from(payload)
        source = str(payload.get("source") or "broadcaster").lower()
        winner = str(payload.get("winner") or "").lower()
        election = str(payload.get("election") or "").lower()
        direction = str(payload.get("opening_drive_direction") or "right").lower()
        edit = bool(payload.get("edit"))

        if winner not in {"home", "visitor"}:
            return jsonify({"error": "COIN_TOSS_WINNER_REQUIRED", "message": "Select the team that won the coin toss."}), 400
        if election not in {"receive", "defer", "kick", "defend"}:
            return jsonify({"error": "COIN_TOSS_ELECTION_REQUIRED", "message": "Select what the coin-toss winner elected to do."}), 400
        if direction not in {"left", "right"}:
            return jsonify({"error": "COIN_TOSS_DIRECTION_REQUIRED", "message": "Select the opening receiving team's direction."}), 400

        with transaction_lock:
            state = load_state()
            duplicate = duplicate_result(state, command_id)
            if duplicate is not None:
                return jsonify(duplicate)
            locked = authority_error(state, source)
            if locked:
                return locked

            existing = state.get("coin_toss") if isinstance(state.get("coin_toss"), dict) else {}
            recorded = existing.get("recorded") is True
            if recorded and not edit:
                return jsonify({"error": "COIN_TOSS_ALREADY_RECORDED", "message": "The coin toss is already recorded. Use Edit Coin Toss before kickoff."}), 409
            if not eligible(state):
                return jsonify({"error": "COIN_TOSS_WINDOW_CLOSED", "message": "Coin toss setup is only available before the first game event."}), 409
            if edit and not recorded:
                return jsonify({"error": "COIN_TOSS_NOT_RECORDED", "message": "There is no recorded coin toss to edit."}), 409
            if recorded and active_events_after(state, float(existing.get("recorded_at") or 0)):
                return jsonify({"error": "COIN_TOSS_EDIT_BLOCKED", "message": "The coin toss cannot be edited after a later game event. Undo later events first."}), 409

            winner_other = other(winner)
            opening_receiver = winner if election == "receive" else winner_other
            second_half_receiver = winner if election == "defer" else winner_other

            opening_override = str(payload.get("opening_receiving_team") or "").lower()
            second_override = str(payload.get("second_half_receiving_team") or "").lower()
            if opening_override in {"home", "visitor"}:
                opening_receiver = opening_override
            if second_override in {"home", "visitor"}:
                second_half_receiver = second_override
            opening_kicker = other(opening_receiver)

            tracked = (
                "home_direction", "visitor_direction", "possession", "down", "distance",
                "special_game_phase", "kicking_team", "receiving_team", "second_half_receiving_team",
            )
            if recorded and isinstance(existing.get("before"), dict):
                before = copy.deepcopy(existing["before"])
                recorded_at = float(existing.get("recorded_at") or clock())
            else:
                before = {key: {"present": key in state, "value": copy.deepcopy(state.get(key))} for key in tracked}
                recorded_at = float(clock())

            # Direction is expressed as the direction the opening receiver's offense will drive.
            state[f"{opening_receiver}_direction"] = direction
            state[f"{opening_kicker}_direction"] = "left" if direction == "right" else "right"
            state["possession"] = opening_receiver
            state["down"] = "Off"
            state["distance"] = "Off"
            state["special_game_phase"] = "kickoff"
            state["kicking_team"] = opening_kicker
            state["receiving_team"] = opening_receiver
            state["second_half_receiving_team"] = second_half_receiver

            summary = (
                f"{team_name(state, winner)} won the toss and elected {election}; "
                f"{team_name(state, opening_receiver)} receives the opening kickoff; "
                f"{team_name(state, second_half_receiver)} receives to start the second half."
            )
            state["coin_toss"] = {
                "recorded": True,
                "winner": winner,
                "winner_name": team_name(state, winner),
                "election": election,
                "opening_receiving_team": opening_receiver,
                "opening_kicking_team": opening_kicker,
                "second_half_receiving_team": second_half_receiver,
                "opening_drive_direction": direction,
                "summary": summary,
                "source": source,
                "recorded_at": recorded_at,
                "updated_at": float(clock()),
                "before": before,
            }
            revision = assign_next_revision(state)
            metadata = command_metadata(
                payload,
                action="coin_toss_record",
                state_revision=revision,
            )
            result_data = attach_metadata(
                {
                    "state": public_state(state),
                    "coin_toss": copy.deepcopy(state["coin_toss"]),
                    "message": summary + " Opening kickoff is now required.",
                },
                metadata,
            )
            remember_command(state, command_id, metadata=metadata, result=result_data)
            save_state(state)
            return jsonify(result_data)

    @routes.post("/api/coin-toss/undo")
    @require_auth
    def undo_coin_toss():
        payload = request.get_json(silent=True) or {}
        command_id = command_id_from(payload)
        with transaction_lock:
            state = load_state()
            duplicate = duplicate_result(state, command_id)
            if duplicate is not None:
                return jsonify(duplicate)
            toss = state.get("coin_toss") if isinstance(state.get("coin_toss"), dict) else {}
            if toss.get("recorded") is not True:
                return jsonify({"error": "COIN_TOSS_NOT_RECORDED", "message": "No recorded coin toss is available to undo."}), 409
            stamp = float(toss.get("recorded_at") or 0)
            if active_events_after(state, stamp):
                return jsonify({"error": "COIN_TOSS_NOT_NEXT_UNDO", "message": "A later game event must be undone before the coin toss can be undone."}), 409
            before = toss.get("before") if isinstance(toss.get("before"), dict) else {}
            for key, entry in before.items():
                if isinstance(entry, dict) and entry.get("present"):
                    state[key] = copy.deepcopy(entry.get("value"))
                else:
                    state.pop(key, None)
            state["coin_toss"] = {"recorded": False, "undone_at": float(clock())}
            revision = assign_next_revision(state)
            metadata = command_metadata(
                payload,
                action="coin_toss_undo",
                state_revision=revision,
            )
            result_data = attach_metadata(
                {
                    "state": public_state(state),
                    "message": "Coin toss undone. Coin toss setup is required again.",
                },
                metadata,
            )
            remember_command(state, command_id, metadata=metadata, result=result_data)
            save_state(state)
            return jsonify(result_data)

    return routes
