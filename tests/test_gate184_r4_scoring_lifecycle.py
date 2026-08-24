from __future__ import annotations
import copy
from threading import Lock
from canonical_state_service import CanonicalStateFoundation
from event_service import EventService
from rules_service import RulesService
from statistics_service import StatisticsService


def base_state():
    return {
        "broadcast_id":"TEST","home_team":"Pine Valley","visitor_team":"Northwood",
        "home_school_id":"pv","visitor_school_id":"nw","sport":"Football","status":"live",
        "broadcast_phase":"live","game_data_authority":"statistician","home_score":0,"visitor_score":0,
        "possession":"home","down":"2nd","distance":"8","ball_spot":"LEFT 30","quarter":"2",
        "clock_seconds":500,"clock_visible":True,"clock_running":True,"clock_started_at":100,
        "home_direction":"right","visitor_direction":"left","special_game_phase":"","kicking_team":"",
        "receiving_team":"","history":[],"events":[],"plays":[],"next_play_number":1,
    }


def _spot(v): return RulesService.spot_to_coord(v)
def _dir(st,team): return RulesService.team_direction(st,team)


def event_service(state):
    holder={"state":copy.deepcopy(state)}
    def load(): return copy.deepcopy(holder["state"])
    def save(v): holder["state"]=copy.deepcopy(dict(v))
    def hist(v): v.setdefault("history",[]).append(copy.deepcopy({k:x for k,x in v.items() if k!="history"}))
    players={"h1":{"id":"h1","number":"7","name":"Home Kicker"},"v1":{"id":"v1","number":"8","name":"Visitor Kicker"}}
    def ap(_roster,pid): return ({"id":"r"},players.get(pid)) if pid in players else (None,None)
    svc=EventService(
        load_state=load,save_state=save,public_state=lambda s:copy.deepcopy(dict(s)),push_history=hist,
        update_linked_status=lambda *a,**k:None,automation_player=ap,manual_player=lambda m,t,*a:m,
        player_display=lambda p:str((p or {}).get("name") or ""),show_player_graphic=lambda *a,**k:None,
        apply_penalty=lambda *a,**k:{},spot_to_coord=_spot,team_direction=_dir,
        normalize_state=lambda s:copy.deepcopy(dict(s)),default_player_graphic=lambda:{},
        transaction_lock=Lock(),now=lambda:1000.0,
    )
    return svc,holder


def rules_service(state):
    holder={"state":copy.deepcopy(state)}
    def load(): return copy.deepcopy(holder["state"])
    def save(v): holder["state"]=copy.deepcopy(dict(v))
    def hist(v): v.setdefault("history",[]).append(copy.deepcopy({k:x for k,x in v.items() if k!="history"}))
    def resolver(_state,team,number): return {"number":str(number or ""),"name":"Player","resolved":bool(number)}
    svc=RulesService(load_state=load,save_state=save,push_history=hist,
        source_allowed=lambda s,src:src=="statistician",locked_payload=lambda s:{},resolve_player=resolver,
        show_player_graphic=lambda *a,**k:None,transaction_lock=Lock(),now=lambda:1000.0)
    return svc,holder


def test_touchdown_enters_pending_try_at_opponent_three():
    svc,h=event_service(base_state())
    r=svc.trigger({"team":"home","event":"TD","source":"statistician","player_id":"h1","play_type":"rush"})
    assert r.ok and h["state"]["home_score"]==6
    assert h["state"]["special_game_phase"]=="pending_try"
    assert h["state"]["possession"]=="home" and h["state"]["ball_spot"]=="RIGHT 3"
    assert h["state"]["down"]=="Off" and h["state"]["distance"]=="Off"


def test_xp_good_transitions_to_kickoff_at_own_40():
    st=base_state(); CanonicalStateFoundation.enter_pending_try(st,"home"); st["home_score"]=6
    svc,h=event_service(st)
    r=svc.trigger({"team":"home","event":"XP","source":"statistician","player_id":"h1","conversion_outcome":"good"})
    assert r.ok and h["state"]["home_score"]==7
    assert h["state"]["special_game_phase"]=="kickoff" and h["state"]["kicking_team"]=="home"
    assert h["state"]["receiving_team"]=="visitor" and h["state"]["ball_spot"]=="LEFT 40"


def test_xp_no_good_awards_no_point_and_still_sets_kickoff():
    st=base_state(); CanonicalStateFoundation.enter_pending_try(st,"home"); st["home_score"]=6
    svc,h=event_service(st)
    r=svc.trigger({"team":"home","event":"XP","source":"statistician","conversion_outcome":"no_good"})
    assert r.ok and h["state"]["home_score"]==6 and h["state"]["special_game_phase"]=="kickoff"
    assert r.data["trigger"]["score_delta"]==0


def test_try_retry_remains_pending_try():
    st=base_state(); CanonicalStateFoundation.enter_pending_try(st,"home"); st["home_score"]=6
    svc,h=event_service(st)
    r=svc.trigger({"team":"home","event":"XP","source":"statistician","conversion_outcome":"retry"})
    assert r.ok and h["state"]["home_score"]==6 and h["state"]["special_game_phase"]=="pending_try"


def test_failed_two_point_transitions_to_kickoff_without_score():
    st=base_state(); CanonicalStateFoundation.enter_pending_try(st,"home"); st["home_score"]=6
    svc,h=event_service(st)
    r=svc.trigger({"team":"home","event":"2PT","source":"statistician","conversion_outcome":"failed"})
    assert r.ok and h["state"]["home_score"]==6 and h["state"]["special_game_phase"]=="kickoff"


