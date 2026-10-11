"""Regression for the 2026-10-09 Columbus @ Caledonia PLAYER_TEAM_MISMATCH drops.

Of 140 /api/rules-play attempts that night, 7 were hard-rejected with
PLAYER_TEAM_MISMATCH, all Columbus plays. 52 of Columbus's 90 roster players
have a blank jersey, so a real Columbus number failed to resolve on Columbus;
when the same number belonged to a Caledonia player the play was dropped.

Such a play now records with that player unresolved (same as any unknown
number) and is flagged in team_mismatch_players. An ejected player still
blocks (PLAYER_INELIGIBLE is intentionally hard).

Real RulesService and the real app.resolve_game_roster_player; only the
roster/school data source is swapped for a small Columbus/Caledonia fixture
that has the same shape as rosters.json.
"""
from __future__ import annotations

import copy
import itertools
import threading

import app
from rules_service import RulesService
from runtime_diagnostics_service import get_runtime_diagnostics

SCHOOLS = [
    {"id": "caledonia", "official_name": "Caledonia High School", "broadcast_name": "Caledonia"},
    {"id": "columbus", "official_name": "Columbus High School", "broadcast_name": "Columbus"},
]
ROSTERS = [
    {
        "id": "roster-caledonia", "school_id": "caledonia", "sport": "Football", "level": "Varsity",
        "players": [
            {"id": "cal-22", "number": "22", "first_name": "Cal", "last_name": "Runner"},
            {"id": "cal-55", "number": "55", "first_name": "Cal", "last_name": "Lineman"},
            {"id": "cal-9", "number": "9", "first_name": "Cal", "last_name": "Passer"},
        ],
    },
    {
        "id": "roster-columbus", "school_id": "columbus", "sport": "Football", "level": "Varsity",
        "players": [
            {"id": "col-4", "number": "4", "first_name": "Col", "last_name": "Back"},
            # The real Columbus #22 and #55 exist but their jerseys are blank.
            {"id": "col-blank-a", "number": "", "first_name": "Blank", "last_name": "Jersey"},
            {"id": "col-blank-b", "number": "", "first_name": "Other", "last_name": "Blank"},
        ],
    },
]


def _game(monkeypatch, **patch):
    monkeypatch.setattr(app, "load_rosters", lambda: copy.deepcopy(ROSTERS))
    monkeypatch.setattr(app, "load_schools", lambda: copy.deepcopy(SCHOOLS))
    store = {
        "broadcast_id": "FB-TEST-MISMATCH", "status": "live", "broadcast_phase": "live",
        "game_data_authority": "broadcaster", "sport": "Football", "level": "Varsity",
        "home_team": "Caledonia", "visitor_team": "Columbus",
        "home_school_id": "caledonia", "visitor_school_id": "columbus",
        "home_score": 0, "visitor_score": 0, "possession": "visitor", "down": "1st", "distance": "10",
        "ball_spot": "LEFT 30", "quarter": "1", "clock_seconds": 720, "clock_running": False,
        "clock_visible": True, "clock_started_at": 0,
        "home_direction": "left", "visitor_direction": "right", "special_game_phase": "",
        "next_play_number": 1, "events": [], "plays": [], "history": [], "correction_log": [],
        "last_event": {}, "player_graphic": {"visible": False}, "team_roles": {},
    }
    store.update(patch)

    def save(value):
        store.clear()
        store.update(copy.deepcopy(dict(value)))

    tick = itertools.count(1000)
    rules = RulesService(
        load_state=lambda: copy.deepcopy(store), save_state=save, push_history=lambda s: None,
        source_allowed=lambda s, src: True, locked_payload=lambda s: s,
        resolve_player=app.resolve_game_roster_player, show_player_graphic=lambda *a, **k: None,
        transaction_lock=threading.Lock(), now=lambda: next(tick),
    )
    return rules, store


def _mismatch_diagnostics(command_id):
    return [
        e for e in get_runtime_diagnostics().snapshot(limit=2000)["events"]
        if e.get("event_type") == "SERVER_RULES_PLAYER_TEAM_MISMATCH" and e.get("command_id") == command_id
    ]


def test_the_fixture_reproduces_the_columbus_failure_mode(monkeypatch) -> None:
    _game(monkeypatch)
    state = {"home_school_id": "caledonia", "visitor_school_id": "columbus", "home_team": "Caledonia",
             "visitor_team": "Columbus", "sport": "Football", "level": "Varsity"}
    assert app.resolve_game_roster_player(state, "visitor", "22")["resolved"] is False
    assert app.resolve_game_roster_player(state, "home", "22")["name"] == "Cal Runner"
    assert app.resolve_game_roster_player(state, "visitor", "4")["name"] == "Col Back"


