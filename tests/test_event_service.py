from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from canonical_state_service import CanonicalStateFoundation
from event_service import EventService


class RecordingLock:
    def __init__(self) -> None:
        self.events: list[str] = []

    def __enter__(self):
        self.events.append("enter")
        return self

    def __exit__(self, exc_type, exc, tb):
        self.events.append("exit")
        return False


def base_state() -> dict[str, Any]:
    return {
        "broadcast_id": "B1",
        "status": "planned",
        "broadcast_phase": "pregame",
        "game_data_authority": "broadcaster",
        "statistician_enabled": False,
        "home_team": "Home",
        "visitor_team": "Visitor",
        "home_school_id": "H",
        "visitor_school_id": "V",
        "home_score": 0,
        "visitor_score": 0,
        "possession": "home",
        "down": "1st",
        "distance": "10",
        "ball_spot": "LEFT 20",
        "quarter": "1",
        "clock_seconds": 720,
        "clock_running": False,
        "next_play_number": 1,
        "events": [],
        "plays": [],
        "history": [],
        "correction_log": [],
        "last_event": {},
        "player_graphic": {"visible": False},
    }


def build_service(state: dict[str, Any] | None = None):
    store = copy.deepcopy(state or base_state())
    calls: dict[str, list[Any]] = {
        "saved": [],
        "history": [],
        "linked": [],
        "graphics": [],
        "penalty": [],
    }
    lock = RecordingLock()
    players = {
        "P1": {"id": "P1", "number": "7", "preferred_name": "Alex Runner"},
        "QB": {"id": "QB", "number": "12", "preferred_name": "Sam Passer"},
    }

    def load_state():
        return copy.deepcopy(store)

    def save_state(value):
        store.clear()
        store.update(copy.deepcopy(dict(value)))
        calls["saved"].append(copy.deepcopy(store))
        return copy.deepcopy(store)

    def push_history(value):
        calls["history"].append(copy.deepcopy(value))
        snapshot = {k: copy.deepcopy(v) for k, v in value.items() if k != "history"}
        value.setdefault("history", []).append(snapshot)

    def automation_player(roster_id: str, player_id: str):
        return ({"id": roster_id, "school_id": "H", "sport": "Football"}, players.get(player_id))

    def manual_player(data, team_name):
        if not isinstance(data, dict) or not data.get("number"):
            return None
        return {
            "id": "",
            "number": str(data["number"]),
            "preferred_name": str(data.get("name") or team_name),
        }

    def show_graphic(*args, **kwargs):
        calls["graphics"].append((args, kwargs))
        args[0]["player_graphic"] = {"visible": True, "eyebrow": kwargs.get("eyebrow", "")}

    def apply_penalty(value, category, name, yards, outcome):
        calls["penalty"].append((category, name, yards, outcome))
        if outcome == "accepted" and category == "Defensive":
            value["down"] = "1st"
            value["distance"] = "10"
        return {"applied": outcome == "accepted", "yards": yards}

    service = EventService(
        load_state=load_state,
        save_state=save_state,
        public_state=lambda value: {**copy.deepcopy(dict(value)), "public": True},
        push_history=push_history,
        update_linked_status=lambda broadcast_id, status, extra=None: calls["linked"].append((broadcast_id, status, extra)),
        automation_player=automation_player,
        manual_player=manual_player,
        player_display=lambda player: str((player or {}).get("preferred_name", "")),
        show_player_graphic=show_graphic,
        apply_penalty=apply_penalty,
        spot_to_coord=lambda value: 20,
        team_direction=lambda value, team: 1,
        normalize_state=lambda value: copy.deepcopy(dict(value)),
        default_player_graphic=lambda: {"visible": False},
        transaction_lock=lock,
        now=lambda: 1000.25,
    )
    return service, store, calls, lock


def pending_try_state(team: str, score: int = 6) -> dict[str, Any]:
    state = base_state()
    state[f"{team}_score"] = score
    CanonicalStateFoundation.enter_pending_try(state, team)
    return state


