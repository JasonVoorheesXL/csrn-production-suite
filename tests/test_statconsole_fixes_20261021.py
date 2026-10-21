"""Statistician Console display/behaviour quirks found while driving demo game
FB-DEMO-GUIDE-001 for the statistician guide (2026-10-21):

1. Play Register text: non-completions were rewritten as "complete to #".
2. Field Position "Ball:" label named the halves home/visitor regardless of
   which end each team defends.
3. A score in overtime entered a kickoff phase that NFHS overtime never has.
"""

from __future__ import annotations

import copy
from pathlib import Path
from threading import Lock

import pytest

from canonical_state_service import CanonicalStateFoundation
from event_service import EventService
from period_service import PeriodService
from rules_service import RulesService
from state_service import StateService

HTML = (Path(__file__).resolve().parents[1] / "templates" / "index.html").read_text(encoding="utf-8")

ROSTERS = {
    ("home", "7"): "Marcus Hale",
    ("home", "11"): "Wide Out",
    ("home", "22"): "Tail Back",
    ("visitor", "99"): "Hunter Graves",
    ("visitor", "35"): "Jackson Bell",
}


def _resolver(_state, team, number):
    name = ROSTERS.get((team, str(number)))
    if not name:
        return {"resolved": False, "number": str(number or "")}
    return {"resolved": True, "number": str(number), "name": name, "player_id": f"{team}-{number}"}


def _base_state(**patch):
    state = {
        "broadcast_id": "TEST", "home_team": "Pine Valley", "visitor_team": "Northwood",
        "sport": "Football", "status": "live", "broadcast_phase": "live",
        "game_data_authority": "statistician", "home_score": 0, "visitor_score": 0,
        "possession": "home", "down": "1st", "distance": "10", "ball_spot": "LEFT 30",
        "quarter": "2", "period_state": "quarter", "clock_seconds": 500, "clock_visible": True,
        "clock_running": False, "clock_started_at": 0,
        "home_direction": "right", "visitor_direction": "left", "special_game_phase": "",
        "kicking_team": "", "receiving_team": "", "history": [], "events": [], "plays": [],
        "next_play_number": 1,
    }
    state.update(patch)
    return state


def _rules(state):
    holder = {"state": copy.deepcopy(state)}

    def save(value):
        holder["state"] = copy.deepcopy(dict(value))

    svc = RulesService(
        load_state=lambda: copy.deepcopy(holder["state"]), save_state=save, push_history=lambda s: None,
        source_allowed=lambda s, src: True, locked_payload=lambda s: {}, resolve_player=_resolver,
        show_player_graphic=lambda *a, **k: None, transaction_lock=Lock(), now=lambda: 1000.0,
    )
    return svc, holder


def _events(state):
    holder = {"state": copy.deepcopy(state)}

    def save(value):
        holder["state"] = copy.deepcopy(dict(value))

    players = {"h1": {"id": "h1", "number": "4", "name": "Home Kicker"}}
    svc = EventService(
        load_state=lambda: copy.deepcopy(holder["state"]), save_state=save,
        public_state=lambda s: copy.deepcopy(dict(s)),
        push_history=lambda s: s.setdefault("history", []),
        update_linked_status=lambda *a, **k: None,
        automation_player=lambda _r, pid: ({"id": "r"}, players[pid]) if pid in players else (None, None),
        manual_player=lambda m, t, *a: m, player_display=lambda p: str((p or {}).get("name") or ""),
        show_player_graphic=lambda *a, **k: None, apply_penalty=lambda *a, **k: {},
        spot_to_coord=lambda v, *_a: RulesService.spot_to_coord(v),
        team_direction=lambda st, team: RulesService.team_direction(st, team),
        normalize_state=lambda s: copy.deepcopy(dict(s)), default_player_graphic=lambda: {},
        transaction_lock=Lock(), now=lambda: 1000.0,
    )
    return svc, holder


def _public_plays(state, resolve=_resolver):
    service = StateService(
        load_raw=lambda: dict(state), replace_raw=lambda s: dict(s),
        default_state=lambda: {}, resolve_player=resolve,
    )
    return service.public(dict(state)).data["state"]["plays"]


