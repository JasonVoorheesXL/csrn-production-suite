"""Regression for the Amory archive overwrite (see docs/AMORY_DATA_LOSS_INVESTIGATION.md).

A final_game period action archives a completed broadcast and clears its live play data.
A later end_game on the same broadcast used to archive the now-empty live state over the
good archive, with nothing to stop it. These tests pin the three guards against that.
"""
from __future__ import annotations

import copy
from threading import Lock

from broadcast_lifecycle_service import BroadcastLifecycleService
from game_operations_service import GameOperationsService

BROADCAST_ID = "FB-TEST-ARCHIVE"
ALREADY_ARCHIVED = "This broadcast's final stats were already archived; nothing further was recorded."


def play_state():
    return {
        "broadcast_id": BROADCAST_ID, "broadcast_created": True, "sport": "Football",
        "status": "live", "broadcast_phase": "live", "period_state": "q4_complete",
        "quarter": "4", "home_score": 27, "visitor_score": 7, "clock_running": False,
        "clock_seconds": 0, "awaiting_period_decision": True, "game_data_authority": "broadcaster",
        "history": [], "redo_stack": [], "correction_log": [], "recent_commands": {},
        "state_revision": 590, "possession": "home", "down": "1st", "distance": "10",
        "ball_spot": "LEFT 20", "special_game_phase": "", "kicking_team": "", "receiving_team": "",
        "events": [{"id": "e1", "event": "TD", "team": "home", "score_delta": 6, "play_id": "p1"}],
        "plays": [{"play_id": "p1", "play_number": 1, "offense": "home", "play_type": "run", "yards": 4,
                   "touchdown": True, "player_name": "Runner", "player_number": "22"}],
    }


class Harness:
    def __init__(self, state):
        self.holder = {"state": copy.deepcopy(state)}
        self.archives: dict[str, dict] = {}
        self.writer_calls = 0
        self.linked_updates = []
        self.svc = GameOperationsService(
            load_state=lambda: copy.deepcopy(self.holder["state"]),
            save_state=lambda s: self.holder.__setitem__("state", copy.deepcopy(dict(s))),
            default_state=lambda: {},
            push_history=lambda s: None,
            source_allowed=lambda s, src: True,
            locked_payload=lambda s: {},
            update_linked_status=lambda *a, **k: self.linked_updates.append(a),
            load_config=lambda: {},
            command_scorebug_visibility=lambda v: {},
            transaction_lock=Lock(),
            archive_final_state=self._archive_writer,
            has_play_archive=lambda bid: bool(
                (self.archives.get(bid) or {}).get("events") or (self.archives.get(bid) or {}).get("plays")
            ),
        )

    def _archive_writer(self, state):
        self.writer_calls += 1
        self.archives[str(state.get("broadcast_id"))] = copy.deepcopy(dict(state))
        return True


def test_final_game_archives_and_clears_then_end_game_leaves_the_good_archive_alone() -> None:
    h = Harness(play_state())
    first = h.svc.set_values({"period_action": "final_game", "command_id": "c-final"})
    assert "archive_error" not in first.data["state"]
    assert h.writer_calls == 1
    good = copy.deepcopy(h.archives[BROADCAST_ID])
    assert good["events"] and good["plays"]
    assert h.holder["state"]["events"] == [] and h.holder["state"]["plays"] == []

    second = h.svc.end_game({"command_id": "c-end"})

    assert h.writer_calls == 1, "end_game must not re-archive a finished broadcast"
    assert h.archives[BROADCAST_ID] == good, "the existing good archive must be untouched"
    assert second.data["state"].get("archive_error") == ALREADY_ARCHIVED


def test_single_final_game_archives_and_clears_with_no_error() -> None:
    h = Harness(play_state())
    result = h.svc.set_values({"period_action": "final_game", "command_id": "c-final"})
    assert h.writer_calls == 1
    assert h.archives[BROADCAST_ID]["events"]
    assert "archive_error" not in result.data["state"]
    assert h.holder["state"]["events"] == [] and h.holder["state"]["plays"] == []


def test_single_end_game_archives_and_clears_with_no_error() -> None:
    state = play_state()
    state["period_state"] = "quarter"
    h = Harness(state)
    result = h.svc.end_game({"command_id": "c-end"})
    assert h.writer_calls == 1
    assert h.archives[BROADCAST_ID]["events"]
    assert "archive_error" not in result.data["state"]
    assert h.holder["state"]["events"] == [] and h.holder["state"]["plays"] == []