def test_made_field_goal_scores_and_sets_kickoff():
    svc,h=event_service(base_state())
    r=svc.trigger({"team":"home","event":"FG","source":"statistician","player_id":"h1","kick_outcome":"made"})
    assert r.ok and h["state"]["home_score"]==3 and h["state"]["special_game_phase"]=="kickoff"
    assert h["state"]["ball_spot"]=="LEFT 40"


def test_missed_field_goal_changes_possession_without_points_at_result_spot():
    svc,h=event_service(base_state())
    r=svc.trigger({"team":"home","event":"FG","source":"statistician","kick_outcome":"no_good","kick_result_spot":"RIGHT 25"})
    assert r.ok and h["state"]["home_score"]==0 and h["state"]["visitor_score"]==0
    assert h["state"]["possession"]=="visitor" and h["state"]["ball_spot"]=="RIGHT 25"
    assert h["state"]["special_game_phase"]=="" and h["state"]["down"]=="1st"


def test_missed_field_goal_touchback_places_receiving_team_at_own_20():
    svc,h=event_service(base_state())
    r=svc.trigger({"team":"home","event":"FG","source":"statistician","kick_outcome":"no_good","kick_touchback":True})
    assert r.ok and h["state"]["possession"]=="visitor"
    assert h["state"]["ball_spot"]=="RIGHT 20"


def test_safety_enters_free_kick_for_team_that_conceded_safety():
    st=base_state(); st["ball_spot"]="LEFT 2"; st["down"]="1st"; st["distance"]="2"
    svc,h=rules_service(st)
    r=svc.play({"team":"home","play_type":"run","player_number":"22","start_spot":"LEFT 2","end_spot":"LEFT GOAL"})
    assert r.ok and h["state"]["visitor_score"]==2
    assert h["state"]["special_game_phase"]=="free_kick" and h["state"]["kicking_team"]=="home"
    assert h["state"]["receiving_team"]=="visitor" and h["state"]["ball_spot"]=="LEFT 20"


def test_scrimmage_touchdown_and_return_touchdown_enter_pending_try():
    svc,h=rules_service(base_state())
    r=svc.play({"team":"home","play_type":"run","player_number":"22","start_spot":"RIGHT 2","end_spot":"RIGHT GOAL"})
    assert r.ok and h["state"]["home_score"]==6 and h["state"]["special_game_phase"]=="pending_try"


def test_scoring_statistics_ignore_failed_kicks_and_tries():
    st=base_state(); st["home_score"]=10
    st["events"]=[
        {"id":"1","broadcast_id":"TEST","team":"home","event":"FG","kick_outcome":"made","score_delta":3,"automation":{"player_name":"K","player_number":"7"}},
        {"id":"2","broadcast_id":"TEST","team":"home","event":"FG","kick_outcome":"no_good","score_delta":0,"automation":{"player_name":"K","player_number":"7"}},
        {"id":"3","broadcast_id":"TEST","team":"home","event":"XP","conversion_outcome":"no_good","score_delta":0,"automation":{"player_name":"K","player_number":"7"}},
        {"id":"4","broadcast_id":"TEST","team":"home","event":"XP","conversion_outcome":"good","score_delta":1,"automation":{"player_name":"K","player_number":"7"}},
        {"id":"5","broadcast_id":"TEST","team":"home","event":"2PT","conversion_outcome":"failed","score_delta":0,"automation":{"player_name":"K","player_number":"7"}},
    ]
    rep=StatisticsService().report(st).data["statistics"]
    assert rep["teams"]["home"]["field_goals"]==1 and rep["teams"]["home"]["extra_points"]==1
    assert rep["teams"]["home"]["two_point_conversions"]==0

def test_pending_try_blocks_ordinary_scrimmage_play():
    st=base_state(); CanonicalStateFoundation.enter_pending_try(st,"home")
    svc,_=rules_service(st)
    r=svc.play({"team":"home","play_type":"run","player_number":"22","start_spot":"RIGHT 3","end_spot":"RIGHT GOAL"})
    assert r.code=="SPECIAL_PHASE_REQUIRES_RESOLUTION"


def test_kickoff_phase_accepts_only_kicking_team_kickoff():
    st=base_state(); CanonicalStateFoundation.enter_kickoff(st,"home")
    svc,_=rules_service(st)
    wrong=svc.play({"team":"visitor","play_type":"kickoff","kicker_number":"8","start_spot":"LEFT 40","end_spot":"RIGHT 20"})
    assert wrong.code=="SPECIAL_PHASE_REQUIRES_KICKOFF"


def test_r41_safety_free_kick_preserves_receiving_team_as_possession():
    st=base_state(); st["ball_spot"]="LEFT 2"
    svc,h=rules_service(st)
    r=svc.play({"team":"home","play_type":"run","start_spot":"LEFT 2","end_spot":"LEFT GOAL","player_number":"22"})
    assert r.ok
    assert h["state"]["visitor_score"]==2
    assert h["state"]["possession"]=="visitor"
    assert h["state"]["special_game_phase"]=="free_kick"
    assert h["state"]["kicking_team"]=="home"
    assert h["state"]["receiving_team"]=="visitor"

def test_r41_conversion_api_outside_pending_try_is_rejected():
    st=base_state()
    svc,h=event_service(st)
    first=svc.trigger({"team":"home","event":"XP","conversion_outcome":"good","source":"statistician"})
    assert first.code=="TRY_ALREADY_RESOLVED"
    assert h["state"]["home_score"]==0
    second=svc.trigger({"team":"visitor","event":"2PT","conversion_outcome":"good","source":"statistician"})
    assert second.code=="TRY_ALREADY_RESOLVED"
    assert h["state"]["visitor_score"]==0


