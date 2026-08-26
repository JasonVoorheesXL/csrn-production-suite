from __future__ import annotations

import threading
from pathlib import Path

from rules_service import RulesService
from statistics_service import StatisticsService


def base_state():
    return {
        "broadcast_id": "GAME-1",
        "sport": "Football",
        "home_team": "Pine Valley",
        "visitor_team": "Northwood",
        "home_score": 0,
        "visitor_score": 0,
        "possession": "home",
        "down": "1st",
        "distance": "10",
        "ball_spot": "LEFT 20",
        "quarter": "1",
        "clock_seconds": 600,
        "clock_running": False,
        "clock_visible": True,
        "home_direction": "right",
        "visitor_direction": "left",
        "broadcast_phase": "live",
        "special_game_phase": "",
        "events": [],
        "plays": [],
        "next_play_number": 1,
        "statistician_enabled": True,
        "game_data_authority": "statistician",
    }


def play(**kw):
    row={
        "play_id":"P1","event_id":"E1","play_number":1,"broadcast_id":"GAME-1",
        "offense":"home","defense":"visitor","play_type":"run","yards":0,"undone":False,
        "player_number":"5","player_name":"Isaiah Johnson",
    }
    row.update(kw)
    return row


def event(**kw):
    row={
        "id":"E1","play_id":"P1","play_number":1,"broadcast_id":"GAME-1",
        "team":"home","event":"PLAY","score_delta":0,"quarter":"1","undone":False,
        "automation":{},"after":{"home_score":0,"visitor_score":0},
    }
    row.update(kw)
    return row


def stats(state):
    return StatisticsService(now=lambda: 1).report(state).data["statistics"]


def get_player(report, team, number):
    return next(p for p in report["players"] if p["team"]==team and p["number"]==str(number))


def test_rushing_gains_losses_and_reconciliation():
    s=base_state()
    s["plays"]=[
        play(play_id="P1",event_id="E1",play_number=1,yards=12),
        play(play_id="P2",event_id="E2",play_number=2,yards=-5),
    ]
    r=stats(s); p=get_player(r,"home",5)
    assert r["teams"]["home"]["rushing_attempts"]==2
    assert r["teams"]["home"]["rushing_yards"]==7
    assert p["rushing_attempts"]==2 and p["rushing_yards"]==7
    assert r["reconciliation"]["rushing_reconciled"] is True


def test_passing_receiving_targets_include_incomplete_without_fake_reception():
    s=base_state()
    s["plays"]=[
        play(play_id="P1",event_id="E1",play_number=1,play_type="pass",yards=18,
             passer_number="2",passer_name="Drew Mason",receiver_number="7",receiver_name="Jaylen Cooper",pass_outcome="complete",player_number="7",player_name="Jaylen Cooper"),
        play(play_id="P2",event_id="E2",play_number=2,play_type="pass",yards=0,
             passer_number="2",passer_name="Drew Mason",receiver_number="7",receiver_name="Jaylen Cooper",pass_outcome="incomplete",player_number="7",player_name="Jaylen Cooper"),
    ]
    r=stats(s); qb=get_player(r,"home",2); wr=get_player(r,"home",7)
    assert (qb["completions"],qb["pass_attempts"],qb["passing_yards"])==(1,2,18)
    assert (wr["receptions"],wr["targets"],wr["receiving_yards"])==(1,2,18)
    assert r["reconciliation"]["passing_reconciled"] is True
    assert r["reconciliation"]["receiving_reconciled"] is True


def test_special_teams_return_and_kicker_production():
    s=base_state()
    s["plays"]=[play(play_type="kickoff",offense="visitor",defense="home",kicking_team="home",yards=0,
                     return_yards=27,returner_number="8",returner_name="Return Guy",player_number="8",player_name="Return Guy",
                     kicker_number="3",kicker_name="Kicker",result="Kickoff returned for 27 yards")]
    r=stats(s); ret=get_player(r,"visitor",8); kicker=get_player(r,"home",3)
    assert r["teams"]["visitor"]["kickoff_returns"]==1
    assert r["teams"]["visitor"]["kickoff_return_yards"]==27
    assert ret["kickoff_returns"]==1 and ret["kickoff_return_yards"]==27
    assert kicker["kickoffs"]==1 and r["teams"]["home"]["kickoffs"]==1
    assert r["reconciliation"]["returns_reconciled"] is True


