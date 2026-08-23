from __future__ import annotations

import copy
from pathlib import Path
from threading import Lock

from canonical_state_service import CanonicalStateFoundation
from eligibility_service import EligibilityService
from event_service import EventService
from rules_service import RulesService


def base_state():
    return {
        "broadcast_id":"TEST","home_team":"Pine Valley","visitor_team":"Northwood",
        "home_school_id":"pv","visitor_school_id":"nw","sport":"Football","status":"live",
        "broadcast_phase":"live","game_data_authority":"statistician","home_score":0,"visitor_score":0,
        "possession":"home","down":"1st","distance":"10","ball_spot":"LEFT 25","quarter":"1",
        "clock_seconds":600,"clock_visible":True,"clock_running":False,"clock_started_at":0,
        "home_direction":"right","visitor_direction":"left","special_game_phase":"","kicking_team":"",
        "receiving_team":"","history":[],"events":[],"plays":[],"next_play_number":1,
    }

PLAYERS = {
    ("home","7"): {"id":"h7","number":"7","name":"Home Seven","preferred_name":"Home Seven"},
    ("home","8"): {"id":"h8","number":"8","name":"Home Eight","preferred_name":"Home Eight"},
    ("visitor","2"): {"id":"v2","number":"2","name":"Visitor Two","preferred_name":"Visitor Two"},
}

def resolver(_state, team, number):
    player=PLAYERS.get((str(team),str(number)))
    if not player:
        return {"number":str(number or ""),"name":"","resolved":False}
    return {"number":player["number"],"name":player["name"],"resolved":True,"player_id":player["id"],"roster_id":f"{team}-roster"}


def event_service(state):
    holder={"state":copy.deepcopy(state)}
    def load(): return copy.deepcopy(holder["state"])
    def save(v): holder["state"]=copy.deepcopy(dict(v))
    def hist(v): v.setdefault("history",[]).append(copy.deepcopy({k:x for k,x in v.items() if k!="history"}))
    by_id={p["id"]:p for p in PLAYERS.values()}
    def ap(_roster,pid): return ({"id":_roster or "r"},copy.deepcopy(by_id.get(pid))) if pid in by_id else (None,None)
    svc=EventService(
        load_state=load,save_state=save,public_state=lambda s:copy.deepcopy(dict(s)),push_history=hist,
        update_linked_status=lambda *a,**k:None,automation_player=ap,manual_player=lambda m,t:m,
        player_display=lambda p:str((p or {}).get("preferred_name") or (p or {}).get("name") or ""),
        show_player_graphic=lambda *a,**k:None,apply_penalty=lambda *a,**k:{},
        spot_to_coord=RulesService.spot_to_coord,team_direction=RulesService.team_direction,
        normalize_state=lambda s:copy.deepcopy(dict(s)),default_player_graphic=lambda:{},
        resolve_player=resolver,transaction_lock=Lock(),now=lambda:1000.0,
    )
    return svc,holder


def rules_service(state):
    holder={"state":copy.deepcopy(state)}
    def load(): return copy.deepcopy(holder["state"])
    def save(v): holder["state"]=copy.deepcopy(dict(v))
    def hist(v): v.setdefault("history",[]).append(copy.deepcopy({k:x for k,x in v.items() if k!="history"}))
    svc=RulesService(
        load_state=load,save_state=save,push_history=hist,
        source_allowed=lambda s,src:src=="statistician",locked_payload=lambda s:{},
        resolve_player=resolver,show_player_graphic=lambda *a,**k:None,
        transaction_lock=Lock(),now=lambda:1000.0,
    )
    return svc,holder


def ejection_event(team="home", number="7", player_id="h7", event_id="EJ1"):
    return {
        "id":event_id,"play_id":f"P-{event_id}","play_number":1,"created_at":1,
        "team":team,"event":"EJECTION","before":CanonicalStateFoundation.snapshot(base_state()),
        "after":CanonicalStateFoundation.snapshot(base_state()),
        "ejection":{"person_type":"Player","person_name":number,"reason":"Fighting","player_id":player_id,"player_number":number,"player_name":"Home Seven"},
    }


def test_eligibility_is_derived_from_active_ejection_history():
    st=base_state(); st["events"]=[ejection_event()]
    derived=EligibilityService.derive(st,resolve_player=resolver)
    assert derived["home"]["ejected"][0]["player_id"]=="h7"
    assert not EligibilityService.is_eligible(st,"home",player_id="h7",number="7",resolve_player=resolver)
    assert EligibilityService.is_eligible(st,"home",player_id="h8",number="8",resolve_player=resolver)


def test_non_player_ejection_does_not_remove_player():
    st=base_state(); ev=ejection_event(); ev["ejection"]["person_type"]="Head Coach"; st["events"]=[ev]
    assert EligibilityService.derive(st,resolve_player=resolver)["home"]["ejected"]==[]


