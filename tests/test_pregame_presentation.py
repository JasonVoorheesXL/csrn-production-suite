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


def _event(quarter: str, eyebrow: str, visible: bool = True, **graphic_overrides):
    graphic = {
        "visible": visible,
        "eyebrow": eyebrow,
        "graphic_type": "touchdown",
        "full_name": "Test Player",
        "display_name": "Test Player",
        "number": "4",
        "headshot": "/roster-headshots/test.jpg",
        "team_logo": "/school-logos/test/logo.png",
        "team_name": "Test",
        "team_color": "#810909",
        "play_detail": "56-yard touchdown run",
        "passer_name": "",
    }
    graphic.update(graphic_overrides)
    return {"quarter": quarter, "created_at": 100, "after": {"player_graphic": graphic}}


def test_first_half_spotlights_includes_real_spotlight_types_from_q1_and_q2() -> None:
    state = {"events": [
        _event("1", "TOUCHDOWN"),
        _event("2", "SACK", display_name="Defender"),
    ]}
    spotlights = pregame_presentation._first_half_spotlights(state)
    assert [s["eyebrow"] for s in spotlights] == ["TOUCHDOWN", "SACK"]


def test_first_half_spotlights_excludes_second_half_and_idle_and_invisible() -> None:
    state = {"events": [
        _event("3", "TOUCHDOWN"),  # second half -- excluded
        _event("1", "PLAYER PROFILE"),  # idle/manual default, not a real moment
        _event("1", "TOUCHDOWN", visible=False),  # never actually shown
        {"quarter": "1", "after": {}},  # no player_graphic at all (pre-fix data)
        {"quarter": "1"},  # no "after" key at all
    ]}
    assert pregame_presentation._first_half_spotlights(state) == []


def test_first_half_spotlights_handles_missing_or_malformed_events() -> None:
    assert pregame_presentation._first_half_spotlights({}) == []
    assert pregame_presentation._first_half_spotlights({"events": "not-a-list"}) == []
    assert pregame_presentation._first_half_spotlights({"events": [None, 5, "x"]}) == []