def _js_function(name: str) -> str:
    start = HTML.index(f"function {name}(")
    return HTML[start: HTML.index("\nfunction ", start + 1)]


# --- 1. Play Register description -------------------------------------------


@pytest.mark.parametrize(
    "payload,outcome,expected",
    [
        ({"pass_outcome": "sack", "sacker_number": "99", "end_spot": "LEFT 24"}, "sack",
         "#7 Marcus Hale sacked by #99 Hunter Graves for -6 yards"),
        ({"pass_outcome": "incomplete", "receiver_number": "11"}, "incomplete",
         "#7 Marcus Hale pass incomplete, intended for #11 Wide Out"),
        ({"pass_outcome": "interception", "returner_number": "35", "end_spot": "LEFT 45",
          "turnover_spot": "LEFT 45", "return_end_spot": "LEFT 40"}, "interception",
         "#7 Marcus Hale pass intercepted by #35 Jackson Bell at LEFT 45"),
        ({"pass_outcome": "complete", "receiver_number": "11", "end_spot": "LEFT 38"}, "complete",
         "#7 Marcus Hale complete to #11 Wide Out for 8 yards"),
    ],
)
def test_pass_play_records_persist_their_outcome_and_display_unchanged(payload, outcome, expected) -> None:
    svc, holder = _rules(_base_state())
    result = svc.play({"team": "home", "play_type": "pass", "passer_number": "7",
                       "start_spot": "LEFT 30", **payload})
    assert result.ok, result.code
    play = holder["state"]["plays"][-1]
    assert play["pass_outcome"] == outcome
    assert play["result"].startswith(expected)
    shown = _public_plays(holder["state"])[-1]["result"]
    assert shown == play["result"]
    assert "complete to #" not in shown or outcome == "complete"


def test_non_pass_play_records_store_an_empty_pass_outcome() -> None:
    svc, holder = _rules(_base_state())
    assert svc.play({"team": "home", "play_type": "run", "player_number": "22",
                     "start_spot": "LEFT 30", "end_spot": "LEFT 34"}).ok
    assert holder["state"]["plays"][-1]["pass_outcome"] == ""


def test_lost_fumble_detail_survives_enrichment() -> None:
    svc, holder = _rules(_base_state())
    assert svc.play({"team": "home", "play_type": "run", "player_number": "22",
                     "start_spot": "LEFT 30", "end_spot": "LEFT 36", "fumble": True,
                     "fumble_lost": True, "returner_number": "35",
                     "turnover_spot": "LEFT 36", "return_end_spot": "LEFT 36"}).ok
    stored = holder["state"]["plays"][-1]["result"]
    assert "fumble lost, recovered by #35 Jackson Bell" in stored
    assert _public_plays(holder["state"])[-1]["result"] == stored


def test_legacy_pass_record_without_pass_outcome_uses_its_label() -> None:
    legacy = {
        "play_id": "P1", "play_number": 1, "offense": "home", "defense": "visitor",
        "play_type": "pass", "label": "Sack", "yards": -6,
        "result": "#7 Marcus Hale sacked by #99 Hunter Graves for -6 yards",
        "passer_number": "7", "passer_name": "Marcus Hale",
        "receiver_number": "", "receiver_name": "", "sacker_number": "99",
    }
    shown = _public_plays(_base_state(plays=[legacy]))[-1]["result"]
    assert shown == legacy["result"]


def test_completion_still_picks_up_a_receiver_name_resolved_after_entry() -> None:
    play = {
        "play_id": "P1", "play_number": 1, "offense": "home", "defense": "visitor",
        "play_type": "pass", "pass_outcome": "complete", "label": "Pass", "yards": 12,
        "first_down": True, "result": "#7 Marcus Hale complete to #11 for 12 yards, first down",
        "passer_number": "7", "passer_name": "Marcus Hale", "receiver_number": "11", "receiver_name": "",
    }
    shown = _public_plays(_base_state(plays=[play]))[-1]["result"]
    assert shown == "#7 Marcus Hale complete to #11 Wide Out for 12 yards, first down"


