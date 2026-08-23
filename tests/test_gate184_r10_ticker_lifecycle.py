from __future__ import annotations

from ticker_policy_service import TickerPolicyService


def ev(event_id, kind, *, team='home', quarter='1', description='', score=(0,0), yards=0, outcome=''):
    return {
        'id': event_id,
        'event': kind,
        'team': team,
        'quarter': quarter,
        'description': description or kind,
        'yards': yards,
        'outcome': outcome,
        'after': {'home_score': score[0], 'visitor_score': score[1], 'quarter': quarter},
    }


def test_routine_play_appears_once():
    items = TickerPolicyService.build({'events':[ev('r1','RUN',yards=4)]})
    assert [x['id'] for x in items] == ['r1']
    assert items[0]['lifecycle'] == 'routine'


def test_important_turnover_publishes_once_with_two_repeats():
    items = TickerPolicyService.build({'events':[ev('t1','TURNOVER',score=(7,7))]})
    assert [x['id'] for x in items] == ['t1']
    assert items[0]['repeat_count'] == 2
    assert items[0]['persistent'] is False


def test_touchdown_and_try_are_one_persistent_scoring_story():
    state={'events':[
        ev('td1','TD',team='home',description='Touchdown by #5',score=(6,0)),
        ev('xp1','XP',team='home',description='Extra point good',score=(7,0)),
    ]}
    items=TickerPolicyService.build(state)
    assert len(items)==1
    story=items[0]
    assert story['persistent'] is True
    assert story['source_ids']==['td1','xp1']
    assert story['description']=='Touchdown by #5 · Extra point good'
    assert story['after']['home_score']==7


def test_scoring_story_persists_beyond_transient_window():
    events=[ev('td1','TD',score=(6,0))]
    events += [ev(f'r{i}','RUN',yards=3) for i in range(20)]
    items=TickerPolicyService.build({'events':events})
    assert any(x.get('id')=='td1' for x in items)
    routine_ids={x['id'] for x in items if x.get('lifecycle')=='routine'}
    assert 'r0' not in routine_ids and 'r19' in routine_ids


def test_close_fourth_quarter_turnover_persists():
    events=[ev('t1','TURNOVER',quarter='4',score=(21,17))]
    events += [ev(f'r{i}','RUN',quarter='4',yards=2,score=(21,17)) for i in range(20)]
    items=TickerPolicyService.build({'events':events})
    found=[x for x in items if x.get('id')=='t1']
    assert len(found)==1
    assert found[0]['persistent'] is True
    assert found[0]['lifecycle']=='persistent_turnover'


def test_blowout_fourth_quarter_turnover_is_not_persistent_and_requests_two_repeats():
    items=TickerPolicyService.build({'events':[ev('t1','TURNOVER',quarter='4',score=(42,7))]})
    assert len(items)==1
    assert items[0]['persistent'] is False
    assert items[0]['repeat_count'] == 2


def test_undone_events_never_enter_ticker_view():
    event=ev('bad','TD',score=(6,0)); event['undone']=True
    assert TickerPolicyService.build({'events':[event]}) == []


def test_failed_try_does_not_become_independent_persistent_scoring_story():
    items=TickerPolicyService.build({'events':[ev('xp1','XP',outcome='no_good',description='Extra point no good')]})
    assert len(items)==1
    assert items[0]['persistent'] is False


def test_overlay_and_theme_adapter_contracts_prefer_backend_ticker_items():
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    overlay=(root/'templates'/'overlay.html').read_text(encoding='utf-8')
    runtime=(root/'static'/'csrn-production-theme-runtime.js').read_text(encoding='utf-8')
    assert "Array.isArray(s.ticker_items)?s.ticker_items" in overlay
    assert "Array.isArray(runtime.ticker_items) ? runtime.ticker_items" in runtime




