from __future__ import annotations

import copy
import threading
from typing import Any

from rules_service import RulesService


def base_state() -> dict[str, Any]:
    return {
        "broadcast_id": "FB-2026-01",
        "status": "planned",
        "broadcast_phase": "pregame",
        "sport": "Football",
        "home_team": "Caledonia",
        "visitor_team": "New Hope",
        "home_school_id": "caledonia",
        "visitor_school_id": "new-hope",
        "home_score": 0,
        "visitor_score": 0,
        "possession": "home",
        "down": "1st",
        "distance": "10",
        "ball_spot": "LEFT 20",
        "quarter": "1",
        "clock_seconds": 720,
        "clock_running": False,
        "clock_started_at": 0,
        "clock_visible": True,
        "home_direction": "right",
        "visitor_direction": "left",
        "game_data_authority": "statistician",
        "next_play_number": 1,
        "events": [],
        "plays": [],
        "history": [],
        "player_graphic": {"visible": False},
    }


def build_service(
    state: dict[str, Any] | None = None,
    *,
    allowed: bool = True,
):
    current = copy.deepcopy(state or base_state())
    saved: list[dict[str, Any]] = []
    graphics: list[dict[str, Any]] = []
    history_calls: list[dict[str, Any]] = []

    def load_state() -> dict[str, Any]:
        return copy.deepcopy(current)

    def save_state(incoming: dict[str, Any]) -> None:
        current.clear()
        current.update(copy.deepcopy(incoming))
        saved.append(copy.deepcopy(incoming))

    def push_history(incoming: dict[str, Any]) -> None:
        history_calls.append(copy.deepcopy(incoming))
        incoming.setdefault("history", []).append({"snapshot": True})

    def resolve_player(_state: dict[str, Any], team: str, number: Any):
        text = str(number or "").strip()
        known = {
            ("home", "12"): "Jason Quarterback",
            ("home", "22"): "Jordan Runner",
            ("home", "7"): "Caledonia Kicker",
            ("visitor", "4"): "New Hope Returner",
            ("visitor", "55"): "New Hope Defender",
        }
        return {
            "number": text,
            "name": known.get((team, text), ""),
            "resolved": (team, text) in known,
            "roster_id": f"{team}-roster" if text else "",
            "player_id": f"{team}-{text}" if text else "",
        }

    def show_player_graphic(
        incoming_state: dict[str, Any],
        roster: dict[str, Any],
        player: dict[str, Any],
        graphic_type: str,
        duration: int,
        **kwargs: Any,
    ) -> None:
        graphics.append(
            {
                "roster": copy.deepcopy(roster),
                "player": copy.deepcopy(player),
                "graphic_type": graphic_type,
                "duration": duration,
                **copy.deepcopy(kwargs),
            }
        )
        incoming_state["player_graphic"] = {
            "visible": True,
            "player_number": player.get("number", ""),
        }

    service = RulesService(
        load_state=load_state,
        save_state=save_state,
        push_history=push_history,
        source_allowed=lambda _state, source: allowed and source == "statistician",
        locked_payload=lambda incoming: {
            "error": "CONTROL_SOURCE_LOCKED",
            "authority": incoming.get("game_data_authority", "broadcaster"),
        },
        resolve_player=resolve_player,
        show_player_graphic=show_player_graphic,
        # play() acquires/releases this directly (for lock-wait-time
        # diagnostics) rather than only using it as a context manager, so it
        # needs a real Lock -- nullcontext() has no .acquire()/.release().
        transaction_lock=threading.Lock(),
        now=lambda: 1_700_000_000.125,
    )
    return service, current, saved, graphics, history_calls


def test_field_coordinate_helpers_cover_named_and_numeric_spots() -> None:
    assert RulesService.spot_to_coord("LEFT GOAL") == 0
    assert RulesService.spot_to_coord("right 20") == 80
    assert RulesService.spot_to_coord("home 35") == 35
    assert RulesService.spot_to_coord("visitor 35") == 65
    assert RulesService.spot_to_coord("bad") == 50
    assert RulesService.coord_to_spot(0) == "LEFT GOAL"
    assert RulesService.coord_to_spot(80) == "RIGHT 20"
    assert RulesService.coord_to_spot(50) == "50"


def test_team_helpers_preserve_direction_and_down_rules() -> None:
    state = base_state()
    assert RulesService.team_direction(state, "home") == 1
    assert RulesService.team_direction(state, "visitor") == -1
    assert RulesService.opposite("home") == "visitor"
    assert RulesService.advance_down("2nd") == "3rd"
    assert RulesService.advance_down("4th") == "4th"