def _lifecycle(live_state):
    holder = {"state": copy.deepcopy(live_state)}
    svc = BroadcastLifecycleService(
        load_broadcasts=lambda: [{"broadcast_id": BROADCAST_ID, "status": "completed", "sport": "Football"}],
        load_packages=lambda: [],
        load_state=lambda: copy.deepcopy(holder["state"]),
        save_state=lambda s: holder.__setitem__("state", copy.deepcopy(dict(s))),
        normalize_state=lambda s: dict(s),
        default_state=lambda: {"broadcast_id": "", "events": [], "plays": [], "history": []},
        get_school=lambda sid: None,
        build_identity=lambda school, sid: {},
        readiness=lambda: {},
        update_linked_status=lambda *a, **k: None,
        load_config=lambda: {},
        command_scorebug_visibility=lambda v: {},
        public_state=lambda s: dict(s),
        resume_record=lambda bid: None,
        transaction_lock=Lock(),
    )
    return svc, holder


def test_load_keeps_a_live_state_that_still_has_play_data_for_the_same_broadcast() -> None:
    live = play_state()
    live["broadcast_created"] = False
    svc, holder = _lifecycle(live)
    result = svc.load(BROADCAST_ID)
    assert result.ok
    assert result.data["state"]["plays"] == live["plays"]
    assert holder["state"]["events"] == live["events"]


def test_load_still_rebuilds_when_the_live_state_is_for_a_different_broadcast() -> None:
    live = play_state()
    live["broadcast_id"] = "SOME-OTHER-GAME"
    svc, holder = _lifecycle(live)
    result = svc.load(BROADCAST_ID)
    assert result.ok
    assert result.data["state"]["broadcast_id"] == BROADCAST_ID
    assert result.data["state"]["plays"] == []


def test_archive_writer_refuses_to_replace_a_populated_archive_with_an_empty_snapshot(tmp_path, monkeypatch) -> None:
    import json

    import app as app_module

    archive = {"broadcast_id": BROADCAST_ID, "history": [], "events": [{"id": "e1"}], "plays": [{"play_id": "p1"}]}
    detail_dir = tmp_path / "Broadcasts"
    detail_dir.mkdir()
    (detail_dir / f"{BROADCAST_ID}.json").write_text(
        json.dumps({"broadcast_id": BROADCAST_ID, "final_state_archive": archive}), encoding="utf-8",
    )
    monkeypatch.setattr(app_module, "DATA_DIR", tmp_path)
    saved = []
    monkeypatch.setattr(app_module, "load_broadcasts", lambda: [{"broadcast_id": BROADCAST_ID, "final_state_archive": archive}])
    monkeypatch.setattr(app_module, "save_broadcasts", lambda items: saved.append(items))
    monkeypatch.setattr(app_module, "write_broadcast_detail", lambda item: saved.append(("detail", item)))

    empty_state = {"broadcast_id": BROADCAST_ID, "history": [], "events": [], "plays": []}
    assert app_module.write_broadcast_final_archive(empty_state) is False
    assert saved == [], "nothing may be written when the guard refuses"
    assert json.loads((detail_dir / f"{BROADCAST_ID}.json").read_text(encoding="utf-8"))["final_state_archive"] == archive


def test_archive_writer_still_writes_the_first_archive_for_a_broadcast(tmp_path, monkeypatch) -> None:
    import app as app_module

    monkeypatch.setattr(app_module, "DATA_DIR", tmp_path)
    (tmp_path / "Broadcasts").mkdir()
    items = [{"broadcast_id": BROADCAST_ID}]
    monkeypatch.setattr(app_module, "load_broadcasts", lambda: items)
    monkeypatch.setattr(app_module, "save_broadcasts", lambda new: None)

    def fake_detail(item):
        import json
        (tmp_path / "Broadcasts" / f"{BROADCAST_ID}.json").write_text(json.dumps(item), encoding="utf-8")

    monkeypatch.setattr(app_module, "write_broadcast_detail", fake_detail)
    state = {"broadcast_id": BROADCAST_ID, "history": [], "events": [{"id": "e1"}], "plays": [{"play_id": "p1"}], "status": "completed"}
    assert app_module.write_broadcast_final_archive(state) is True