def test_console_rewrite_only_targets_plain_runs_and_completions() -> None:
    body = _js_function("resolvedPlayDisplay")
    assert "const plain=!['fumble','fumble_lost','turnover','safety','muffed_punt'].some(k=>p[k]);" in body
    assert "playPassOutcome(p)==='complete'" in body
    assert "!stored.includes(p.player_name)" in body and "!stored.includes(p.receiver_name)" in body
    # the old default that read every pass as a completion is gone
    assert "String(p.pass_outcome||'complete')" not in HTML
    helper = _js_function("playPassOutcome")
    assert "'sack':'sack'" in helper and "'incomplete pass':'incomplete'" in helper


# --- 2. Field Position "Ball:" label ------------------------------------------


def test_ball_label_names_each_half_by_the_team_defending_that_goal() -> None:
    body = _js_function("teamSpotFromCoord")
    assert "const homeDrivesLeft=String(currentState?.home_direction||'right').toLowerCase()==='left';" in body
    assert "const leftName=homeDrivesLeft?visitorName:homeName,rightName=homeDrivesLeft?homeName:visitorName;" in body
    assert "const leftName=currentState?.home_team||'HOME'" not in body


# --- 3. No kickoff after an overtime score --------------------------------------


def _ot_state(**patch):
    return _base_state(quarter="OT", period_state="overtime", ball_spot="RIGHT 10",
                       possession="home", **patch)


def test_made_field_goal_in_overtime_does_not_require_a_kickoff() -> None:
    svc, holder = _events(_ot_state())
    r = svc.trigger({"team": "home", "event": "FG", "source": "statistician",
                     "player_id": "h1", "kick_outcome": "made"})
    assert r.ok and holder["state"]["home_score"] == 3
    state = holder["state"]
    assert state["special_game_phase"] == ""
    assert (state["kicking_team"], state["receiving_team"]) == ("", "")


def test_try_after_an_overtime_touchdown_does_not_require_a_kickoff() -> None:
    svc, holder = _events(_ot_state())
    assert svc.trigger({"team": "home", "event": "TD", "source": "statistician",
                        "player_id": "h1", "play_type": "rush"}).ok
    assert holder["state"]["special_game_phase"] == "pending_try"
    assert svc.trigger({"team": "home", "event": "XP", "source": "statistician",
                        "player_id": "h1", "conversion_outcome": "good"}).ok
    assert holder["state"]["home_score"] == 7
    assert holder["state"]["special_game_phase"] == ""


def test_regulation_field_goal_still_enters_kickoff() -> None:
    svc, holder = _events(_base_state())
    assert svc.trigger({"team": "home", "event": "FG", "source": "statistician",
                        "player_id": "h1", "kick_outcome": "made"}).ok
    assert holder["state"]["special_game_phase"] == "kickoff"
    assert holder["state"]["kicking_team"] == "home"


@pytest.mark.parametrize("quarter,period_state", [("OT", "overtime"), ("OT", "overtime_complete"), ("3", "overtime")])
def test_enter_kickoff_is_a_no_op_phase_in_overtime(quarter, period_state) -> None:
    state = _base_state(quarter=quarter, period_state=period_state)
    CanonicalStateFoundation.enter_kickoff(state, "visitor")
    assert state["special_game_phase"] == ""
    assert state["possession"] == "visitor"


def test_ot_score_then_end_period_and_confirm_final_has_no_kickoff() -> None:
    svc, holder = _events(_ot_state())
    assert svc.trigger({"team": "home", "event": "FG", "source": "statistician",
                        "player_id": "h1", "kick_outcome": "made"}).ok
    ended = PeriodService.transition(holder["state"], "end_quarter")
    assert ended.ok and ended.data["transition"] == "OVERTIME_COMPLETE"
    final = PeriodService.transition(ended.state, "final_game")
    assert final.ok and final.state["special_game_phase"] == ""


def test_confirm_final_clears_a_leftover_regulation_kickoff_phase() -> None:
    state = _base_state(quarter="4", period_state="q4_complete")
    CanonicalStateFoundation.enter_kickoff(state, "home")
    assert state["special_game_phase"] == "kickoff"
    final = PeriodService.transition(state, "final_game")
    assert final.ok
    assert (final.state["special_game_phase"], final.state["kicking_team"], final.state["receiving_team"]) == ("", "", "")
