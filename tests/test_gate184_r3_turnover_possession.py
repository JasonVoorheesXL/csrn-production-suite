from __future__ import annotations
import copy
from threading import Lock
from canonical_state_service import CanonicalStateFoundation
from rules_service import RulesService
from statistics_service import StatisticsService


def base_state():
    return {"broadcast_id":"TEST","home_team":"Pine Valley","visitor_team":"Northwood","home_school_id":"pv","visitor_school_id":"nw","sport":"Football","status":"live","broadcast_phase":"live","game_data_authority":"statistician","home_score":0,"visitor_score":0,"possession":"home","down":"2nd","distance":"8","ball_spot":"LEFT 30","quarter":"2","clock_seconds":500,"clock_visible":True,"clock_running":True,"clock_started_at":100,"home_direction":"right","visitor_direction":"left","history":[],"events":[],"plays":[],"next_play_number":1}

def resolver(_state, team, number):
    n=str(number or '')
    rosters={('home','12'):'Home QB',('home','22'):'Home RB',('visitor','35'):'Jackson Bell',('visitor','44'):'Northwood LB'}
    if (team,n) in rosters:return {"number":n,"name":rosters[(team,n)],"resolved":True}
    return {"number":n,"name":"","resolved":False}

def service(state):
    holder={"state":copy.deepcopy(state)}
    def load():return copy.deepcopy(holder['state'])
    def save(v):holder['state']=copy.deepcopy(dict(v))
    def hist(v):v.setdefault('history',[]).append(copy.deepcopy({k:x for k,x in v.items() if k!='history'}))
    return RulesService(load_state=load,save_state=save,push_history=hist,source_allowed=lambda s,src:src=='statistician',locked_payload=lambda s:{},resolve_player=resolver,show_player_graphic=lambda *a,**k:None,transaction_lock=Lock(),now=lambda:1000.0),holder

def test_interception_return_sets_final_spot_and_new_possession():
    svc,h=service(base_state())
    r=svc.play({"team":"home","play_type":"pass","passer_number":"12","pass_outcome":"interception","returner_number":"35","start_spot":"LEFT 30","turnover_spot":"LEFT 45","return_end_spot":"LEFT 38"})
    assert r.ok
    p=r.data['play']; st=h['state']
    assert p['turnover_type']=='interception' and p['turnover_team']=='visitor'
    assert p['turnover_spot']=='LEFT 45' and p['return_end_spot']=='LEFT 38'
    assert p['return_yards']==7 and p['turnover_player_number']=='35'
    assert st['possession']=='visitor' and st['ball_spot']=='LEFT 38'
    assert st['down']=='1st' and st['distance']=='10' and not st['clock_running']

def test_interception_has_zero_offensive_yards():
    svc,_=service(base_state())
    p=svc.play({"team":"home","play_type":"pass","passer_number":"12","pass_outcome":"interception","returner_number":"35","start_spot":"LEFT 30","turnover_spot":"LEFT 45","return_end_spot":"LEFT 38"}).data['play']
    assert p['yards']==0

def test_interception_return_td_scores_defense():
    svc,h=service(base_state())
    r=svc.play({"team":"home","play_type":"pass","passer_number":"12","pass_outcome":"interception","returner_number":"35","start_spot":"LEFT 30","turnover_spot":"LEFT 45","return_end_spot":"LEFT GOAL"})
    assert r.ok and h['state']['visitor_score']==6 and h['state']['home_score']==0
    assert r.data['play']['touchdown'] is True and h['state']['possession']=='visitor'

def test_fumble_lost_preserves_rushing_yards_to_recovery_spot_not_return_end():
    svc,h=service(base_state())
    r=svc.play({"team":"home","play_type":"run","player_number":"22","fumble":True,"fumble_lost":True,"returner_number":"44","start_spot":"LEFT 30","turnover_spot":"LEFT 36","return_end_spot":"LEFT 32"})
    p=r.data['play']; assert p['yards']==6 and p['return_yards']==4
    assert p['turnover_type']=='fumble_recovery' and h['state']['ball_spot']=='LEFT 32' and h['state']['possession']=='visitor'

def test_fourth_down_failure_has_explicit_turnover_metadata():
    st=base_state(); st['down']='4th'; st['distance']='5'
    svc,h=service(st)
    p=svc.play({"team":"home","play_type":"run","player_number":"22","start_spot":"LEFT 30","end_spot":"LEFT 33"}).data['play']
    assert p['turnover'] and p['turnover_type']=='downs' and p['turnover_team']=='visitor'
    assert p['turnover_spot']=='LEFT 33' and p['return_yards']==0
    assert h['state']['possession']=='visitor' and h['state']['ball_spot']=='LEFT 33'

