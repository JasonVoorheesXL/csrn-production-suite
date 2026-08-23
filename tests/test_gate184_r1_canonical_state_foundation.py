from __future__ import annotations

import copy
from threading import Lock

from canonical_state_service import CanonicalStateFoundation
from rules_service import RulesService


def base_state():
    return {
        "broadcast_id": "TEST-GAME",
        "home_team": "Pine Valley",
        "visitor_team": "Northwood",
        "home_school_id": "pine-valley",
        "visitor_school_id": "northwood",
        "sport": "Football",
        "status": "live",
        "broadcast_phase": "live",
        "game_data_authority": "statistician",
        "home_score": 0,
        "visitor_score": 0,
        "possession": "home",
        "down": "1st",
        "distance": "10",
        "ball_spot": "LEFT 25",
        "quarter": "1",
        "clock_seconds": 720,
        "clock_visible": True,
        "clock_running": False,
        "clock_started_at": 0,
        "home_direction": "right",
        "visitor_direction": "left",
        "history": [],
        "events": [],
        "plays": [],
        "next_play_number": 1,
    }


def test_team_role_resolver_and_penalty_default_inverse():
    state = base_state()
    roles = CanonicalStateFoundation.team_roles(state)
    assert roles.offense == "home"
    assert roles.defense == "visitor"
    assert CanonicalStateFoundation.penalty_unit(state, "home") == "Offensive"
    assert CanonicalStateFoundation.penalty_unit(state, "visitor") == "Defensive"
    state["possession"] = "visitor"
    roles = CanonicalStateFoundation.team_roles(state)
    assert roles.offense == "visitor"
    assert roles.defense == "home"
    assert CanonicalStateFoundation.penalty_unit(state, "visitor") == "Offensive"
    assert CanonicalStateFoundation.penalty_unit(state, "home") == "Defensive"


def test_canonical_field_state_is_single_serializable_projection():
    state = base_state()
    projection = CanonicalStateFoundation.field_state(state)
    assert projection["ball_spot"] == state["ball_spot"]
    assert projection["possession"] == state["possession"]
    assert projection["down"] == state["down"]
    assert projection["distance"] == state["distance"]
    assert projection["drive_direction"] == state["home_direction"]
    assert projection["quarter"] == state["quarter"]
    assert projection["home_score"] == state["home_score"]
    assert projection["visitor_score"] == state["visitor_score"]


def make_rules_service(state, resolver):
    holder = {"state": copy.deepcopy(state)}
    def load_state():
        return copy.deepcopy(holder["state"])
    def save_state(next_state):
        holder["state"] = copy.deepcopy(dict(next_state))
    def push_history(current):
        current.setdefault("history", []).append(copy.deepcopy({k: v for k, v in current.items() if k != "history"}))
    service = RulesService(
        load_state=load_state,
        save_state=save_state,
        push_history=push_history,
        source_allowed=lambda _state, source: source == "statistician",
        locked_payload=lambda _state: {},
        resolve_player=resolver,
        show_player_graphic=lambda *args, **kwargs: None,
        transaction_lock=Lock(),
        now=lambda: 1000.0,
    )
    return service, holder


def test_wrong_team_offensive_play_is_rejected_before_stats_record_creation():
    state = base_state()
    def resolver(_state, team, number):
        if team == "visitor" and str(number) == "22":
            return {"number": "22", "name": "Northwood Defender", "resolved": True}
        return {"number": str(number or ""), "name": "", "resolved": False}
    service, holder = make_rules_service(state, resolver)
    result = service.play({
        "team": "visitor",
        "play_type": "run",
        "player_number": "22",
        "start_spot": "LEFT 25",
        "end_spot": "LEFT 30",
    })
    assert result.code == "TEAM_ROLE_MISMATCH"
    assert holder["state"]["plays"] == []
    assert holder["state"]["events"] == []


def test_wrong_team_jersey_on_possessing_team_request_is_rejected():
    state = base_state()
    def resolver(_state, team, number):
        # #22 only exists for Northwood, never for Pine Valley.
        if team == "visitor" and str(number) == "22":
            return {"number": "22", "name": "Northwood Defender", "resolved": True}
        return {"number": str(number or ""), "name": "", "resolved": False}
    service, holder = make_rules_service(state, resolver)
    result = service.play({
        "team": "home",
        "play_type": "run",
        "player_number": "22",
        "player_name": "Northwood Defender",
        "start_spot": "LEFT 25",
        "end_spot": "LEFT 30",
    })
    assert result.code == "PLAYER_TEAM_MISMATCH"
    assert holder["state"]["plays"] == []


def test_unknown_jersey_remains_recordable_and_unresolved():
    state = base_state()
    def resolver(_state, team, number):
        return {"number": str(number or ""), "name": "", "resolved": False}
    service, holder = make_rules_service(state, resolver)
    result = service.play({
        "team": "home",
        "play_type": "run",
        "player_number": "99",
        "start_spot": "LEFT 25",
        "end_spot": "LEFT 26",
    })
    assert result.code == "OK"
    assert result.data["play"]["unresolved_players"] == ["player"]
    assert len(holder["state"]["plays"]) == 1