def test_number_resolving_only_on_the_other_team_records_as_unresolved(monkeypatch) -> None:
    rules, store = _game(monkeypatch)
    result = rules.play({
        "team": "visitor", "play_type": "run", "player_number": "22",
        "start_spot": "LEFT 30", "end_spot": "LEFT 38", "command_id": "cmd-mismatch-run",
    })

    assert result.code == "OK", result.data
    play = result.data["play"]
    assert len(store["plays"]) == 1 and len(store["events"]) == 1
    assert play["offense"] == "visitor" and play["yards"] == 8
    assert play["player_number"] == "22"
    assert play["player_name"] == ""  # never credited to Caledonia's #22
    assert "Cal Runner" not in play["result"]
    assert play["unresolved_players"] == ["player"]
    assert play["team_mismatch_players"] == [{
        "role": "player", "number": "22", "permitted_team": "visitor",
        "resolved_team": "home", "resolved_name": "Cal Runner",
    }]
    assert store["plays"][0]["team_mismatch_players"] == play["team_mismatch_players"]
    assert store["ball_spot"] == "LEFT 38"

    logged = _mismatch_diagnostics("cmd-mismatch-run")
    assert len(logged) == 1
    assert logged[0]["play_id"] == play["play_id"] and logged[0]["number"] == "22"
    assert logged[0]["permitted_team"] == "visitor" and logged[0]["resolved_team"] == "home"


def test_browser_supplied_other_team_name_is_dropped(monkeypatch) -> None:
    rules, store = _game(monkeypatch)
    result = rules.play({
        "team": "visitor", "play_type": "run", "player_number": "22", "player_name": "Cal Runner",
        "start_spot": "LEFT 30", "end_spot": "LEFT 34",
    })
    assert result.code == "OK"
    assert result.data["play"]["player_name"] == ""
    assert "Cal Runner" not in result.data["play"]["result"]


def test_pass_with_mismatched_receiver_and_sacker_roles(monkeypatch) -> None:
    rules, store = _game(monkeypatch)
    # Columbus #4 (resolves) to #55 (only Caledonia has a 55).
    complete = rules.play({
        "team": "visitor", "play_type": "pass", "pass_outcome": "complete",
        "passer_number": "4", "receiver_number": "55", "start_spot": "LEFT 30", "end_spot": "LEFT 40",
    })
    assert complete.code == "OK"
    play = complete.data["play"]
    assert play["passer_name"] == "Col Back"
    assert play["unresolved_players"] == ["receiver"]
    assert [m["role"] for m in play["team_mismatch_players"]] == ["receiver"]

    # Defensive role: Caledonia sacker #4 doesn't exist on Caledonia, but Columbus has a #4.
    sack = rules.play({
        "team": "visitor", "play_type": "pass", "pass_outcome": "sack",
        "passer_number": "4", "sacker_number": "4", "start_spot": "LEFT 40", "end_spot": "LEFT 35",
    })
    assert sack.code == "OK", sack.data
    mismatch = sack.data["play"]["team_mismatch_players"]
    assert mismatch == [{
        "role": "sacker", "number": "4", "permitted_team": "home",
        "resolved_team": "visitor", "resolved_name": "Col Back",
    }]
    assert sack.data["play"]["sacker_name"] == ""
    assert len(store["plays"]) == 2


def test_clean_play_has_no_mismatch_flag(monkeypatch) -> None:
    rules, store = _game(monkeypatch)
    result = rules.play({
        "team": "visitor", "play_type": "run", "player_number": "4",
        "start_spot": "LEFT 30", "end_spot": "LEFT 33", "command_id": "cmd-clean-run",
    })
    assert result.code == "OK"
    assert result.data["play"]["team_mismatch_players"] == []
    assert result.data["play"]["unresolved_players"] == []
    assert result.data["play"]["player_name"] == "Col Back"
    assert _mismatch_diagnostics("cmd-clean-run") == []


def test_ejected_player_still_blocks(monkeypatch) -> None:
    ejection = {
        "id": "ej-1", "event": "EJECTION", "team": "visitor", "undone": False,
        "ejection": {"person_type": "player", "player_number": "22", "reason": "Targeting"},
    }
    rules, store = _game(monkeypatch, events=[ejection])
    result = rules.play({
        "team": "visitor", "play_type": "run", "player_number": "22",
        "start_spot": "LEFT 30", "end_spot": "LEFT 38",
    })
    assert result.code == "PLAYER_INELIGIBLE"
    assert result.data["role"] == "player" and result.data["team"] == "visitor"
    assert store["plays"] == []
    assert store["events"] == [ejection]
