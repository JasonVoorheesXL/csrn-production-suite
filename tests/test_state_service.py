from __future__ import annotations

import copy

from state_service import StateService


def defaults() -> dict:
    return {
        "broadcast_id": "",
        "broadcast_phase": "pregame",
        "possession": "home",
        "history": [],
        "events": [],
        "plays": [],
        "correction_log": [],
        "next_play_number": 1,
        "game_data_authority": "broadcaster",
        "statistician_enabled": False,
        "clock_running": False,
        "clock_started_at": 0,
        "clock_seconds": 720,
        "home_identity": {},
        "visitor_identity": {},
        "personnel_graphic": {},
        "player_graphic": {},
        "player_highlight": {},
        "sponsor_spotlight": {},
        "graphics_queue": [],
    }


def build(initial: dict | None = None, *, now: int = 100, snapshot=None):
    store = copy.deepcopy(initial or defaults())

    def load_raw():
        return copy.deepcopy(store)

    def replace_raw(value):
        store.clear()
        store.update(copy.deepcopy(dict(value)))
        return copy.deepcopy(store)

    service = StateService(
        load_raw=load_raw,
        replace_raw=replace_raw,
        default_state=defaults,
        persist_linked_snapshot=snapshot,
        canonical_team_key=lambda state, value: str(value),
        canonical_team_name=lambda state, value: str(value).title(),
        now=lambda: now,
    )
    return service, store


def test_normalize_restores_invalid_core_fields() -> None:
    service, _ = build()
    state = service.normalize({
        "broadcast_phase": "bad",
        "possession": "bad",
        "history": "bad",
        "next_play_number": "bad",
        "game_data_authority": "bad",
    })
    assert state["broadcast_phase"] == "pregame"
    assert state["possession"] == "home"
    assert state["history"] == []
    assert state["next_play_number"] == 1
    assert state["game_data_authority"] == "broadcaster"
    assert state["statistician_enabled"] is False


def test_normalize_sets_statistician_flag() -> None:
    service, _ = build()
    state = service.normalize({"game_data_authority": "statistician"})
    assert state["statistician_enabled"] is True


def test_events_are_migrated_to_plays() -> None:
    service, _ = build()
    state = service.normalize({
        "broadcast_id": "B1",
        "events": [{
            "id": "E1",
            "event": "TD",
            "team": "home",
            "quarter": "2",
            "description": "Touchdown",
            "automation": {"yards": 12},
        }],
        "plays": [],
    })
    assert state["plays"][0]["play_id"] == "B1-0001"
    assert state["plays"][0]["touchdown"] is True
    assert state["plays"][0]["yards"] == 12


def test_running_clock_advances_without_persisting_on_read() -> None:
    initial = defaults() | {
        "clock_running": True,
        "clock_started_at": 90,
        "clock_seconds": 20,
    }
    service, store = build(initial, now=100)
    state = service.load().data["state"]
    assert state["clock_seconds"] == 10
    assert state["clock_started_at"] == 100
    assert store["clock_seconds"] == 20
    assert store["clock_started_at"] == 90


def test_running_clock_stops_at_zero() -> None:
    initial = defaults() | {
        "clock_running": True,
        "clock_started_at": 80,
        "clock_seconds": 10,
    }
    service, _ = build(initial, now=100)
    state = service.load().data["state"]
    assert state["clock_seconds"] == 0
    assert state["clock_running"] is False
    assert state["clock_started_at"] == 0


def test_running_clock_without_start_time_is_derived_without_write() -> None:
    initial = defaults() | {"clock_running": True, "clock_started_at": 0}
    service, store = build(initial, now=100)
    state = service.load().data["state"]
    assert state["clock_started_at"] == 100
    assert store["clock_started_at"] == 0


def test_repeated_running_clock_reads_never_replace_raw_state() -> None:
    initial = defaults() | {
        "clock_running": True,
        "clock_started_at": 90,
        "clock_seconds": 20,
    }
    store = copy.deepcopy(initial)
    replacements = []

    service = StateService(
        load_raw=lambda: copy.deepcopy(store),
        replace_raw=lambda value: replacements.append(copy.deepcopy(dict(value))) or dict(value),
        default_state=defaults,
        canonical_team_key=lambda state, value: str(value),
        canonical_team_name=lambda state, value: str(value).title(),
        now=lambda: 100,
    )

    for _ in range(20):
        state = service.load().data["state"]
        assert state["clock_seconds"] == 10

    assert replacements == []
    assert store == initial


def test_save_persists_linked_broadcast_snapshot() -> None:
    seen = []
    service, store = build(snapshot=lambda state: seen.append(state))
    result = service.save(defaults() | {"broadcast_id": "B1"})
    assert result.ok
    assert store["broadcast_id"] == "B1"
    assert seen[0]["broadcast_id"] == "B1"


def test_save_without_broadcast_skips_snapshot() -> None:
    seen = []
    service, _ = build(snapshot=lambda state: seen.append(state))
    service.save(defaults())
    assert seen == []


def test_apply_change_records_undo_snapshot() -> None:
    service, _ = build(defaults() | {"home_score": 0})
    state = service.apply_change({"home_score": 6}).data["state"]
    assert state["home_score"] == 6
    assert state["history"][0]["home_score"] == 0


