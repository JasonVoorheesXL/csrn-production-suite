from __future__ import annotations

import copy
from contextlib import nullcontext
from typing import Any

from game_operations_service import GameOperationsService


def base_state() -> dict[str, Any]:
    return {
        "broadcast_created": True,
        "broadcast_id": "FB-2026-01",
        "sport": "Football",
        "season": "2026",
        "week": "1",
        "classification": "5A",
        "level": "Varsity",
        "division": "Boys",
        "home_team": "Caledonia",
        "visitor_team": "New Hope",
        "home_school_id": "caledonia",
        "visitor_school_id": "new-hope",
        "home_identity": {"name": "Caledonia"},
        "visitor_identity": {"name": "New Hope"},
        "venue_id": "caledonia-football",
        "venue": "Caledonia High School",
        "date": "2026-08-21",
        "scheduled_start": "19:00",
        "visual_mode": "graphic",
        "crew": {"play_by_play": "Jason"},
        "status": "planned",
        "broadcast_phase": "pregame",
        "home_score": 0,
        "visitor_score": 0,
        "quarter": "1",
        "down": "1st",
        "distance": "10",
        "possession": "home",
        "clock_visible": False,
        "scorebug_visible": False,
        "ticker_visible": True,
        "ticker_speed": "slow",
        "ticker_pause": 2,
        "history": [],
        "events": [{"id": "evt-1"}],
        "plays": [{"play_id": "play-1"}],
        "review_mode": False,
    }


def default_state() -> dict[str, Any]:
    return {
        "broadcast_created": False,
        "broadcast_id": "",
        "sport": "Football",
        "season": "",
        "week": "1",
        "classification": "",
        "level": "Varsity",
        "division": "Boys",
        "home_team": "Caledonia",
        "visitor_team": "Visitor",
        "home_school_id": "",
        "visitor_school_id": "",
        "home_identity": {},
        "visitor_identity": {},
        "venue_id": "",
        "venue": "Caledonia High School",
        "date": "",
        "scheduled_start": "",
        "visual_mode": "graphic",
        "crew": {},
        "status": "planned",
        "broadcast_phase": "pregame",
        "home_score": 0,
        "visitor_score": 0,
        "quarter": "1",
        "down": "1st",
        "distance": "Off",
        "possession": "home",
        "clock_visible": False,
        "scorebug_visible": False,
        "ticker_visible": True,
        "ticker_speed": "slow",
        "ticker_pause": 2,
        "history": [],
        "events": [],
        "plays": [],
        "review_mode": False,
    }


def build_service(
    state: dict[str, Any] | None = None,
    *,
    allowed: bool = True,
    controlled_commands: bool = False,
    command_error: Exception | None = None,
):
    current = copy.deepcopy(state or base_state())
    saved: list[dict[str, Any]] = []
    linked: list[tuple[Any, ...]] = []
    commands: list[bool] = []
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

    def update_linked_status(*args: Any) -> None:
        linked.append(tuple(copy.deepcopy(args)))

    def command_scorebug_visibility(visible: bool) -> None:
        commands.append(visible)
        if command_error is not None:
            raise command_error

    service = GameOperationsService(
        load_state=load_state,
        save_state=save_state,
        default_state=default_state,
        push_history=push_history,
        source_allowed=lambda _state, _source: allowed,
        locked_payload=lambda incoming: {
            "error": "CONTROL_SOURCE_LOCKED",
            "authority": incoming.get("game_data_authority", "broadcaster"),
        },
        update_linked_status=update_linked_status,
        load_config=lambda: {
            "obs": {"controlled_commands": controlled_commands}
        },
        command_scorebug_visibility=command_scorebug_visibility,
        transaction_lock=nullcontext(),
    )
    return service, current, saved, linked, commands, history_calls


def test_score_rejects_invalid_team() -> None:
    service, _, saved, _, _, _ = build_service()
    result = service.score({"team": "neutral", "delta": 1})
    assert result.code == "INVALID_SCORE_REQUEST"
    assert saved == []


def test_score_rejects_invalid_delta_without_exception() -> None:
    service, _, saved, _, _, _ = build_service()
    result = service.score({"team": "home", "delta": "six"})
    assert result.code == "INVALID_SCORE_REQUEST"
    assert saved == []


def test_score_respects_control_authority() -> None:
    state = base_state()
    state["game_data_authority"] = "statistician"
    service, _, saved, _, _, _ = build_service(state, allowed=False)
    result = service.score({"team": "home", "delta": 6})
    assert result.code == "CONTROL_SOURCE_LOCKED"
    assert result.data["authority"] == "statistician"
    assert saved == []


def test_score_updates_score_marks_live_and_links_broadcast() -> None:
    service, current, saved, linked, _, history = build_service()
    result = service.score({"team": "home", "delta": 6})
    assert result.ok
    assert current["home_score"] == 6
    assert current["broadcast_phase"] == "live"
    assert current["status"] == "live"
    assert len(saved) == 2
    assert linked == [("FB-2026-01", "live")]
    assert len(history) == 1