def test_rebuild_run_then_undo_restores_exact_pre_run_field_state():
    state = base_state()
    before = CanonicalStateFoundation.snapshot(state)
    play = {
        "play_id": "P1", "event_id": "E1", "play_number": 1,
        "offense": "home", "play_type": "run", "yards": 5,
        "ball_spot": "LEFT 25", "end_spot": "LEFT 30",
    }
    event = {
        "id": "E1", "play_id": "P1", "play_number": 1, "event": "PLAY",
        "before": copy.deepcopy(before), "after": {}, "created_at": 1,
    }
    after = CanonicalStateFoundation.rebuild(state, [event], [play], baseline=before)
    assert after["ball_spot"] == "LEFT 30"
    assert after["down"] == "2nd"
    assert after["distance"] == "5"
    restored = CanonicalStateFoundation.rebuild(after, [], [], baseline=before)
    for key, value in before.items():
        assert restored[key] == value


def test_rebuild_first_down_and_edit_yardage_updates_down_distance_and_spot():
    state = base_state()
    before = CanonicalStateFoundation.snapshot(state)
    p1 = {
        "play_id": "P1", "event_id": "E1", "play_number": 1,
        "offense": "home", "play_type": "run", "yards": 12,
        "ball_spot": "LEFT 25", "end_spot": "LEFT 37",
    }
    e1 = {"id": "E1", "play_id": "P1", "play_number": 1, "event": "PLAY", "before": copy.deepcopy(before), "after": {}, "created_at": 1}
    rebuilt = CanonicalStateFoundation.rebuild(state, [e1], [p1], baseline=before)
    assert rebuilt["ball_spot"] == "LEFT 37"
    assert rebuilt["down"] == "1st"
    assert rebuilt["distance"] == "10"
    p1["yards"] = 4
    rebuilt2 = CanonicalStateFoundation.rebuild(rebuilt, [e1], [p1], baseline=before)
    assert rebuilt2["ball_spot"] == "LEFT 29"
    assert rebuilt2["down"] == "2nd"
    assert rebuilt2["distance"] == "6"
    assert len(rebuilt2["plays"]) == 1
    assert len(rebuilt2["events"]) == 1


def test_rebuild_scoring_and_possession_changing_snapshots_are_deterministic():
    state = base_state()
    before = CanonicalStateFoundation.snapshot(state)
    score_event = {
        "id": "E1", "play_id": "P1", "play_number": 1, "event": "TD", "created_at": 1,
        "before": copy.deepcopy(before),
        "after": {**before, "home_score": 6},
    }
    rebuilt = CanonicalStateFoundation.rebuild(state, [score_event], [], baseline=before)
    assert rebuilt["home_score"] == 6
    restored = CanonicalStateFoundation.rebuild(rebuilt, [], [], baseline=before)
    assert restored["home_score"] == 0
    turnover = {
        "id": "E2", "play_id": "P2", "play_number": 1, "event": "TURNOVER", "created_at": 1,
        "before": copy.deepcopy(before),
        "after": {**before, "possession": "visitor", "down": "1st", "distance": "10"},
    }
    changed = CanonicalStateFoundation.rebuild(state, [turnover], [], baseline=before)
    assert changed["possession"] == "visitor"
    restored2 = CanonicalStateFoundation.rebuild(changed, [], [], baseline=before)
    assert restored2["possession"] == "home"


def test_multiple_rebuilds_do_not_duplicate_canonical_records():
    state = base_state()
    before = CanonicalStateFoundation.snapshot(state)
    play = {"play_id": "P1", "event_id": "E1", "play_number": 1, "offense": "home", "play_type": "run", "yards": 3}
    event = {"id": "E1", "play_id": "P1", "play_number": 1, "event": "PLAY", "before": copy.deepcopy(before), "after": {}, "created_at": 1}
    first = CanonicalStateFoundation.rebuild(state, [event], [play], baseline=before)
    second = CanonicalStateFoundation.rebuild(first, first["events"], first["plays"], baseline=before)
    assert [e["id"] for e in second["events"]] == ["E1"]
    assert [p["play_id"] for p in second["plays"]] == ["P1"]


def test_browser_serialization_contains_exact_backend_canonical_projection():
    from state_service import StateService
    state = base_state()
    service = StateService(
        load_raw=lambda: copy.deepcopy(state),
        replace_raw=lambda value: copy.deepcopy(dict(value)),
        default_state=base_state,
    )
    public = service.public(state).data["state"]
    assert public["canonical_field_state"] == CanonicalStateFoundation.field_state(state)
    assert public["team_roles"] == CanonicalStateFoundation.team_roles(state).as_dict()
    assert public["canonical_field_state"]["ball_spot"] == public["ball_spot"]
    assert public["canonical_field_state"]["possession"] == public["possession"]
    assert public["canonical_field_state"]["down"] == public["down"]
    assert public["canonical_field_state"]["distance"] == public["distance"]