def test_history_is_capped_at_fifty() -> None:
    state = defaults() | {"history": [{"n": n} for n in range(50)]}
    StateService.push_history(state)
    assert len(state["history"]) == 50
    assert state["history"][0] == {"n": 1}


def test_public_state_removes_local_media_paths() -> None:
    service, _ = build()
    state = defaults() | {
        "home_identity": {"logo": "C:/logos/home.png"},
        "visitor_identity": {"logo": "/school-logos/v/logo.png"},
        "personnel_graphic": {"headshot": "Data/Personnel/a.png"},
        "player_graphic": {"team_logo": "https://example.com/logo.png"},
        "player_highlight": {
            "team_logo": "/school-logos/team.png",
            "media_url": "C:/private/highlight.mp4",
        },
        "sponsor_spotlight": {
            "media_url": "C:/private/sponsor.mp4",
            "sponsor_logo": "/asset-files/sponsor.png",
        },
        "graphics_queue": [
            {
                "graphic": {
                    "headshot": "C:/private/player.png",
                    "team_logo": "/school-logos/team.png",
                }
            }
        ],
    }
    public = service.public(state).data["state"]
    assert public["home_identity"]["logo"] == ""
    assert public["visitor_identity"]["logo"].startswith("/")
    assert public["personnel_graphic"]["headshot"] == ""
    assert public["player_graphic"]["team_logo"].startswith("https://")
    assert public["player_highlight"]["team_logo"].startswith("/")
    assert public["player_highlight"]["media_url"] == ""
    assert public["sponsor_spotlight"]["media_url"] == ""
    assert public["sponsor_spotlight"]["sponsor_logo"].startswith("/")
    assert public["graphics_queue"][0]["graphic"]["headshot"] == ""
    assert public["graphics_queue"][0]["graphic"]["team_logo"].startswith("/")


def test_public_state_enriches_player_name_and_result() -> None:
    service, _ = build()
    service._resolve_player = lambda state, team, number: {"name": "Runner"}
    state = defaults() | {
        "plays": [{
            "play_type": "run",
            "offense": "home",
            "defense": "visitor",
            "player_number": "7",
            "player_name": "",
            "yards": 8,
            "first_down": True,
        }]
    }
    play = service.public(state).data["state"]["plays"][0]
    assert play["player_name"] == "Runner"
    assert play["result"] == "#7 Runner run for 8 yards, first down"

def test_public_state_normalizes_legacy_managed_relative_logo_urls() -> None:
    service, _ = build()
    state = defaults() | {
        "home_identity": {
            "logo": "school-logos/test-northwood-knights/logo.png",
            "logo_certified": True,
            "branding_status": "certified_logo",
        },
        "visitor_identity": {
            "logo": r"school-logos\test-pine-valley-panthers\logo.png",
            "logo_certified": True,
            "branding_status": "certified_logo",
        },
    }

    public = service.public(state).data["state"]

    assert (
        public["home_identity"]["logo"]
        == "/school-logos/test-northwood-knights/logo.png"
    )
    assert (
        public["visitor_identity"]["logo"]
        == "/school-logos/test-pine-valley-panthers/logo.png"
    )
    assert public["home_identity"]["logo_certified"] is True
    assert public["visitor_identity"]["logo_certified"] is True
    assert public["home_identity"]["branding_status"] == "certified_logo"
    assert public["visitor_identity"]["branding_status"] == "certified_logo"


def test_public_state_normalizes_only_known_managed_relative_media_paths() -> None:
    service, _ = build()
    state = defaults() | {
        "home_identity": {"logo": "assets/private/logo.png"},
        "visitor_identity": {"logo": "../outside/logo.png"},
        "personnel_graphic": {
            "headshot": "personnel-headshots/coach.png",
        },
        "player_graphic": {
            "headshot": "roster-headshots/test-fixtures/player.png",
            "team_logo": "asset-files/team.png",
        },
    }

    public = service.public(state).data["state"]

    assert public["home_identity"]["logo"] == ""
    assert public["visitor_identity"]["logo"] == ""
    assert (
        public["personnel_graphic"]["headshot"]
        == "/personnel-headshots/coach.png"
    )
    assert (
        public["player_graphic"]["headshot"]
        == "/roster-headshots/test-fixtures/player.png"
    )
    assert public["player_graphic"]["team_logo"] == "/asset-files/team.png"


def test_legacy_logo_url_normalization_does_not_mutate_frozen_state() -> None:
    service, store = build(
        defaults()
        | {
            "broadcast_id": "B1",
            "home_identity": {
                "logo": "school-logos/test-northwood-knights/logo.png",
                "logo_certified": True,
            },
        }
    )

    loaded = service.load().data["state"]
    public = service.public(loaded).data["state"]

    assert (
        loaded["home_identity"]["logo"]
        == "school-logos/test-northwood-knights/logo.png"
    )
    assert (
        store["home_identity"]["logo"]
        == "school-logos/test-northwood-knights/logo.png"
    )
    assert (
        public["home_identity"]["logo"]
        == "/school-logos/test-northwood-knights/logo.png"
    )