def test_clock_start_sets_timestamp_and_persists() -> None:
    service, current, saved, _, _ = build_service()
    result = service.clock_control({"action": "start"})
    assert result.ok
    assert current["clock_running"] is True
    assert current["clock_started_at"] == 1_700_000_000
    assert len(saved) == 1


def test_clock_adjust_is_bounded() -> None:
    state = base_state()
    state["clock_seconds"] = 5
    service, current, _, _, _ = build_service(state)
    service.clock_control({"action": "adjust", "delta": -20})
    assert current["clock_seconds"] == 0
    service.clock_control({"action": "adjust", "delta": 5000})
    assert current["clock_seconds"] == 3599


def test_clock_reset_stops_clock_and_updates_visibility() -> None:
    state = base_state()
    state["clock_running"] = True
    state["clock_started_at"] = 99
    service, current, _, _, _ = build_service(state)
    service.clock_control({"action": "reset", "seconds": 600, "visible": False})
    assert current["clock_seconds"] == 600
    assert current["clock_running"] is False
    assert current["clock_started_at"] == 0
    assert current["clock_visible"] is False


def test_field_direction_updates_both_teams() -> None:
    service, current, _, _, _ = build_service()
    result = service.field_direction({"team": "visitor", "direction": "right"})
    assert result.ok
    assert current["visitor_direction"] == "right"
    assert current["home_direction"] == "left"


def test_field_direction_rejects_invalid_values_without_saving() -> None:
    service, _, saved, _, _ = build_service()
    result = service.field_direction({"team": "home", "direction": "up"})
    assert result.code == "INVALID_DIRECTION"
    assert saved == []


def test_play_rejects_invalid_team_or_kind() -> None:
    service, _, saved, _, _ = build_service()
    assert service.play({"team": "neutral", "play_type": "run"}).code == "INVALID_PLAY"
    assert service.play({"team": "home", "play_type": "field_goal"}).code == "INVALID_PLAY"
    assert saved == []


def test_play_requires_active_broadcast() -> None:
    state = base_state()
    state["broadcast_id"] = ""
    service, _, saved, _, _ = build_service(state)
    result = service.play({"team": "home", "play_type": "run"})
    assert result.code == "NO_ACTIVE_BROADCAST"
    assert saved == []


def test_play_enforces_statistician_control_source() -> None:
    state = base_state()
    state["game_data_authority"] = "broadcaster"
    service, _, saved, _, _ = build_service(state, allowed=False)
    result = service.play({"team": "home", "play_type": "run"})
    assert result.code == "CONTROL_SOURCE_LOCKED"
    assert result.data["authority"] == "broadcaster"
    assert saved == []


def test_run_first_down_creates_canonical_event_and_play() -> None:
    service, current, _, _, history = build_service()
    result = service.play(
        {
            "team": "home",
            "play_type": "run",
            "start_spot": "LEFT 20",
            "end_spot": "LEFT 35",
            "player_number": "22",
        }
    )
    assert result.ok
    assert current["down"] == "1st"
    assert current["distance"] == "10"
    assert current["ball_spot"] == "LEFT 35"
    assert result.data["play"]["yards"] == 15
    assert result.data["play"]["first_down"] is True
    assert result.data["play"]["play_id"] == "FB-2026-01-0001"
    assert current["events"][0]["play_id"] == result.data["play"]["play_id"]
    assert len(history) == 1


def test_run_touchdown_scores_and_triggers_player_graphic() -> None:
    service, current, _, graphics, _ = build_service()
    result = service.play(
        {
            "team": "home",
            "play_type": "run",
            "start_spot": "RIGHT 10",
            "end_spot": "RIGHT GOAL",
            "player_number": "22",
        }
    )
    assert result.ok
    assert current["home_score"] == 6
    assert result.data["play"]["touchdown"] is True
    assert result.data["play"]["label"] == "Touchdown Run"
    assert graphics[0]["player"]["number"] == "22"
    assert current["clock_running"] is False


def test_complete_pass_records_passer_and_receiver() -> None:
    service, _, _, _, _ = build_service()
    result = service.play(
        {
            "team": "home",
            "play_type": "pass",
            "pass_outcome": "complete",
            "start_spot": "LEFT 20",
            "end_spot": "LEFT 28",
            "passer_number": "12",
            "receiver_number": "22",
        }
    )
    play = result.data["play"]
    assert play["passer_name"] == "Jason Quarterback"
    assert play["receiver_name"] == "Jordan Runner"
    assert "complete to" in play["result"]


