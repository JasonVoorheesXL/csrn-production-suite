"""headshot_backfill_sim.py

Settles overnight-audit finding #2: does the manual-trigger headshot
backfill from commit b9b8f97 ("Backfill manual player-graphic entries
with their roster headshot") have any *observable* effect when driven
through the real EventService.trigger() path it targets?

This does not mock manual_automation_player() or
_roster_player_by_school_and_number() -- it imports the real, committed
functions from app.py and drives them through a real EventService
instance (event_service.py, unmodified), the same wiring app.py uses in
get_event_service(). Only the roster data source and the terminal
show_player_graphic callback are stubbed, so this stays a fast, isolated
simulation instead of a full Flask/HTTP run -- everything upstream of
"does the graphic actually get shown" is the real production code.

Two cases:
  A. A player is entered with only a typed jersey number (no
     roster_id/player_id) -- the exact scenario the commit describes:
     the automatic roster match was rejected (e.g. by the stale-number
     guard), so manual_automation_player() has to backfill from the
     roster by number+school instead.
  B. Control case: a player resolved normally via player_id, to confirm
     the harness/gate isn't just broken for everyone.

Run: python headshot_backfill_sim.py
"""

from __future__ import annotations

import copy
import sys
from typing import Any

import app as app_module
from event_service import EventService

# Real production shape, taken from Data/Rosters/rosters.json as of
# 2026-08-25: Caledonia #79 Jaraylon Washington has a real headshot on
# file; #1 Caleb Lang genuinely has none. These are the same two "known
# real cases" cited in commit b9b8f97's own message.
REAL_CALEDONIA_ROSTER = [
    {
        "id": "caledonia-football-2026-varsity-boys",
        "school_id": "caledonia",
        "players": [
            {
                "id": "13-jaraylon-washington",
                "number": "79",
                "first_name": "Jaraylon",
                "last_name": "Washington",
                "status": "active",
                "grade": "12",
                "headshot": "/roster-headshots/caledonia-football-2026-varsity-boys__79-jaraylon-washington.jpg",
            },
            {
                "id": "1-caleb-lang",
                "number": "1",
                "first_name": "Caleb",
                "last_name": "Lang",
                "status": "active",
                "grade": "",
                "headshot": "",
            },
        ],
    }
]


def base_state() -> dict[str, Any]:
    return {
        "broadcast_id": "SIM-1",
        "status": "live",
        "broadcast_phase": "live",
        "game_data_authority": "broadcaster",
        "statistician_enabled": False,
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
        "next_play_number": 1,
        "events": [],
        "plays": [],
        "history": [],
        "correction_log": [],
        "last_event": {},
        "player_graphic": {"visible": False},
    }


def build_service(state: dict[str, Any]):
    """Same wiring as app.get_event_service(), except:
    - automation_player/resolve_player use a tiny in-memory roster
      instead of the real filesystem-backed RosterRepository, and
    - show_player_graphic is a recording stub instead of
      GraphicsService.show_automation_player.
    manual_player is the REAL app.manual_automation_player, unmodified,
    and the id-gate being tested lives in the real, unmodified
    event_service.py -- neither is stubbed.
    """
    store = copy.deepcopy(state)
    calls: dict[str, list[Any]] = {"graphics": []}

    def load_state():
        return copy.deepcopy(store)

    def save_state(value):
        store.clear()
        store.update(copy.deepcopy(dict(value)))

    def automation_player(roster_id: str, player_id: str):
        # Simulates "no roster_id/player_id supplied, or the stale-number
        # guard rejected the automatic match" -- exactly the scenario
        # manual_automation_player() exists to cover.
        return (None, None)

    def show_player_graphic(state_arg, roster, player, graphic_type, duration, **kwargs):
        calls["graphics"].append(
            {
                "player": copy.deepcopy(player),
                "graphic_type": graphic_type,
                "eyebrow": kwargs.get("eyebrow", ""),
            }
        )
        state_arg["player_graphic"] = {
            "visible": True,
            "headshot": (player or {}).get("headshot", ""),
            "eyebrow": kwargs.get("eyebrow", ""),
        }

    service = EventService(
        load_state=load_state,
        save_state=save_state,
        public_state=lambda value: copy.deepcopy(dict(value)),
        push_history=lambda value: None,
        update_linked_status=lambda broadcast_id, status, extra=None: None,
        automation_player=automation_player,
        manual_player=app_module.manual_automation_player,  # REAL, committed backfill code
        player_display=app_module.player_display,
        show_player_graphic=show_player_graphic,
        apply_penalty=lambda *a, **k: {"applied": False, "yards": 0},
        spot_to_coord=lambda value: 20,
        team_direction=lambda value, team: 1,
        normalize_state=lambda value: copy.deepcopy(dict(value)),
        default_player_graphic=lambda: {"visible": False},
        resolve_player=lambda roster_id, player_id: (None, None),
        on_event=lambda event: None,
        transaction_lock=_NullLock(),
    )
    return service, store, calls


