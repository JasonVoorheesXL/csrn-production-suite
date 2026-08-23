from __future__ import annotations

import copy
from pathlib import Path

from eligibility_service import EligibilityService
from event_service import EventService


def make_service(initial):
    box={"state":copy.deepcopy(initial)}
    def load(): return copy.deepcopy(box["state"])
    def save(state): box["state"]=copy.deepcopy(dict(state)); return box["state"]
    service=EventService(
        load_state=load,
        save_state=save,
        public_state=lambda state: copy.deepcopy(dict(state)),
        push_history=lambda state: None,
        update_linked_status=lambda *a,**k: None,
        automation_player=lambda *a:(None,None),
        manual_player=lambda *a:None,
        player_display=lambda p:"",
        show_player_graphic=lambda *a,**k:None,
        apply_penalty=lambda state,*a,**k:{"applied":False},
        spot_to_coord=lambda v:20,
        team_direction=lambda state,team:1,
        normalize_state=lambda state:dict(state),
        default_player_graphic=lambda:{},
        resolve_player=lambda state,team,value:{"resolved":True,"player_id":str(value),"number":str(value),"name":str(value),"roster_id":team},
        now=lambda:123456,
    )
    return service,box


def baseline():
    return {
        "home_score":0,"visitor_score":0,"possession":"home","down":"1st","distance":"10",
        "ball_spot":"LEFT 20","quarter":"1","clock_seconds":600,"clock_running":False,
        "events":[],"plays":[],"correction_log":[],"redo_stack":[],"history":[],"next_play_number":1,
        "game_data_authority":"statistician","player_eligibility":{"ejected":[]},
    }


def add_event(state, *, event_id, play_number, event="FG", score=0, player_id=""):
    before={k:copy.deepcopy(state[k]) for k in ("home_score","visitor_score","possession","down","distance","ball_spot","quarter","clock_seconds","clock_running")}
    after=copy.deepcopy(before); after["home_score"] += score
    ev={"id":event_id,"team":"home","play_id":f"P{play_number}","play_number":play_number,"event":event,"label":event,"before":before,"after":after,"created_at":play_number,
        "ejection":{"person_type":"Player" if event=="EJECTION" else "","player_id":player_id,"person_name":player_id,"reason":"Fighting" if event=="EJECTION" else ""}}
    play={"event_id":event_id,"play_id":f"P{play_number}","play_number":play_number,"play_type":event.lower(),"result":event,"undone":False}
    state["events"].append(ev); state["plays"].append(play); state.update(after); state["last_event"]=copy.deepcopy(ev); state["next_play_number"]=play_number+1


def test_undo_then_restore_returns_exact_visible_state_without_duplicate_records():
    state=baseline(); add_event(state,event_id="E1",play_number=1,event="FG",score=3)
    expected={k:copy.deepcopy(state[k]) for k in ("home_score","visitor_score","possession","down","distance","ball_spot","quarter","clock_seconds","clock_running","next_play_number")}
    svc,box=make_service(state)
    assert svc.undo().ok
    assert box["state"]["home_score"]==0 and len(box["state"]["events"])==0
    result=svc.restore(); assert result.ok
    restored=box["state"]
    for key,value in expected.items(): assert restored[key]==value
    assert [e["id"] for e in restored["events"]]==["E1"]
    assert [p["play_id"] for p in restored["plays"]]==["P1"]
    assert restored["redo_stack"]==[]


def test_multiple_undo_restore_is_lifo_and_does_not_duplicate():
    state=baseline(); add_event(state,event_id="E1",play_number=1,event="FG",score=3); add_event(state,event_id="E2",play_number=2,event="FG",score=3)
    svc,box=make_service(state)
    svc.undo(); svc.undo()
    assert len(box["state"]["redo_stack"])==2 and box["state"]["next_play_number"]==1
    svc.restore(); assert [e["id"] for e in box["state"]["events"]]==["E1"]
    svc.restore(); assert [e["id"] for e in box["state"]["events"]]==["E1","E2"]
    assert len({e["id"] for e in box["state"]["events"]})==2
    assert len({p["play_id"] for p in box["state"]["plays"]})==2


def test_restore_reapplies_ejection_eligibility_from_canonical_history():
    state=baseline(); add_event(state,event_id="EJ1",play_number=1,event="EJECTION",player_id="7")
    state["player_eligibility"]=EligibilityService.derive(state)
    svc,box=make_service(state)
    svc.undo(); assert EligibilityService.is_eligible(box["state"], "home", player_id="7")
    svc.restore(); assert not EligibilityService.is_eligible(box["state"], "home", player_id="7")


def test_stale_restore_is_blocked_after_timeline_diverges():
    state=baseline(); add_event(state,event_id="E1",play_number=1,event="FG",score=3)
    svc,box=make_service(state); svc.undo()
    # Simulate a new canonical record occupying the restored play number.
    add_event(box["state"],event_id="NEW",play_number=1,event="FG",score=3)
    result=svc.restore()
    assert result.code=="RESTORE_UNAVAILABLE"
    assert [e["id"] for e in box["state"]["events"]]==["NEW"]


def test_restore_records_operator_correction():
    state=baseline(); add_event(state,event_id="E1",play_number=1,event="FG",score=3)
    svc,box=make_service(state); svc.undo(); svc.restore()
    kinds=[row.get("kind") for row in box["state"].get("correction_log",[])]
    assert kinds[-2:]==["undo","restore"]


def test_statistician_ui_exposes_restore_action_and_disables_when_unavailable():
    text=Path("index.html").read_text(encoding="utf-8") if Path("index.html").exists() else (Path(__file__).resolve().parents[1]/"templates"/"index.html").read_text(encoding="utf-8")
    assert "Restore Last Undone" in text
    assert "restoreLastUndone" in text
    assert "'/api/restore'" in text
    assert "restoreEntryAvailable" in text