def test_rebuild_interception_return_is_deterministic():
    st=base_state(); before=CanonicalStateFoundation.snapshot(st)
    p={"play_id":"P1","event_id":"E1","play_number":1,"offense":"home","play_type":"pass","yards":0,"pass_outcome":"interception","turnover":True,"turnover_type":"interception","turnover_team":"visitor","turnover_spot":"LEFT 45","return_end_spot":"LEFT 38","return_yards":7,"turnover_player_number":"35"}
    e={"id":"E1","play_id":"P1","play_number":1,"event":"PLAY","before":copy.deepcopy(before),"after":{},"created_at":1}
    a=CanonicalStateFoundation.rebuild(st,[e],[p],baseline=before)
    b=CanonicalStateFoundation.rebuild(a,a['events'],a['plays'],baseline=before)
    assert a['possession']==b['possession']=='visitor' and a['ball_spot']==b['ball_spot']=='LEFT 38'
    assert b['plays'][0]['return_yards']==7

def test_rebuild_turnover_td_scores_gaining_team_only():
    st=base_state(); before=CanonicalStateFoundation.snapshot(st)
    p={"play_id":"P1","event_id":"E1","play_number":1,"offense":"home","play_type":"pass","yards":0,"pass_outcome":"interception","turnover":True,"touchdown":True,"turnover_type":"interception","turnover_team":"visitor","turnover_spot":"LEFT 45","return_end_spot":"LEFT GOAL"}
    e={"id":"E1","play_id":"P1","play_number":1,"event":"PLAY","before":copy.deepcopy(before),"after":{},"created_at":1}
    a=CanonicalStateFoundation.rebuild(st,[e],[p],baseline=before)
    assert a['visitor_score']==6 and a['home_score']==0 and a['possession']=='visitor'

def test_statistics_attribute_interception_and_return_yards_to_defender():
    st=base_state(); st['events']=[]; st['plays']=[{"play_id":"P1","event_id":"E1","play_number":1,"broadcast_id":"TEST","offense":"home","defense":"visitor","play_type":"pass","pass_outcome":"interception","yards":0,"turnover":True,"turnover_type":"interception","turnover_team":"visitor","turnover_player_number":"35","turnover_player_name":"Jackson Bell","return_yards":7,"passer_number":"12","passer_name":"Home QB"}]
    rep=StatisticsService(now=lambda:1).report(st).data['statistics']
    bell=next(p for p in rep['players'] if p['number']=='35')
    qb=next(p for p in rep['players'] if p['number']=='12')
    assert bell['defensive_interceptions']==1 and bell['turnover_return_yards']==7
    assert qb['interceptions_thrown']==1 and rep['teams']['visitor']['turnovers_gained']==1

def test_statistics_attribute_fumble_recovery():
    st=base_state(); st['events']=[]; st['plays']=[{"play_id":"P1","event_id":"E1","play_number":1,"broadcast_id":"TEST","offense":"home","defense":"visitor","play_type":"run","yards":6,"turnover":True,"fumble":True,"fumble_lost":True,"turnover_type":"fumble_recovery","turnover_team":"visitor","turnover_player_number":"44","turnover_player_name":"Northwood LB","return_yards":4,"player_number":"22","player_name":"Home RB"}]
    rep=StatisticsService().report(st).data['statistics']
    lb=next(p for p in rep['players'] if p['number']=='44')
    rb=next(p for p in rep['players'] if p['number']=='22')
    assert lb['fumble_recoveries']==1 and lb['turnover_return_yards']==4 and rb['fumbles_lost']==1

def test_muff_recovery_stat_hook_exists_without_expanding_ui_contract():
    st=base_state(); st['events']=[]; st['plays']=[{"play_id":"P1","event_id":"E1","play_number":1,"broadcast_id":"TEST","offense":"home","defense":"visitor","play_type":"other","turnover":True,"turnover_type":"muff_recovery","turnover_team":"visitor","turnover_player_number":"35","turnover_player_name":"Jackson Bell","return_yards":0}]
    rep=StatisticsService().report(st).data['statistics']
    bell=next(p for p in rep['players'] if p['number']=='35')
    assert bell['muff_recoveries']==1