def test_source_allowed_uses_active_authority() -> None:
    state = {"game_data_authority": "statistician"}
    assert EventService.source_allowed(state, "statistician")
    assert not EventService.source_allowed(state, "broadcaster")


def test_locked_payload_identifies_authority() -> None:
    payload = EventService.locked_payload({"game_data_authority": "statistician"})
    assert payload["error"] == "CONTROL_SOURCE_LOCKED"
    assert payload["authority"] == "statistician"


def test_control_source_rejects_invalid_authority() -> None:
    service, _, _, _ = build_service()
    assert service.set_control_source("producer").code == "INVALID_CONTROL_SOURCE"


def test_control_source_updates_state_with_history_and_lock() -> None:
    service, store, calls, lock = build_service()
    result = service.set_control_source("statistician")
    assert result.ok
    assert store["game_data_authority"] == "statistician"
    assert store["statistician_enabled"] is True
    assert calls["history"]
    assert lock.events == ["enter", "exit"]


def test_trigger_rejects_invalid_event() -> None:
    service, _, _, _ = build_service()
    assert service.trigger({"team": "home", "event": "BAD"}).code == "INVALID_EVENT"


def test_trigger_requires_active_broadcast() -> None:
    state = base_state()
    state["broadcast_id"] = ""
    service, _, _, _ = build_service(state)
    assert service.trigger({"team": "home", "event": "TD"}).code == "NO_ACTIVE_BROADCAST"


def test_trigger_enforces_control_source() -> None:
    state = base_state()
    state["game_data_authority"] = "statistician"
    service, _, _, _ = build_service(state)
    result = service.trigger({"team": "home", "event": "TD", "source": "broadcaster"})
    assert result.code == "CONTROL_SOURCE_LOCKED"
    assert result.data["authority"] == "statistician"


def test_touchdown_scores_and_creates_event_and_play() -> None:
    service, store, calls, _ = build_service()
    result = service.trigger({"team": "home", "event": "TD", "player_id": "P1", "play_type": "rush"})
    assert result.ok
    assert store["home_score"] == 6
    assert store["status"] == "live"
    assert store["events"][0]["event"] == "TD"
    assert store["plays"][0]["touchdown"] is True
    assert store["next_play_number"] == 2
    assert calls["linked"] == [("B1", "live", None)]


def test_turnover_return_touchdown_scores_and_changes_possession() -> None:
    service, store, _, _ = build_service()
    result = service.trigger({"team": "visitor", "event": "TURNOVER", "turnover_type": "interception", "return_td": True})
    assert result.ok
    assert store["visitor_score"] == 6
    assert store["possession"] == "visitor"
    assert result.data["trigger"]["label"] == "Defensive Touchdown"


def test_first_down_resets_down_and_distance() -> None:
    state = base_state()
    state["down"] = "3rd"
    state["distance"] = "4"
    service, store, _, _ = build_service(state)
    service.trigger({"team": "home", "event": "FIRST_DOWN"})
    assert store["down"] == "1st"
    assert store["distance"] == "10"


def test_penalty_delegates_enforcement() -> None:
    service, store, calls, _ = build_service()
    result = service.trigger({"team": "visitor", "event": "PENALTY", "penalty_category": "Defensive", "penalty_name": "Holding", "penalty_yards": 10, "penalty_outcome": "accepted"})
    assert result.ok
    assert calls["penalty"] == [("Defensive", "Holding", 10, "accepted")]
    assert result.data["trigger"]["penalty"]["enforcement"]["applied"] is True
    assert store["down"] == "1st"


def test_play_turnover_changes_possession() -> None:
    service, store, _, _ = build_service()
    service.trigger({"team": "home", "event": "PLAY", "play_type": "pass", "pass_outcome": "interception", "statistician_mode": True})
    assert store["possession"] == "visitor"
    assert store["plays"][0]["turnover"] is True


def test_touchdown_player_graphic_is_requested() -> None:
    service, store, calls, _ = build_service()
    service.trigger({"team": "home", "event": "TD", "player_id": "P1", "graphic_duration": 8})
    assert calls["graphics"]
    assert store["player_graphic"]["visible"] is True


