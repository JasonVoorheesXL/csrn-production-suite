"""Regression coverage for the Caledonia @ Lamar (9/11/2026) bug report,
item 1 (CRITICAL): "Undo Last" could wipe the entire play list and snap
game state back to the 1st quarter.

EventService.undo()'s `if not remaining_events:` branch used to redundantly
re-copy the undone event's `before` snapshot onto live state and
unconditionally wipe `events`/`plays`, undoing the correct work
CanonicalStateFoundation.rebuild() had just done one line above -- snapping
the whole game back to a near-game-start baseline and deleting every
surviving play, not just the one being undone.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from event_service import EventService

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


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


class RecordingLock:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def build_service(state: dict[str, Any]):
    store = copy.deepcopy(state)

    def load_state():
        return copy.deepcopy(store)

    def save_state(value):
        store.clear()
        store.update(copy.deepcopy(dict(value)))
        return copy.deepcopy(store)

    service = EventService(
        load_state=load_state,
        save_state=save_state,
        public_state=lambda value: {**copy.deepcopy(dict(value)), "public": True},
        push_history=lambda value: None,
        update_linked_status=lambda broadcast_id, status, extra=None: None,
        automation_player=lambda roster_id, player_id: (None, None),
        manual_player=lambda data, team_name, school_id="": None,
        player_display=lambda player: "",
        show_player_graphic=lambda *a, **k: None,
        apply_penalty=lambda *a, **k: {"applied": False, "yards": ""},
        spot_to_coord=lambda value: 20,
        team_direction=lambda value, team: 1,
        normalize_state=lambda value: copy.deepcopy(dict(value)),
        default_player_graphic=lambda: {"visible": False},
        transaction_lock=RecordingLock(),
        now=lambda: 1000.25,
    )
    return service, store


def test_undo_of_last_surviving_manual_event_preserves_unrelated_plays() -> None:
    """The surviving event is an early, playless manual event (e.g. a
    first-quarter penalty) -- exactly the "old surviving entry" scenario
    the bug report describes. Plays from later in the game that are not
    tied to it must survive the undo, not be wiped along with it."""
    state = base_state()
    state["quarter"] = "3"
    state["home_score"] = 21
    state["visitor_score"] = 14
    state["down"] = "2nd"
    state["distance"] = "7"
    state["next_play_number"] = 9
    state["events"] = [{
        "id": "E1", "play_id": "", "play_number": 1, "label": "Penalty",
        "before": {
            "home_score": 0, "visitor_score": 0, "possession": "home",
            "down": "1st", "distance": "10", "ball_spot": "LEFT 20", "quarter": "1",
        },
        "after": {"home_score": 0, "visitor_score": 0},
    }]
    state["plays"] = [
        {"event_id": "E7", "play_id": "P7", "play_number": 7, "result": "Run for 4"},
        {"event_id": "E8", "play_id": "P8", "play_number": 8, "result": "Pass complete"},
    ]
    service, store = build_service(state)

    result = service.undo()

    assert result.ok
    # Canonical fields correctly land on E1's baseline (rebuild()'s job)...
    assert store["quarter"] == "1"
    assert store["home_score"] == 0
    assert store["visitor_score"] == 0
    assert store["down"] == "1st"
    assert store["distance"] == "10"
    # ...but the two unrelated plays must NOT be wiped.
    assert store["events"] == []
    assert [p["play_id"] for p in store["plays"]] == ["P7", "P8"]
    assert store["next_play_number"] == 1


def test_undo_of_last_surviving_play_event_preserves_other_plays() -> None:
    """Same scenario, but the last surviving tracked event is itself a
    run/pass PLAY record (report's verification step 4: "since those also
    live in state['events'] via the 'event': 'PLAY' records")."""
    state = base_state()
    state["quarter"] = "3"
    state["home_score"] = 6
    state["next_play_number"] = 10
    state["events"] = [{
        "id": "E1", "play_id": "P1", "play_number": 1, "label": "Touchdown",
        "before": {
            "home_score": 0, "visitor_score": 0, "possession": "home",
            "down": "1st", "distance": "10", "ball_spot": "LEFT 20", "quarter": "1",
        },
        "after": {"home_score": 6},
    }]
    state["plays"] = [
        {"event_id": "E1", "play_id": "P1", "play_number": 1, "result": "Touchdown run"},
        {"event_id": "E9", "play_id": "P9", "play_number": 9, "result": "Sack"},
    ]
    service, store = build_service(state)

    result = service.undo()

    assert result.ok
    assert store["quarter"] == "1"
    assert store["home_score"] == 0
    assert store["events"] == []
    # P9 is not tied to the undone event (E1) and must survive.
    assert [p["play_id"] for p in store["plays"]] == ["P9"]
    assert store["next_play_number"] == 1


def test_undo_of_the_only_event_and_play_still_ends_up_empty() -> None:
    """Sanity check: when there really is nothing left (the pre-existing
    test_undo_restores_event_before_state_and_removes_records scenario in
    tests/test_event_service.py), events and plays legitimately end up
    empty -- the fix must not change that correct outcome."""
    state = base_state()
    state["home_score"] = 6
    state["next_play_number"] = 2
    state["events"] = [{
        "id": "E1", "play_id": "P1", "play_number": 1, "label": "Touchdown",
        "before": {
            "home_score": 0, "visitor_score": 0, "possession": "home",
            "down": "1st", "distance": "10", "ball_spot": "LEFT 20", "quarter": "1",
        },
        "after": {"home_score": 6},
    }]
    state["plays"] = [{"event_id": "E1", "play_id": "P1"}]
    service, store = build_service(state)

    result = service.undo()

    assert result.ok
    assert store["home_score"] == 0
    assert store["events"] == []
    assert store["plays"] == []
    assert store["next_play_number"] == 1


def test_undo_redo_stack_and_correction_log_survive_the_clobber_removal() -> None:
    """The redo-stack/correction-log bookkeeping the bug report said to
    keep must still work once the destructive clobber lines are gone."""
    state = base_state()
    state["events"] = [{
        "id": "E1", "play_id": "", "play_number": 1, "label": "Penalty",
        "before": {"home_score": 0, "visitor_score": 0, "possession": "home",
                   "down": "1st", "distance": "10", "ball_spot": "LEFT 20", "quarter": "1"},
        "after": {"home_score": 0},
    }]
    service, store = build_service(state)

    result = service.undo()

    assert result.ok
    assert store["redo_stack"][-1]["event"]["id"] == "E1"
    assert store["correction_log"][-1]["kind"] == "undo"


def test_event_service_source_no_longer_clobbers_rebuilt_state() -> None:
    """Belt-and-suspenders text check: the redundant before-snapshot
    copy-loop and the unconditional events/plays wipe are gone from the
    `if not remaining_events:` branch; the redo/correction bookkeeping and
    next_play_number reset remain, per the bug report's proposed fix."""
    source = _read("event_service.py")
    branch_start = source.index("if not remaining_events:")
    branch = source[branch_start:source.index("revision = assign_next_revision(state)", branch_start)]
    assert 'for key, value in dict(target.get("before")' not in branch
    assert 'state["events"] = []' not in branch
    assert 'state["plays"] = []' not in branch
    assert 'state["next_play_number"] = int(target.get("play_number", 1) or 1)' in branch
    assert 'state["redo_stack"] = saved_redo' in branch
    assert 'state["correction_log"] = saved_corrections' in branch
