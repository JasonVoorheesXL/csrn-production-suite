"""Round 26 Phase B step 5b -- Canadian football, end to end through the
real service layer, once a broadcast can select the jurisdiction.

Pins that every Canadian mechanic Round 26 built actually works together:
3-down cycle (no 4th down), the ball reaching the real 110-yard goal
line, a rouge/single scored and restarting the other team, no-fair-catch,
the operator field_state readout at 110 scale, and field_goal still
cleanly rejected.
"""
from __future__ import annotations

import copy
from threading import Lock

import ruleset_service
from canonical_state_service import CanonicalStateFoundation
from event_service import EventService
from rules_service import RulesService

_ROSTER = {
    ("home", "10"): "Home RB", ("home", "12"): "Home QB", ("home", "80"): "Home WR",
    ("home", "7"): "Home K", ("home", "25"): "Home Ret",
    ("visitor", "22"): "Vis RB", ("visitor", "14"): "Vis QB", ("visitor", "88"): "Vis WR",
    ("visitor", "9"): "Vis K", ("visitor", "27"): "Vis Ret",
}


def _initial_state() -> dict:
    return {
        "broadcast_id": "E2E-CA", "sport": "Football", "status": "live",
        "broadcast_phase": "live", "game_data_authority": "statistician",
        "country": "CA", "region": "ON", "association": "CJFL",
        "home_team": "Ottawa", "visitor_team": "Hamilton",
        "home_school_id": "ott", "visitor_school_id": "ham",
        "home_score": 0, "visitor_score": 0,
        "possession": "home", "down": "1st", "distance": "10",
        "ball_spot": "LEFT 25", "quarter": "1", "clock_seconds": 900,
        "clock_visible": True, "clock_running": False, "clock_started_at": 0,
        "home_direction": "right", "visitor_direction": "left",
        "special_game_phase": "", "kicking_team": "", "receiving_team": "",
        "penalty_administration": {}, "history": [], "events": [], "plays": [],
        "next_play_number": 1,
    }


def _build(holder):
    def load():
        return copy.deepcopy(holder["state"])

    def save(v):
        holder["state"] = copy.deepcopy(dict(v))

    def hist(v):
        v.setdefault("history", []).append(copy.deepcopy({k: x for k, x in v.items() if k != "history"}))

    def resolver(_s, team, number):
        text = str(number or "").strip()
        return {"number": text, "name": _ROSTER.get((team, text), ""),
                "resolved": (team, text) in _ROSTER, "roster_id": "r",
                "player_id": f"{team}-{text}", "headshot": "", "position": "",
                "grade": "", "height": "", "weight": ""}

    players = {f"{t}{n}": {"id": f"{t}{n}", "number": n, "name": nm} for (t, n), nm in _ROSTER.items()}
    rules = RulesService(
        load_state=load, save_state=save, push_history=hist,
        source_allowed=lambda s, src: True, locked_payload=lambda s: {},
        resolve_player=resolver, show_player_graphic=lambda *a, **k: None,
        transaction_lock=Lock(), now=lambda: 1000.0,
    )
    events = EventService(
        load_state=load, save_state=save, public_state=lambda s: copy.deepcopy(dict(s)),
        push_history=hist, update_linked_status=lambda *a, **k: None,
        automation_player=lambda _r, pid: (({"id": "r"}, players.get(pid)) if pid in players else (None, None)),
        manual_player=lambda m, t, *a: m, player_display=lambda p: str((p or {}).get("name") or ""),
        show_player_graphic=lambda *a, **k: None, apply_penalty=lambda *a, **k: {},
        spot_to_coord=RulesService.spot_to_coord, coord_to_spot=RulesService.coord_to_spot,
        team_direction=RulesService.team_direction, normalize_state=lambda s: copy.deepcopy(dict(s)),
        default_player_graphic=lambda: {}, transaction_lock=Lock(), now=lambda: 1000.0,
    )
    return rules, events


def test_jurisdiction_resolves_the_canadian_ruleset() -> None:
    ca = ruleset_service.resolve(country="CA", region="ON", association="CJFL", sport="football")
    assert ca["id"] == "football/ca-cjfl-ofc"
    assert ruleset_service.downs_sequence(ca) == ["1st", "2nd", "3rd"]
    assert ruleset_service.field_geometry(ca)["length_yards"] == 110