class _NullLock:
    def acquire(self, *a, **k):
        return True

    def release(self):
        return None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def run_case_a() -> bool:
    """Manual number-only entry -- the fixed scenario. Does the
    backfilled headshot ever reach the on-screen graphic?"""
    print("=" * 78)
    print("CASE A: manual jersey-number-only entry (no roster_id/player_id)")
    print("=" * 78)

    app_module.load_rosters = lambda: REAL_CALEDONIA_ROSTER  # real backfill's data source

    service, store, calls = build_service(base_state())
    result = service.trigger(
        {
            "team": "home",
            "event": "TD",
            "play_type": "rush",
            "manual_player": {"number": "79", "name": "Jaraylon Washington"},
        }
    )

    print(f"trigger() result code: {result.code}")

    # Directly confirm the committed backfill fires and does its job.
    backfilled = app_module.manual_automation_player(
        {"number": "79", "name": "Jaraylon Washington"}, "Caledonia", "caledonia"
    )
    print(f"manual_automation_player() output: id={backfilled['id']!r} "
          f"headshot={backfilled['headshot']!r}")
    backfill_worked = bool(backfilled["headshot"])

    graphic_fired = len(calls["graphics"]) > 0
    final_graphic = store.get("player_graphic", {})
    print(f"_show_player_graphic() called: {graphic_fired}")
    print(f"final state['player_graphic']: {final_graphic}")

    observable = graphic_fired and bool(final_graphic.get("headshot"))
    print()
    print(f"Backfill computed a real headshot: {backfill_worked}")
    print(f"That headshot became observable on screen: {observable}")
    print()
    if backfill_worked and not observable:
        print(">>> Backfill fires internally, but is NEVER shown: EventService.trigger()'s")
        print(">>> automatic player-graphic branch only calls show_player_graphic() when")
        print(">>> player.get('id') is truthy (event_service.py's TD/2PT/sack/turnover/")
        print(">>> first-down eyebrow block). manual_automation_player() always returns")
        print(">>> id='' -- by construction, a manual entry can never satisfy that gate.")
        print(">>> The fix is real but has ZERO observable effect through this call site.")
    return observable


def run_case_b() -> bool:
    """Control: a normally-resolved roster player (real id) should still
    show the graphic normally -- confirms the gate isn't broken for
    everyone, only for manual/no-id entries."""
    print()
    print("=" * 78)
    print("CASE B (control): player resolved via a real roster id")
    print("=" * 78)

    state = base_state()
    store = copy.deepcopy(state)
    calls: dict[str, list[Any]] = {"graphics": []}

    def load_state():
        return copy.deepcopy(store)

    def save_state(value):
        store.clear()
        store.update(copy.deepcopy(dict(value)))

    real_player = {
        "id": "13-jaraylon-washington",
        "number": "79",
        "preferred_name": "Jaraylon Washington",
        "headshot": "/roster-headshots/caledonia-football-2026-varsity-boys__79-jaraylon-washington.jpg",
    }

    def automation_player(roster_id: str, player_id: str):
        if player_id == "13-jaraylon-washington":
            return ({"id": "caledonia-football-2026-varsity-boys", "school_id": "caledonia"}, real_player)
        return (None, None)

    def show_player_graphic(state_arg, roster, player, graphic_type, duration, **kwargs):
        calls["graphics"].append({"player": copy.deepcopy(player)})
        state_arg["player_graphic"] = {"visible": True, "headshot": (player or {}).get("headshot", "")}

    service = EventService(
        load_state=load_state,
        save_state=save_state,
        public_state=lambda value: copy.deepcopy(dict(value)),
        push_history=lambda value: None,
        update_linked_status=lambda broadcast_id, status, extra=None: None,
        automation_player=automation_player,
        manual_player=app_module.manual_automation_player,
        player_display=app_module.player_display,
        show_player_graphic=show_player_graphic,
        apply_penalty=lambda *a, **k: {"applied": False, "yards": 0},
        spot_to_coord=lambda value: 20,
        team_direction=lambda value, team: 1,
        normalize_state=lambda value: copy.deepcopy(dict(value)),
        default_player_graphic=lambda: {"visible": False},
        resolve_player=lambda roster_id, player_id: (None, None),
        on_event=lambda event: None,
        transaction_lock=_NullLock(),
    )

    result = service.trigger(
        {
            "team": "home",
            "event": "TD",
            "play_type": "rush",
            "player_id": "13-jaraylon-washington",
        }
    )
    print(f"trigger() result code: {result.code}")
    graphic_fired = len(calls["graphics"]) > 0
    final_graphic = store.get("player_graphic", {})
    print(f"_show_player_graphic() called: {graphic_fired}")
    print(f"final state['player_graphic']: {final_graphic}")
    return graphic_fired and bool(final_graphic.get("headshot"))


if __name__ == "__main__":
    case_a_observable = run_case_a()
    case_b_observable = run_case_b()

    print()
    print("=" * 78)
    print("VERDICT")
    print("=" * 78)
    print(f"Case A (manual number-only entry) headshot observable on screen: {case_a_observable}")
    print(f"Case B (normal roster-id entry)   headshot observable on screen: {case_b_observable}")
    if not case_a_observable and case_b_observable:
        print()
        print("Finding #2 CONFIRMED: the manual-trigger headshot backfill (b9b8f97) has no")
        print("observable effect via EventService.trigger(). The player.get('id') truthy")
        print("gate in event_service.py's automatic player-graphic branch silently drops")
        print("every manually-entered player -- headshot or not -- before it ever reaches")
        print("show_player_graphic(). The gate blocks display, not just missing headshots.")
    sys.exit(0 if (case_b_observable and True) else 1)
