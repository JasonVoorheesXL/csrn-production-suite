"""Per-request state cost (2026-10-29 profile of a ~140-play game).

Record Play slowed to 3-8 s late in a game. About 90% of the time was deep
copies of the multi-MB live state: two full load()s per mutation just for the
route diagnostics summary, two copies inside every load(), another copy at the
top of RulesService.play(), and a roster/school file re-read for every play
during /api/state. These tests pin the cheaper paths.
"""
from __future__ import annotations

import copy

import pytest

from state_service import StateService


def _service(state: dict, **kwargs) -> StateService:
    return StateService(
        load_raw=lambda: copy.deepcopy(state),
        replace_raw=lambda s: dict(s),
        default_state=lambda: {},
        cache_committed_state=True,
        **kwargs,
    )


def _state() -> dict:
    return {
        "broadcast_id": "FB-PERF-1",
        "state_revision": 7,
        "home_team": "Home",
        "visitor_team": "Visitor",
        "events": [{"id": "e1"}, {"id": "e2"}],
        "plays": [
            {"play_id": "p1", "play_type": "run", "offense": "home", "defense": "visitor", "player_number": "22"},
            {"play_id": "p2", "play_type": "run", "offense": "home", "defense": "visitor", "player_number": "22"},
            {"play_id": "p3", "play_type": "run", "offense": "home", "defense": "visitor", "player_number": "5"},
        ],
    }


def test_peek_reads_the_committed_state_without_copying_it() -> None:
    service = _service(_state())
    service.load()  # primes the committed-state cache
    seen = []
    assert service.peek(lambda s: seen.append(s) or s.get("broadcast_id")) == "FB-PERF-1"
    assert seen[0] is service._committed_state


def test_peek_falls_back_to_a_raw_read_when_nothing_is_cached() -> None:
    service = StateService(load_raw=lambda: _state(), replace_raw=lambda s: dict(s), default_state=lambda: {})
    assert service.peek(lambda s: len(s["plays"])) == 3


def test_load_still_returns_an_independent_copy_of_the_committed_state() -> None:
    service = _service(_state())
    first = service.load().data["state"]
    first["plays"].append({"play_id": "mutated"})
    first["events"][0]["id"] = "changed"
    second = service.load().data["state"]
    assert len(second["plays"]) == 3
    assert second["events"][0]["id"] == "e1"


def test_public_resolves_each_jersey_once_per_call() -> None:
    calls = []

    def resolve(state, team, number):
        calls.append((team, str(number)))
        return {"number": str(number), "name": f"Player {number}", "resolved": True}

    service = _service(_state(), resolve_player=resolve)
    public = service.public(_state()).data["state"]
    assert [p["player_name"] for p in public["plays"]] == ["Player 22", "Player 22", "Player 5"]
    assert sorted(set(calls)) == [("home", "22"), ("home", "5")]
    assert len(calls) == 2


def test_memoized_resolver_returns_copies_callers_can_change() -> None:
    resolve = StateService._memoized_resolver(lambda s, t, n: {"name": "A"})
    first = resolve({}, "home", "1")
    first["name"] = "changed"
    assert resolve({}, "home", "1")["name"] == "A"


@pytest.mark.parametrize("owned", [True, False])
def test_normalize_owned_flag_only_skips_the_copy(owned: bool) -> None:
    service = _service(_state())
    raw = _state()
    merged = service.normalize(raw, owned=owned)
    assert merged["broadcast_id"] == "FB-PERF-1"
    assert (merged["events"][0] is raw["events"][0]) is owned


def test_live_game_routes_take_the_diagnostics_summary_through_peek() -> None:
    import app

    deps = app.LIVE_GAME_ROUTES_BLUEPRINT  # registered with peek_state wired in
    assert deps is not None
    source = open("routes/live_game_routes.py", encoding="utf-8").read()
    assert "dependencies.peek_state(state_summary)" in source
    assert "peek_state=lambda reader: get_state_service().peek(reader)" in open("app.py", encoding="utf-8").read()