def test_incomplete_pass_keeps_spot_and_stops_clock() -> None:
    state = base_state()
    state["clock_running"] = True
    state["clock_started_at"] = 100
    service, current, _, _, _ = build_service(state)
    result = service.play(
        {
            "team": "home",
            "play_type": "pass",
            "pass_outcome": "incomplete",
            "start_spot": "LEFT 20",
            "end_spot": "LEFT 40",
            "passer_number": "12",
        }
    )
    assert result.data["play"]["yards"] == 0
    assert current["ball_spot"] == "LEFT 20"
    assert current["clock_running"] is False


def test_interception_changes_possession_and_resets_down() -> None:
    service, current, _, _, _ = build_service()
    result = service.play(
        {
            "team": "home",
            "play_type": "pass",
            "pass_outcome": "interception",
            "start_spot": "LEFT 20",
            "end_spot": "LEFT 30",
            "passer_number": "12",
        }
    )
    assert result.data["play"]["turnover"] is True
    assert current["possession"] == "visitor"
    assert current["down"] == "1st"
    assert current["distance"] == "10"


def test_safety_awards_two_points_to_opponent() -> None:
    state = base_state()
    state["ball_spot"] = "LEFT 2"
    service, current, _, _, _ = build_service(state)
    result = service.play(
        {
            "team": "home",
            "play_type": "run",
            "start_spot": "LEFT 2",
            "end_spot": "LEFT GOAL",
            "player_number": "22",
        }
    )
    assert result.data["play"]["safety"] is True
    assert current["visitor_score"] == 2
    assert current["possession"] == "visitor"


def test_failed_fourth_down_changes_possession() -> None:
    state = base_state()
    state["down"] = "4th"
    state["distance"] = "5"
    service, current, _, _, _ = build_service(state)
    result = service.play(
        {
            "team": "home",
            "play_type": "run",
            "start_spot": "LEFT 20",
            "end_spot": "LEFT 22",
            "player_number": "22",
        }
    )
    assert result.data["play"]["turnover"] is True
    assert current["possession"] == "visitor"
    assert current["down"] == "1st"


def test_kickoff_touchback_places_ball_at_receiving_twenty() -> None:
    service, current, _, _, _ = build_service()
    result = service.play(
        {
            "team": "home",
            "play_type": "kickoff",
            "start_spot": "LEFT 40",
            "landing_spot": "RIGHT GOAL",
            "end_spot": "RIGHT GOAL",
            "kicker_number": "7",
            "touchback": True,
        }
    )
    assert current["possession"] == "visitor"
    assert current["ball_spot"] == "RIGHT 20"
    assert result.data["play"]["landing_spot"] == "RIGHT GOAL"
    assert "touchback" in result.data["play"]["result"]


def test_punt_return_touchdown_scores_receiving_team() -> None:
    service, current, _, graphics, _ = build_service()
    result = service.play(
        {
            "team": "home",
            "play_type": "punt",
            "start_spot": "LEFT 20",
            "landing_spot": "RIGHT 30",
            "end_spot": "LEFT GOAL",
            "kicker_number": "7",
            "returner_number": "4",
        }
    )
    assert result.data["play"]["touchdown"] is True
    assert current["visitor_score"] == 6
    assert result.data["play"]["label"] == "Punt Return Touchdown"
    assert graphics[0]["player"]["number"] == "4"


def test_unknown_number_is_listed_as_unresolved() -> None:
    service, _, _, _, _ = build_service()
    result = service.play(
        {
            "team": "home",
            "play_type": "run",
            "start_spot": "LEFT 20",
            "end_spot": "LEFT 21",
            "player_number": "99",
        }
    )
    assert result.data["play"]["unresolved_players"] == ["player"]


def test_play_marks_game_live_and_advances_play_number() -> None:
    service, current, saved, _, _ = build_service()
    result = service.play(
        {
            "team": "home",
            "play_type": "run",
            "start_spot": "LEFT 20",
            "end_spot": "LEFT 21",
        }
    )
    assert result.ok
    assert current["status"] == "live"
    assert current["broadcast_phase"] == "live"
    assert current["next_play_number"] == 2
    assert len(saved) == 1