def test_score_never_drops_below_zero() -> None:
    service, current, _, _, _, _ = build_service()
    service.score({"team": "visitor", "delta": -1})
    assert current["visitor_score"] == 0


def test_set_values_ignores_unknown_fields() -> None:
    service, current, _, _, _, _ = build_service()
    result = service.set_values({"ticker_speed": "fast", "unsafe": "value"})
    assert result.ok
    assert current["ticker_speed"] == "fast"
    assert "unsafe" not in current
    assert result.data["changes"] == {"ticker_speed": "fast"}


def test_set_values_respects_authority_for_game_fields() -> None:
    state = base_state()
    state["game_data_authority"] = "statistician"
    service, _, saved, _, _, _ = build_service(state, allowed=False)
    result = service.set_values({"quarter": "2", "source": "broadcaster"})
    assert result.code == "CONTROL_SOURCE_LOCKED"
    assert saved == []


def test_set_values_persists_and_records_history() -> None:
    service, current, saved, _, _, history = build_service()
    result = service.set_values({"quarter": "2", "possession": "visitor"})
    assert result.ok
    assert current["quarter"] == "2"
    assert current["possession"] == "visitor"
    assert len(saved) == 1
    assert len(history) == 1


def test_toggle_scorebug_without_obs_command() -> None:
    service, current, _, _, commands, history = build_service()
    result = service.toggle_scorebug()
    assert result.ok
    assert current["scorebug_visible"] is True
    assert current["broadcast_id"] == "FB-2026-01"
    assert commands == []
    assert len(history) == 1


def test_toggle_scorebug_executes_controlled_obs_command() -> None:
    service, current, _, _, commands, _ = build_service(
        controlled_commands=True
    )
    result = service.toggle_scorebug()
    assert result.ok
    assert commands == [True]
    assert current["scorebug_visible"] is True


def test_toggle_scorebug_command_failure_does_not_mutate_state() -> None:
    service, current, saved, _, commands, history = build_service(
        controlled_commands=True,
        command_error=RuntimeError("OBS unavailable"),
    )
    result = service.toggle_scorebug()
    assert result.code == "OBS_COMMAND_BLOCKED"
    assert result.data["message"] == "OBS unavailable"
    assert commands == [True]
    assert current["scorebug_visible"] is False
    assert saved == []
    assert history == []


def test_toggle_halftime_enters_halftime_and_hides_scorebug() -> None:
    state = base_state()
    state["broadcast_phase"] = "live"
    state["scorebug_visible"] = True
    service, current, _, _, _, _ = build_service(state)
    service.toggle_halftime()
    assert current["broadcast_phase"] == "halftime"
    assert current["scorebug_visible"] is False


def test_toggle_halftime_resumes_third_quarter() -> None:
    state = base_state()
    state["broadcast_phase"] = "halftime"
    state["quarter"] = "2"
    service, current, _, _, _, _ = build_service(state)
    service.toggle_halftime()
    assert current["broadcast_phase"] == "live"
    assert current["quarter"] == "3"
    assert current["scorebug_visible"] is True


def test_end_game_sets_final_state_and_linked_scores() -> None:
    state = base_state()
    state["home_score"] = 21
    state["visitor_score"] = 14
    state["scorebug_visible"] = True
    service, current, _, linked, _, history = build_service(state)
    result = service.end_game()
    assert result.ok
    assert current["broadcast_phase"] == "final"
    assert current["status"] == "completed"
    assert current["scorebug_visible"] is False
    assert linked == [
        (
            "FB-2026-01",
            "completed",
            {"final_home_score": 21, "final_visitor_score": 14},
        )
    ]
    assert len(history) == 1


def test_reset_data_preserves_selected_broadcast_identity() -> None:
    state = base_state()
    state["home_score"] = 35
    state["events"] = [{"id": "evt-9"}]
    service, current, _, _, _, _ = build_service(state)
    result = service.reset_data()
    assert result.ok
    assert current["broadcast_id"] == "FB-2026-01"
    assert current["home_team"] == "Caledonia"
    assert current["visitor_team"] == "New Hope"
    assert current["home_score"] == 0
    assert current["events"] == []
    assert current["broadcast_phase"] == "pregame"
    assert current["broadcast_created"] is True


def test_reset_completed_game_preserves_review_mode() -> None:
    state = base_state()
    state["status"] = "completed"
    service, current, _, _, _, _ = build_service(state)
    service.reset_data()
    assert current["status"] == "completed"
    assert current["broadcast_phase"] == "final"
    assert current["review_mode"] is True
    assert current["scorebug_visible"] is False


def test_new_broadcast_restores_complete_default_state() -> None:
    service, current, saved, _, _, _ = build_service()
    result = service.new_broadcast()
    assert result.ok
    assert current == default_state()
    assert saved == [default_state()]
