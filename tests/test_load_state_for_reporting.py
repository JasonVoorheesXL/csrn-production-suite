"""Regression coverage for load_state_for_reporting()'s archive fallback.

Confirmed against tonight's real Caledonia/Northwood broadcast
(FB-2026-OPEN-W00-001): the archive (Data/Broadcasts/<id>.json's
final_state_archive) had all 16 real events/plays and the correct 20-7
score, but the Statistics Engine, PDF, and recap all showed empty results
anyway, because load_state_for_reporting()'s guard checked history/events/
plays generically -- a single stray leftover history entry (see
test_state_service.py's push_history-completed-broadcast tests for how
that entry got there) was enough to make the `or` trip and skip the
archive fallback entirely, even though events and plays were both
genuinely empty.
"""

from __future__ import annotations

import app as app_module


def _completed_state(**overrides):
    base = {
        "broadcast_id": "FB-TEST-1",
        "status": "completed",
        "home_score": 20,
        "visitor_score": 7,
        "history": [],
        "events": [],
        "plays": [],
    }
    base.update(overrides)
    return base


def test_falls_back_to_archive_when_events_and_plays_are_empty_despite_stray_history(monkeypatch) -> None:
    # The exact real-world shape: one leftover history entry, but events and
    # plays genuinely empty.
    monkeypatch.setattr(app_module, "load_state", lambda: _completed_state(history=[{"stray": True}]))
    monkeypatch.setattr(
        app_module,
        "load_final_state_archive",
        lambda broadcast_id: {
            "events": [{"id": "e1"}, {"id": "e2"}],
            "plays": [{"id": "p1"}, {"id": "p2"}],
            "history": [{"h": 1}, {"h": 2}],
        },
    )
    result = app_module.load_state_for_reporting()
    assert len(result["events"]) == 2
    assert len(result["plays"]) == 2
    assert len(result["history"]) == 2


def test_does_not_backfill_when_events_or_plays_already_present(monkeypatch) -> None:
    monkeypatch.setattr(app_module, "load_state", lambda: _completed_state(events=[{"id": "e1"}]))
    calls = []
    monkeypatch.setattr(
        app_module,
        "load_final_state_archive",
        lambda broadcast_id: calls.append(broadcast_id) or {"events": [{"id": "archived"}]},
    )
    result = app_module.load_state_for_reporting()
    assert result["events"] == [{"id": "e1"}]
    assert calls == []  # archive lookup skipped entirely -- live data already real


def test_does_not_backfill_a_non_completed_broadcast(monkeypatch) -> None:
    monkeypatch.setattr(app_module, "load_state", lambda: _completed_state(status="live"))
    calls = []
    monkeypatch.setattr(
        app_module,
        "load_final_state_archive",
        lambda broadcast_id: calls.append(broadcast_id) or {"events": [{"id": "archived"}]},
    )
    result = app_module.load_state_for_reporting()
    assert result["events"] == []
    assert calls == []


def test_returns_live_state_unchanged_when_no_archive_exists(monkeypatch) -> None:
    monkeypatch.setattr(app_module, "load_state", lambda: _completed_state())
    monkeypatch.setattr(app_module, "load_final_state_archive", lambda broadcast_id: None)
    result = app_module.load_state_for_reporting()
    assert result["events"] == []
    assert result["plays"] == []