def test_touchdown_ignores_stale_player_id_when_submitted_number_differs() -> None:
    service, store, calls, _ = build_service()
    result = service.trigger({
        "team": "home",
        "event": "TD",
        "player_id": "P1",
        "play_type": "rush",
        "manual_player": {"number": "88", "name": ""},
        "graphic_duration": 8,
    })

    assert result.ok
    assert calls["graphics"] == []
    assert store["events"][0]["automation"]["player_id"] == ""
    assert store["events"][0]["automation"]["player_number"] == "88"
    assert store["events"][0]["automation"]["player_name"] == "Home"


def test_sack_triggers_player_spotlight() -> None:
    # PLAY events are entered against the offense (team in possession) --
    # base_state() has home on offense. The sacking (defensive) player is
    # still whoever is resolved via player_id/roster_id, independent of
    # `team`, exactly like the existing return_td turnover case.
    service, store, calls, _ = build_service()
    result = service.trigger({
        "team": "home",
        "event": "PLAY",
        "play_type": "pass",
        "pass_outcome": "sack",
        "player_id": "P1",
        "graphic_duration": 6,
    })
    assert result.ok
    assert calls["graphics"]
    _, kwargs = calls["graphics"][-1]
    assert kwargs["eyebrow"] == "SACK"
    assert kwargs["defensive"] is True
    assert store["player_graphic"]["visible"] is True


def test_turnover_without_return_touchdown_triggers_player_spotlight() -> None:
    service, store, calls, _ = build_service()
    result = service.trigger({
        "team": "visitor",
        "event": "TURNOVER",
        "turnover_type": "interception",
        "player_id": "P1",
        "graphic_duration": 6,
    })
    assert result.ok
    assert calls["graphics"]
    _, kwargs = calls["graphics"][-1]
    assert kwargs["eyebrow"] == "TURNOVER"
    assert kwargs["defensive"] is True
    assert store["player_graphic"]["visible"] is True


def test_first_down_triggers_player_spotlight() -> None:
    service, store, calls, _ = build_service()
    result = service.trigger({
        "team": "home",
        "event": "FIRST_DOWN",
        "player_id": "P1",
        "graphic_duration": 6,
    })
    assert result.ok
    assert calls["graphics"]
    _, kwargs = calls["graphics"][-1]
    assert kwargs["eyebrow"] == "FIRST DOWN"
    assert kwargs["defensive"] is False
    assert store["player_graphic"]["visible"] is True


def test_touchdown_player_graphic_carries_submitted_sponsor_id() -> None:
    service, _, calls, _ = build_service()
    service.trigger({
        "team": "home",
        "event": "TD",
        "player_id": "P1",
        "graphic_duration": 8,
        "sponsor_id": "SPONSOR-1",
    })
    assert calls["graphics"]
    _, kwargs = calls["graphics"][-1]
    assert kwargs["sponsor_id"] == "SPONSOR-1"


def test_quick_correction_rejects_invalid_down() -> None:
    state = base_state()
    state["game_data_authority"] = "statistician"
    service, _, _, _ = build_service(state)
    assert service.quick_correction({"down": "5th"}).code == "INVALID_DOWN"


def test_quick_correction_updates_fields_and_logs_change() -> None:
    state = base_state()
    state["game_data_authority"] = "statistician"
    service, store, _, _ = build_service(state)
    result = service.quick_correction({"down": "2nd", "distance": 7, "possession": "visitor", "ball_spot": "RIGHT 30"})
    assert result.ok
    assert store["down"] == "2nd"
    assert store["distance"] == "7"
    assert store["possession"] == "visitor"
    assert store["correction_log"][-1]["kind"] == "quick_correction"


def test_edit_reports_missing_event() -> None:
    state = base_state()
    state["game_data_authority"] = "statistician"
    service, _, _, _ = build_service(state)
    assert service.edit("missing", {}).code == "EVENT_NOT_FOUND"


