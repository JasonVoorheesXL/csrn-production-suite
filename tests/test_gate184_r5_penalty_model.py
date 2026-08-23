from penalty_service import PenaltyService


def spot_to_coord(value):
    text=str(value).upper()
    if text in {'LEFT GOAL','0'}: return 0
    if text in {'RIGHT GOAL','100'}: return 100
    if text=='50': return 50
    side, yard=text.split()
    yard=int(yard)
    return yard if side=='LEFT' else 100-yard


def coord_to_spot(c):
    c=int(c)
    if c==0:return 'LEFT GOAL'
    if c==100:return 'RIGHT GOAL'
    if c==50:return '50'
    return f'LEFT {c}' if c<50 else f'RIGHT {100-c}'


def direction(state, team):
    return 1 if state.get(f'{team}_direction','right' if team=='home' else 'left')=='right' else -1


def state(**kw):
    row={'possession':'home','down':'2nd','distance':'10','ball_spot':'LEFT 30','home_direction':'right','visitor_direction':'left','special_game_phase':''}
    row.update(kw); return row


def apply(s, **kw):
    defaults=dict(selected_team='home',requested_unit='Offensive',name='Holding',yards=10,outcome='accepted',spot_to_coord=spot_to_coord,coord_to_spot=coord_to_spot,team_direction=direction)
    defaults.update(kw)
    return PenaltyService.enforce(s, **defaults)


def test_unit_inference_uses_possession_but_preserves_manual_special_override():
    s=state(possession='home')
    assert PenaltyService.infer_unit(s,'home','Defensive')=='Offensive'
    assert PenaltyService.infer_unit(s,'visitor','Offensive')=='Defensive'
    assert PenaltyService.infer_unit(s,'visitor','Special Teams')=='Special Teams'


def test_offensive_penalty_moves_physical_spot_backward_and_increases_distance():
    s=state(ball_spot='LEFT 30',down='2nd',distance='10')
    r=apply(s,name='Holding',yards=10)
    assert r['applied'] and s['ball_spot']=='LEFT 20' and s['down']=='2nd' and s['distance']=='20'


def test_defensive_roughing_preserves_verified_automatic_first_down():
    s=state(ball_spot='LEFT 30',down='3rd',distance='18')
    r=apply(s,selected_team='visitor',requested_unit='Defensive',name='Roughing the Passer',yards=15)
    assert r['automatic_first_down'] is True
    assert s['ball_spot']=='LEFT 45' and s['down']=='1st' and s['distance']=='10'


def test_intentional_grounding_has_loss_of_down_and_field_enforcement():
    s=state(ball_spot='LEFT 30',down='2nd',distance='10')
    r=apply(s,name='Intentional Grounding',yards=5)
    assert r['loss_of_down'] is True
    assert s['ball_spot']=='LEFT 25' and s['down']=='3rd' and s['distance']=='15'


def test_declined_and_picked_up_are_state_neutral():
    for outcome in ('declined','flag_picked_up'):
        s=state(); before=dict(s)
        r=apply(s,outcome=outcome)
        assert r['applied'] is False and s==before


def test_offsetting_is_state_neutral_and_marks_retry():
    s=state(); before=dict(s)
    r=apply(s,outcome='offset')
    assert s==before and r['offsetting'] and r['retry_down']


def test_half_distance_moves_half_remaining_distance_to_goal():
    s=state(ball_spot='LEFT 8',down='1st',distance='10')
    r=apply(s,name='Personal Foul',yards=15,half_distance=True)
    assert r['half_distance'] is True and r['enforced_yards']==4 and s['ball_spot']=='LEFT 4' and s['distance']=='14'


def test_custom_enforcement_spot_is_authoritative():
    s=state(ball_spot='LEFT 35',down='2nd',distance='8')
    r=apply(s,enforcement_spot='LEFT 30',name='Holding',yards=10)
    assert r['enforcement_spot']=='LEFT 30' and s['ball_spot']=='LEFT 20'


def test_penalty_does_not_clear_special_phase_and_carries_administration_flags():
    s=state(special_game_phase='pending_try')
    r=apply(s,untimed_down=True,retry_down=True)
    assert s['special_game_phase']=='pending_try'
    assert s['penalty_administration']=={'untimed_down':True,'retry_down':True}
    assert r['untimed_down'] and r['retry_down']