def test_ejection_record_enriches_player_identity_without_mutating_roster():
    svc,h=event_service(base_state())
    r=svc.trigger({"team":"home","event":"EJECTION","source":"statistician","ejection_person_type":"Player","ejection_person_name":"7","ejection_reason":"Fighting"})
    assert r.ok
    eject=h["state"]["events"][-1]["ejection"]
    assert eject["player_id"]=="h7" and eject["player_number"]=="7"
    assert PLAYERS[("home","7")]["id"]=="h7"


def test_ejected_runner_is_rejected_by_rules_service():
    st=base_state(); st["events"]=[ejection_event()]
    svc,h=rules_service(st)
    r=svc.play({"team":"home","play_type":"run","player_number":"7","source":"statistician","start_spot":"LEFT 25","end_spot":"LEFT 30"})
    assert r.code=="PLAYER_INELIGIBLE"
    assert h["state"]["plays"]==[]


def test_ejected_passer_is_rejected_by_rules_service():
    st=base_state(); st["events"]=[ejection_event()]
    svc,_=rules_service(st)
    r=svc.play({"team":"home","play_type":"pass","passer_number":"7","receiver_number":"8","source":"statistician","start_spot":"LEFT 25","end_spot":"LEFT 35"})
    assert r.code=="PLAYER_INELIGIBLE" and r.data["role"]=="passer"


def test_ejected_player_is_rejected_by_event_scoring_path():
    st=base_state(); st["events"]=[ejection_event()]; st["next_play_number"]=2
    svc,h=event_service(st)
    r=svc.trigger({"team":"home","event":"TD","source":"statistician","roster_id":"home-roster","player_id":"h7","play_type":"rush"})
    assert r.code=="PLAYER_INELIGIBLE"
    assert h["state"]["home_score"]==0


def test_other_player_remains_eligible_after_ejection():
    st=base_state(); st["events"]=[ejection_event()]; st["next_play_number"]=2
    svc,_=event_service(st)
    r=svc.trigger({"team":"home","event":"TD","source":"statistician","roster_id":"home-roster","player_id":"h8","play_type":"rush"})
    assert r.ok


def test_undo_ejection_restores_player_eligibility():
    svc,h=event_service(base_state())
    assert svc.trigger({"team":"home","event":"EJECTION","source":"statistician","ejection_person_type":"Player","ejection_person_name":"7","ejection_reason":"Fighting"}).ok
    assert not EligibilityService.is_eligible(h["state"],"home",player_id="h7",number="7",resolve_player=resolver)
    assert svc.undo().ok
    assert EligibilityService.is_eligible(h["state"],"home",player_id="h7",number="7",resolve_player=resolver)


def test_edit_ejection_identity_moves_ineligibility_to_correct_player():
    svc,h=event_service(base_state())
    r=svc.trigger({"team":"home","event":"EJECTION","source":"statistician","ejection_person_type":"Player","ejection_person_name":"7","ejection_reason":"Fighting"})
    eid=r.data["trigger"]["id"]
    edited=svc.edit(eid,{"source":"statistician","ejection_person_name":"8","ejection_player_number":"8","ejection_player_id":"h8","ejection_player_name":"Home Eight"})
    assert edited.ok
    assert EligibilityService.is_eligible(h["state"],"home",player_id="h7",number="7",resolve_player=resolver)
    assert not EligibilityService.is_eligible(h["state"],"home",player_id="h8",number="8",resolve_player=resolver)


def test_rebuild_derives_eligibility_and_preserves_historical_records():
    st=base_state(); before=CanonicalStateFoundation.snapshot(st)
    old_play={"play_id":"P0","event_id":"E0","play_number":1,"offense":"home","play_type":"run","yards":5,"player_id":"h7","player_number":"7"}
    old_event={"id":"E0","play_id":"P0","play_number":1,"created_at":1,"event":"PLAY","before":copy.deepcopy(before),"after":copy.deepcopy(before)}
    ej=ejection_event(event_id="EJ2"); ej["play_number"]=2; ej["created_at"]=2
    rebuilt=CanonicalStateFoundation.rebuild(st,[old_event,ej],[old_play],baseline=before)
    assert len(rebuilt["plays"])==1 and rebuilt["plays"][0]["player_id"]=="h7"
    assert not EligibilityService.is_eligible(rebuilt,"home",player_id="h7",number="7")


def test_undone_ejection_is_ignored_by_derived_eligibility():
    st=base_state(); ev=ejection_event(); ev["undone"]=True; st["events"]=[ev]
    assert EligibilityService.derive(st,resolve_player=resolver)["home"]["ejected"]==[]


def test_statistician_ui_filters_ejected_players_and_labels_unavailable():
    text=(Path(__file__).resolve().parents[1] / "templates" / "index.html").read_text(encoding="utf-8")
    assert "gamePlayerEligible(team,p)" in text
    assert "Ejected / unavailable" in text
    assert "automationRosterPlayers" in text and "gamePlayerEligible(team,p)" in text


