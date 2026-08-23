from __future__ import annotations

import types

import pregame_presentation


def test_state_prefers_running_main_module_over_imported_app_module(monkeypatch) -> None:
    live_app = types.SimpleNamespace(
        load_state=lambda: {
            "broadcast_id": "LIVE-1",
            "status": "live",
            "broadcast_phase": "live",
        }
    )
    stale_app = types.SimpleNamespace(
        load_state=lambda: {
            "broadcast_id": "STALE-1",
            "status": "pregame",
            "broadcast_phase": "pregame",
        }
    )

    monkeypatch.setitem(pregame_presentation.sys.modules, "__main__", live_app)
    monkeypatch.setitem(pregame_presentation.sys.modules, "app", stale_app)

    assert pregame_presentation._state()["broadcast_id"] == "LIVE-1"
