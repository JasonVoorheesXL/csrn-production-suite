"""Field goal distance, captured through the real operator event path and carried to the
kicker's stat row. Covers the event record, the event label, and the per-player aggregate
that the Final Score Graphic highlights read from."""
from __future__ import annotations

import copy
from threading import Lock

from event_service import EventService
from rules_service import RulesService
from statistics_service import StatisticsService


def base_state():
    return {
        "broadcast_id": "TEST", "home_team": "Pine Valley", "visitor_team": "Northwood",
        "home_school_id": "pv", "visitor_school_id": "nw", "sport": "Football", "status": "live",
        "broadcast_phase": "live", "game_data_authority": "statistician", "home_score": 0, "visitor_score": 0,
        "possession": "home", "down": "2nd", "distance": "8", "ball_spot": "LEFT 30", "quarter": "2",
        "clock_seconds": 500, "clock_visible": True, "clock_running": True, "clock_started_at": 100,
        "home_direction": "right", "visitor_direction": "left", "special_game_phase": "", "kicking_team": "",
        "receiving_team": "", "history": [], "events": [], "plays": [], "next_play_number": 1,
    }


def _spot(value, *_args):
    return RulesService.spot_to_coord(value)


def _direction(state, team):
    return RulesService.team_direction(state, team)


def event_service(state):
    holder = {"state": copy.deepcopy(state)}

    def load():
        return copy.deepcopy(holder["state"])

    def save(value):
        holder["state"] = copy.deepcopy(dict(value))

    def push_history(value):
        value.setdefault("history", []).append(copy.deepcopy({k: v for k, v in value.items() if k != "history"}))

    players = {"h1": {"id": "h1", "number": "7", "name": "Owen Hale"}}

    def automation_player(_roster, player_id):
        return ({"id": "r"}, players.get(player_id)) if player_id in players else (None, None)

    svc = EventService(
        load_state=load, save_state=save, public_state=lambda s: copy.deepcopy(dict(s)),
        push_history=push_history, update_linked_status=lambda *a, **k: None,
        automation_player=automation_player, manual_player=lambda m, t, *a: m,
        player_display=lambda p: str((p or {}).get("name") or ""), show_player_graphic=lambda *a, **k: None,
        apply_penalty=lambda *a, **k: {}, spot_to_coord=_spot, team_direction=_direction,
        normalize_state=lambda s: copy.deepcopy(dict(s)), default_player_graphic=lambda: {},
        transaction_lock=Lock(), now=lambda: 1000.0,
    )
    return svc, holder


def _record_fg(kick_outcome: str, fg_distance) -> dict:
    svc, holder = event_service(base_state())
    payload = {
        "team": "home", "event": "FG", "source": "statistician", "player_id": "h1",
        "kick_outcome": kick_outcome,
    }
    if fg_distance is not None:
        payload["fg_distance"] = fg_distance
    result = svc.trigger(payload)
    assert result.ok, result.data
    return holder["state"]


def _kicker_row(state: dict) -> dict:
    players = StatisticsService().report(state).data["statistics"]["players"]
    return next(p for p in players if p["number"] == "7")


def test_made_fg_with_distance_is_stored_on_the_event_and_labelled_with_it() -> None:
    state = _record_fg("made", "38")
    event = state["events"][-1]
    assert event["automation"]["fg_distance"] == "38"
    assert event["fg_distance"] == "38"
    assert "38-yard field goal" in event["description"]


def test_fg_without_distance_stores_blank_and_labels_without_yards() -> None:
    state = _record_fg("made", None)
    event = state["events"][-1]
    assert event["automation"]["fg_distance"] == ""
    assert "yard field goal" not in event["description"]
    assert "field goal" in event["description"]


def test_made_fg_distance_reaches_the_kickers_stat_row() -> None:
    state = _record_fg("made", "38")
    row = _kicker_row(state)
    assert row["field_goals"] == 1
    assert row["field_goal_distances"] == [38]


def test_missed_fg_distance_is_not_counted_as_a_made_distance() -> None:
    state = _record_fg("no_good", "45")
    row = _kicker_row(state)
    assert row["field_goal_attempts"] == 1 and row["field_goals"] == 0
    assert row["field_goal_distances"] == []


def test_invalid_distances_are_ignored_by_statistics() -> None:
    for bad in ("abc", "0", "120", "-5", "3.5"):
        state = _record_fg("made", bad)
        row = _kicker_row(state)
        assert row["field_goals"] == 1
        assert row["field_goal_distances"] == [], bad


if __name__ == "__main__":
    import sys

    failures = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("PASS", name)
            except Exception as exc:  # pragma: no cover
                failures += 1
                print("FAIL", name, exc)
    sys.exit(1 if failures else 0)