def test_edit_updates_event_and_linked_play() -> None:
    state = base_state()
    state["game_data_authority"] = "statistician"
    state["events"] = [{"id": "E1", "play_id": "P1", "description": "Run", "automation": {}, "after": {}}]
    state["plays"] = [{"event_id": "E1", "play_id": "P1", "result": "Run"}]
    service, store, _, _ = build_service(state)
    result = service.edit("E1", {"description": "Corrected run", "yards": 12})
    assert result.ok
    assert store["events"][0]["description"] == "Corrected run"
    assert store["plays"][0]["result"] == "Corrected run"
    assert store["plays"][0]["yards"] == 12
    assert store["correction_log"][-1]["kind"] == "event_edit"


def test_corrections_are_newest_first_and_detached() -> None:
    state = base_state()
    state["correction_log"] = [{"id": "1"}, {"id": "2"}]
    service, store, _, _ = build_service(state)
    result = service.corrections()
    result.data["corrections"][0]["id"] = "changed"
    assert [row["id"] for row in service.corrections().data["corrections"]] == ["2", "1"]
    assert store["correction_log"][1]["id"] == "2"


def test_undo_restores_event_before_state_and_removes_records() -> None:
    state = base_state()
    state["home_score"] = 6
    state["next_play_number"] = 2
    state["events"] = [{"id": "E1", "play_id": "P1", "play_number": 1, "label": "Touchdown", "before": {"home_score": 0, "visitor_score": 0, "possession": "home", "down": "1st", "distance": "10", "ball_spot": "LEFT 20", "quarter": "1"}, "after": {"home_score": 6}}]
    state["plays"] = [{"event_id": "E1", "play_id": "P1"}]
    service, store, _, _ = build_service(state)
    result = service.undo()
    assert result.ok
    assert store["home_score"] == 0
    assert store["events"] == []
    assert store["plays"] == []
    assert store["next_play_number"] == 1
    assert store["correction_log"][-1]["kind"] == "undo"


def test_undo_falls_back_to_history_snapshot() -> None:
    state = base_state()
    previous = copy.deepcopy(state)
    previous["down"] = "2nd"
    state["down"] = "3rd"
    state["history"] = [previous]
    service, store, _, _ = build_service(state)
    service.undo()
    assert store["down"] == "2nd"
    assert store["history"] == []


def test_extra_point_no_good_records_event_without_score_change() -> None:
    service, store, _, _ = build_service(pending_try_state("home", 6))
    result = service.trigger({
        "team": "home",
        "event": "XP",
        "player_id": "P1",
        "conversion_outcome": "no_good",
    })
    assert result.ok
    assert store["home_score"] == 6
    event = store["events"][0]
    assert event["score_delta"] == 0
    assert event["conversion_outcome"] == "no_good"
    assert event["label"] == "Extra Point No Good"
    assert "no good" in event["description"].lower()


def test_two_point_failed_records_event_without_score_change() -> None:
    service, store, _, _ = build_service(pending_try_state("visitor", 6))
    result = service.trigger({
        "team": "visitor",
        "event": "2PT",
        "player_id": "P1",
        "play_type": "rush",
        "conversion_outcome": "failed",
    })
    assert result.ok
    assert store["visitor_score"] == 6
    event = store["events"][0]
    assert event["score_delta"] == 0
    assert event["conversion_outcome"] == "failed"
    assert event["label"] == "Two-Point Conversion Failed"


def test_successful_conversion_outcomes_award_points() -> None:
    service, store, _, _ = build_service(pending_try_state("home", 6))
    assert service.trigger({"team": "home", "event": "XP", "conversion_outcome": "good"}).ok
    assert store["home_score"] == 7

    service, store, _, _ = build_service(pending_try_state("visitor", 6))
    assert service.trigger({"team": "visitor", "event": "2PT", "conversion_outcome": "good"}).ok
    assert store["visitor_score"] == 8


def test_invalid_conversion_outcome_is_rejected() -> None:
    service, store, _, _ = build_service(pending_try_state("home", 6))
    result = service.trigger({"team": "home", "event": "XP", "conversion_outcome": "failed"})
    assert result.code == "INVALID_CONVERSION_OUTCOME"
    assert store["home_score"] == 6