def test_defensive_sack_interception_and_fumble_recovery_credit():
    s=base_state()
    s["plays"]=[
        play(play_id="P1",event_id="E1",play_type="pass",pass_outcome="sack",yards=-8,passer_number="2",passer_name="QB",sacker_number="44",sacker_name="Edge",player_number="",player_name=""),
        play(play_id="P2",event_id="E2",play_number=2,play_type="pass",pass_outcome="interception",turnover=True,turnover_type="interception",turnover_player_number="9",turnover_player_name="DB",passer_number="2",passer_name="QB",player_number="",player_name=""),
        play(play_id="P3",event_id="E3",play_number=3,play_type="run",yards=4,turnover=True,turnover_type="fumble_recovery",turnover_player_number="55",turnover_player_name="LB",fumble=True,fumble_lost=True),
    ]
    r=stats(s)
    assert r["teams"]["visitor"]["sacks"]==1
    assert r["teams"]["visitor"]["turnovers_gained"]==2
    assert r["teams"]["visitor"]["interceptions_gained"]==1
    assert r["teams"]["visitor"]["fumble_recoveries"]==1
    assert get_player(r,"visitor",44)["sacks"]==1
    assert get_player(r,"visitor",9)["interceptions"]==1
    assert get_player(r,"visitor",55)["fumble_recoveries"]==1


def test_kicking_attempts_distinguish_made_and_missed_events():
    s=base_state(); s["events"]=[
        event(id="F1",play_id="F1P",event="FG",score_delta=3,kick_outcome="made",automation={"player_number":"3","player_name":"Kicker"}),
        event(id="F2",play_id="F2P",event="FG",score_delta=0,kick_outcome="no_good",automation={"player_number":"3","player_name":"Kicker"}),
        event(id="X1",play_id="X1P",event="XP",score_delta=1,conversion_outcome="good",automation={"player_number":"3","player_name":"Kicker"}),
        event(id="X2",play_id="X2P",event="XP",score_delta=0,conversion_outcome="blocked",automation={"player_number":"3","player_name":"Kicker"}),
    ]
    r=stats(s); p=get_player(r,"home",3)
    assert (r["teams"]["home"]["field_goals"],r["teams"]["home"]["field_goal_attempts"])==(1,2)
    assert (r["teams"]["home"]["extra_points"],r["teams"]["home"]["extra_point_attempts"])==(1,2)
    assert (p["field_goals"],p["field_goal_attempts"])==(1,2)
    assert (p["extra_points"],p["extra_point_attempts"])==(1,2)


def test_incomplete_rules_play_keeps_intended_receiver_and_description():
    state=base_state()
    roster={
        ("home","2"): {"resolved":True,"number":"2","name":"Drew Mason","player_id":"p2","roster_id":"r"},
        ("home","7"): {"resolved":True,"number":"7","name":"Jaylen Cooper","player_id":"p7","roster_id":"r"},
    }
    def load(): return state
    def save(value): state.clear(); state.update(value)
    svc=RulesService(load_state=load,save_state=save,push_history=lambda s:None,source_allowed=lambda s,a:True,locked_payload=lambda s:{},
        resolve_player=lambda s,t,n: roster.get((t,str(n)),{"resolved":False,"number":str(n)}),show_player_graphic=lambda *a,**k:None,
        # play() acquires/releases this lock directly (for lock-wait-time
        # diagnostics logging), not just via `with self._transaction_lock:` --
        # nullcontext() has no .acquire()/.release(), so this raised
        # AttributeError on every call, silently failing this test.
        transaction_lock=threading.Lock(),now=lambda:10)
    result=svc.play({"team":"home","play_type":"pass","start_spot":"LEFT 20","end_spot":"LEFT 20","pass_outcome":"incomplete","passer_number":"2","receiver_number":"7"})
    assert result.ok
    row=result.data["play"]
    assert row["intended_receiver_number"]=="7"
    assert row["intended_receiver_name"]=="Jaylen Cooper"
    assert "incomplete, intended for #7 Jaylen Cooper" in row["result"]



def test_legacy_completed_pass_uses_player_fields_for_receiver_credit():
    s=base_state()
    s["plays"]=[play(play_type="pass",pass_outcome="complete",yards=18,
        passer_number="12",passer_name="Jason Quarterback",
        receiver_number="",receiver_name="",player_number="22",player_name="Jordan Receiver")]
    r=stats(s); wr=get_player(r,"home",22)
    assert wr["targets"]==1
    assert wr["receptions"]==1
    assert wr["receiving_yards"]==18


def test_incomplete_does_not_use_legacy_player_fields_as_fake_receiver():
    s=base_state()
    s["plays"]=[play(play_type="pass",pass_outcome="incomplete",yards=0,
        passer_number="12",passer_name="Jason Quarterback",
        receiver_number="",receiver_name="",intended_receiver_number="",intended_receiver_name="",
        player_number="22",player_name="Jordan Receiver")]
    r=stats(s)
    rows=[p for p in r["players"] if p["team"]=="home" and p["number"]=="22"]
    assert rows == [] or (rows[0]["targets"]==0 and rows[0]["receptions"]==0)

def test_statistics_ui_exposes_full_production_and_reconciliation():
    text=(Path(__file__).resolve().parents[1]/"templates"/"index.html").read_text(encoding="utf-8")
    assert "Individual Production" in text
    assert "Canonical reconciliation: PASS" in text
    assert "p.rushing_attempts" in text and "p.targets" in text
    assert "p.kickoff_return_yards" in text and "p.sacks" in text
    assert "['complete','incomplete'].includes(o)" in text