def test_three_down_cycle_has_no_fourth_down() -> None:
    holder = {"state": _initial_state()}
    rules, _ = _build(holder)
    rules.play({"team": "home", "play_type": "run", "start_spot": "LEFT 25", "end_spot": "LEFT 27", "player_number": "10"})
    assert holder["state"]["down"] == "2nd"
    rules.play({"team": "home", "play_type": "run", "start_spot": "LEFT 27", "end_spot": "LEFT 30", "player_number": "10"})
    assert holder["state"]["down"] == "3rd"
    r = rules.play({"team": "home", "play_type": "pass", "start_spot": "LEFT 30", "end_spot": "LEFT 30",
                    "pass_outcome": "incomplete", "passer_number": "12", "receiver_number": "80"})
    assert holder["state"]["down"] != "4th"
    assert holder["state"]["possession"] == "visitor"          # turnover on downs
    assert r.data["play"]["turnover"] is True
    assert r.data["play"]["turnover_type"] == "downs"


def test_ball_reaches_the_real_110_yard_goal_line() -> None:
    holder = {"state": _initial_state()}
    rules, _ = _build(holder)
    holder["state"].update(possession="visitor", ball_spot="RIGHT 5", down="1st", distance="10")
    # "55" is the Canadian centre line and round-trips as coord 55
    assert RulesService.spot_to_coord("55", holder["state"]) == 55
    assert RulesService.coord_to_spot(55, holder["state"]) == "55"
    rules.play({"team": "visitor", "play_type": "pass", "start_spot": "RIGHT 5", "end_spot": "55",
                "pass_outcome": "complete", "passer_number": "14", "receiver_number": "88"})
    assert holder["state"]["ball_spot"] == "55"
    rules.play({"team": "visitor", "play_type": "run", "start_spot": "55", "end_spot": "LEFT 52", "player_number": "22"})
    assert "LEFT 52" in str(holder["state"]["ball_spot"])       # a spot past the 50 exists on 110
    r = rules.play({"team": "visitor", "play_type": "run", "start_spot": "LEFT 52", "end_spot": "LEFT GOAL", "player_number": "22"})
    assert r.data["play"]["touchdown"] is True
    assert holder["state"]["visitor_score"] == 6


def test_operator_field_state_readout_is_at_110_scale() -> None:
    ca = dict(_initial_state(), ball_spot="RIGHT 15", possession="home", home_direction="right")
    fs = CanonicalStateFoundation.field_state(ca)
    assert fs["length_yards"] == 110
    assert fs["end_zone_depth_yards"] == 20
    assert fs["yards_to_goal"] == 15
    assert fs["red_zone"] is True
    assert CanonicalStateFoundation.field_state(dict(ca, ball_spot="50"))["yards_to_goal"] == 60


def test_no_fair_catch_signal_is_ignored_on_a_canadian_punt() -> None:
    holder = {"state": _initial_state()}
    rules, _ = _build(holder)
    holder["state"].update(possession="home", ball_spot="LEFT 40", down="1st", distance="10", quarter="2")
    r = rules.play({"team": "home", "play_type": "punt", "start_spot": "LEFT 40", "landing_spot": "RIGHT 25",
                    "end_spot": "RIGHT 32", "kicker_number": "7", "returner_number": "27", "fair_catch": True})
    res = str(r.data["play"]["result"]).lower()
    assert "fair catch" not in res
    assert "returned by" in res


def test_rouge_single_scores_one_and_restarts_the_other_team_at_its_35() -> None:
    holder = {"state": _initial_state()}
    _, events = _build(holder)
    r = events.trigger({"team": "home", "event": "SINGLE", "source": "statistician"})
    assert r.ok
    assert holder["state"]["home_score"] == 1
    assert holder["state"]["possession"] == "visitor"
    assert holder["state"]["special_game_phase"] == ""
    assert holder["state"]["ball_spot"] == "RIGHT 35"          # visitor own 35 on the 110 field
    assert holder["state"]["events"][-1]["event"] == "SINGLE"
    assert holder["state"]["events"][-1]["score_delta"] == 1


def test_field_goal_play_is_still_cleanly_rejected_for_a_canadian_broadcast() -> None:
    ca = ruleset_service.resolve(country="CA", region="ON", association="CJFL", sport="football")
    assert "field_goal" not in ruleset_service.valid_play_types(ca)
    holder = {"state": _initial_state()}
    rules, _ = _build(holder)
    r = rules.play({"team": "home", "play_type": "field_goal", "start_spot": "LEFT 30",
                    "end_spot": "LEFT 45", "kicker_number": "7"})
    assert r.code == "INVALID_PLAY"
