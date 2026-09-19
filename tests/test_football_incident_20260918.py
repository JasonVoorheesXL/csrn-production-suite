"""Regression coverage for incident FB-2026-5A-W04-001 (Caledonia vs. New
Albany, 2026-09-18) -- six reported bugs, one section per bug.

Section 1/2: ball_spot must follow the direction swap at quarter breaks.
"""

from __future__ import annotations

import pytest

from canonical_state_service import CanonicalStateFoundation as C
from period_service import PeriodService


def _state(**patch):
    state = {
        "broadcast_id": "B1",
        "status": "live",
        "broadcast_phase": "live",
        "quarter": "1",
        "home_score": 0,
        "visitor_score": 0,
        "home_direction": "right",
        "visitor_direction": "left",
        "possession": "home",
        "down": "2nd",
        "distance": "6",
        "ball_spot": "LEFT 34",
        "clock_seconds": 0,
        "clock_running": False,
        "clock_started_at": 0,
        "clock_visible": True,
        "special_game_phase": "",
        "kicking_team": "",
        "receiving_team": "",
        "plays": [],
        "penalty_administration": {},
    }
    state.update(patch)
    return state


# --- Bugs 1 & 2: ball spot mirrors with the direction swap -----------------


@pytest.mark.parametrize(
    "before,after",
    [
        ("LEFT 40", "RIGHT 40"),
        ("RIGHT 40", "LEFT 40"),
        ("LEFT 1", "RIGHT 1"),
        ("RIGHT 1", "LEFT 1"),
        ("LEFT GOAL", "RIGHT GOAL"),
        ("RIGHT GOAL", "LEFT GOAL"),
        ("50", "50"),
        # legacy HOME/VISITOR aliases normalise to the canonical spelling
        ("HOME 30", "RIGHT 30"),
    ],
)
def test_mirror_spot_boundaries(before: str, after: str) -> None:
    assert C.mirror_spot(before) == after


@pytest.mark.parametrize("spot", ["", None, "somewhere", "Own 20"])
def test_mirror_spot_leaves_empty_or_unrecognised_spots_alone(spot) -> None:
    assert C.mirror_spot(spot) == spot


def test_mirror_spot_is_its_own_inverse() -> None:
    for coord in range(0, 101):
        spot = C._coord_to_spot(coord)
        assert C.mirror_spot(C.mirror_spot(spot)) == spot


def test_q1_to_q2_mirrors_ball_spot() -> None:
    r = PeriodService.transition(_state(ball_spot="LEFT 40"), "end_quarter")
    assert r.ok and r.data["transition"] == "Q1_TO_Q2"
    assert r.state["ball_spot"] == "RIGHT 40"
    assert (r.state["home_direction"], r.state["visitor_direction"]) == ("left", "right")


def test_q3_to_q4_mirrors_ball_spot() -> None:
    r = PeriodService.transition(
        _state(quarter="3", home_direction="left", visitor_direction="right", ball_spot="RIGHT 12"),
        "end_quarter",
    )
    assert r.ok and r.data["transition"] == "Q3_TO_Q4"
    assert r.state["ball_spot"] == "LEFT 12"
    assert (r.state["home_direction"], r.state["visitor_direction"]) == ("right", "left")


def test_q2_to_halftime_does_not_move_the_ball() -> None:
    # No change of ends at the end of Q2 -- that happens at start_second_half.
    r = PeriodService.transition(_state(quarter="2", ball_spot="LEFT 40"), "end_quarter")
    assert r.data["transition"] == "Q2_TO_HALFTIME"
    assert r.state["ball_spot"] == "LEFT 40"
    assert (r.state["home_direction"], r.state["visitor_direction"]) == ("right", "left")


def test_halftime_to_q3_leaves_a_correct_kickoff_spot_after_the_swap() -> None:
    """start_second_half swaps directions, then enter_kickoff places the ball.
    The kickoff spot must sit on the *kicking team's own 40* in the new
    orientation, not on the side left over from the first half."""
    state = _state(
        quarter="2",
        broadcast_phase="halftime",
        period_state="halftime",
        ball_spot="LEFT 40",
        plays=[{"play_type": "kickoff", "offense": "home", "undone": False}],
    )
    r = PeriodService.transition(state, "start_second_half")
    assert r.ok and r.data["transition"] == "HALFTIME_TO_Q3_KICKOFF"
    s = r.state
    assert (s["home_direction"], s["visitor_direction"]) == ("left", "right")
    assert s["kicking_team"] == "visitor"  # home kicked off, so visitor kicks to start Q3
    # visitor now drives right (defends the LEFT end), own 40 == LEFT 40
    assert s["ball_spot"] == C._team_own_yard_spot(s, "visitor", 40) == "LEFT 40"


@pytest.mark.parametrize(
    "state_patch,action",
    [
        ({"quarter": "1"}, "end_quarter"),
        ({"quarter": "3", "home_direction": "left", "visitor_direction": "right"}, "end_quarter"),
    ],
)
@pytest.mark.parametrize("spot", ["LEFT 3", "LEFT 49", "50", "RIGHT 49", "RIGHT 3", "LEFT GOAL"])
@pytest.mark.parametrize("possession", ["home", "visitor"])
def test_swap_preserves_yards_to_goal_and_series(state_patch, action, spot, possession) -> None:
    """The point of mirroring: the offense must be exactly as far from the
    goal it is attacking after the teams change ends as it was before."""
    before = _state(ball_spot=spot, possession=possession, **state_patch)
    after = PeriodService.transition(before, action).state
    assert C.yards_to_goal(after) == C.yards_to_goal(before)
    assert (after["down"], after["distance"], after["possession"]) == (
        before["down"],
        before["distance"],
        before["possession"],
    )


def test_swap_mirrors_on_a_110_yard_canadian_field() -> None:
    canadian = _state(country="CA", region="ON", association="CJFL", ball_spot="LEFT 20")
    assert C._field_length(canadian) == 110
    after = PeriodService.transition(canadian, "end_quarter").state
    assert after["ball_spot"] == "RIGHT 20"
    assert C.yards_to_goal(after) == C.yards_to_goal(canadian)
    # midfield on a 110 field is 55
    mid = PeriodService.transition({**canadian, "ball_spot": "55"}, "end_quarter").state
    assert mid["ball_spot"] == "55"


def test_swap_with_no_ball_spot_does_not_invent_one() -> None:
    r = PeriodService.transition(_state(ball_spot=""), "end_quarter")
    assert r.ok and r.state["ball_spot"] == ""


# --- Bug 3: goal-to-go -------------------------------------------------------
#
# Boundary note: goal to go is INCLUSIVE (yards_to_goal <= distance). 1st & 10
# from the opponent's 10 is "1st & Goal" -- the line to gain *is* the goal
# line -- which is also what the operator panel's own readout has always done.


def _gtg(spot, distance="10", possession="home", down="1st", **patch):
    return _state(ball_spot=spot, distance=distance, possession=possession, down=down, **patch)


@pytest.mark.parametrize(
    "spot,distance,expected",
    [
        ("RIGHT 10", "10", True),   # exactly equal -> still goal to go
        ("RIGHT 9", "10", True),
        ("RIGHT 11", "10", False),  # one yard farther than the distance
        ("RIGHT 3", "10", True),
        ("RIGHT 3", "3", True),
        ("RIGHT 3", "2", False),    # 2nd & 2 at the 3: line to gain is short of the goal
        ("RIGHT 1", "1", True),
        ("LEFT 40", "10", False),
        ("50", "10", False),
        ("RIGHT GOAL", "10", False),  # 0 yards to go: the ball is in the end zone
    ],
)
def test_goal_to_go_boundary_home_driving_right(spot, distance, expected) -> None:
    state = _gtg(spot, distance)
    assert C.goal_to_go(state) is expected
    fs = C.field_state(state)
    assert fs["goal_to_go"] is expected
    assert fs["distance_display"] == ("Goal" if expected else distance)


def test_goal_to_go_follows_the_offense_direction_not_the_label() -> None:
    # Visitor drives LEFT: its goal is coord 0, so LEFT 5 is 5 to score...
    assert C.goal_to_go(_gtg("LEFT 5", possession="visitor")) is True
    # ...while RIGHT 5 is its own 5-yard line (95 to score).
    assert C.goal_to_go(_gtg("RIGHT 5", possession="visitor")) is False
    # And after a change of ends the same team attacks the other goal.
    swapped = _gtg("RIGHT 5", possession="home", home_direction="left", visitor_direction="right")
    assert C.goal_to_go(swapped) is False
    swapped = _gtg("LEFT 5", possession="home", home_direction="left", visitor_direction="right")
    assert C.goal_to_go(swapped) is True


def test_goal_to_go_is_false_when_there_is_no_live_down() -> None:
    assert C.goal_to_go(_gtg("RIGHT 3", down="Off", distance="Off")) is False
    assert C.goal_to_go(_gtg("RIGHT 3", special_game_phase="kickoff", down="Off", distance="Off")) is False
    assert C.goal_to_go(_gtg("RIGHT 3", special_game_phase="pending_try")) is False
    assert C.goal_to_go(_gtg("RIGHT 3", distance="")) is False
    assert C.goal_to_go(_gtg("RIGHT 3", distance="junk")) is False


def test_goal_to_go_honours_a_stored_goal_literal() -> None:
    # Older data / a hand-typed value.
    assert C.goal_to_go(_gtg("RIGHT 3", distance="Goal")) is True
    assert C.goal_to_go(_gtg("RIGHT GOAL", distance="Goal")) is False


def test_goal_to_go_on_a_110_yard_canadian_field() -> None:
    ca = dict(country="CA", region="ON", association="CJFL")
    assert C.goal_to_go(_gtg("RIGHT 10", "10", **ca)) is True
    assert C.goal_to_go(_gtg("RIGHT 11", "10", **ca)) is False


def test_goal_to_go_is_recomputed_after_a_manual_spot_or_direction_change() -> None:
    """The reason this is derived on read rather than stored: a spot
    correction or direction toggle must never leave a stale "Goal"."""
    state = _gtg("RIGHT 5")
    assert C.field_state(state)["distance_display"] == "Goal"
    state["ball_spot"] = "LEFT 30"           # operator drags the ball away
    assert C.field_state(state)["distance_display"] == "10"
    state["ball_spot"] = "RIGHT 5"
    state["home_direction"], state["visitor_direction"] = "left", "right"  # flips who attacks where
    assert C.field_state(state)["distance_display"] == "10"


def _runtime(state):
    from state_service import StateService

    service = StateService(
        load_raw=lambda: dict(state),
        replace_raw=lambda s: dict(s),
        default_state=lambda: {},
    )
    return service, service.runtime_view(state).data["state"]


def test_runtime_view_serves_goal_to_the_overlay_and_keeps_the_numeric_distance() -> None:
    state = _gtg("RIGHT 6", "10")
    _service, runtime = _runtime(state)
    assert runtime["distance"] == "Goal"
    assert runtime["distance_yards"] == "10"
    assert runtime["canonical_field_state"]["goal_to_go"] is True
    assert runtime["canonical_field_state"]["yards_to_goal"] == 6
    # the stored state is untouched
    assert state["distance"] == "10"


def test_runtime_view_leaves_a_normal_distance_alone() -> None:
    _service, runtime = _runtime(_gtg("LEFT 30", "7"))
    assert runtime["distance"] == "7"
    assert "distance_yards" not in runtime
    assert runtime["canonical_field_state"]["goal_to_go"] is False


def test_operator_public_state_keeps_the_numeric_distance() -> None:
    """commitFieldSpot() posts currentState.distance back to /api/game-correction,
    so the operator-facing state must never carry the display-only "Goal"."""
    state = _gtg("RIGHT 6", "10")
    service, _runtime_state = _runtime(state)
    public = service.public(state).data["state"]
    assert public["distance"] == "10"
    assert public["canonical_field_state"]["goal_to_go"] is True


def test_overlay_js_renders_goal_text_and_led_yards() -> None:
    from pathlib import Path

    js = (Path(__file__).resolve().parents[1] / "static" / "csrn-production-theme-runtime.js").read_text(
        encoding="utf-8"
    )
    body = js[js.index("function productionDownDistance") : js.index("function productionBallOn")]
    # text keeps the server's "Goal"; LED cells get yards-to-goal digits
    assert 'rawDistance.toLowerCase() === "goal"' in body
    assert "canonical_field_state?.yards_to_goal" in body
    assert "combined: `${downOff ? \"-\" : rawDown} & ${distanceOff ? \"-\" : rawDistance}`" in body


# --- Bug 4b: editing/undoing a past play must not reset period, clock, ends --
#
# Confirmed by execution against the pre-fix code: log plays, cross Q1->Q2,
# edit play 1 -> quarter snapped back to Q1, clock to the baseline value,
# direction to the first play's, and the ball landed on the wrong side of the
# field. Period transitions append no event, so rebuild() had nothing to replay.


def _live_game(resolve=None, apply_penalty=None, **patch):
    import copy
    import itertools
    import threading

    from event_service import EventService
    from rules_service import RulesService

    store = {
        "broadcast_id": "B1", "status": "live", "broadcast_phase": "live",
        "game_data_authority": "broadcaster", "home_team": "Home", "visitor_team": "Visitor",
        "home_score": 0, "visitor_score": 0, "possession": "home", "down": "1st", "distance": "10",
        "ball_spot": "LEFT 20", "quarter": "1", "clock_seconds": 720, "clock_running": False,
        "clock_visible": True, "clock_started_at": 0,
        "home_direction": "right", "visitor_direction": "left", "special_game_phase": "",
        "next_play_number": 1, "events": [], "plays": [], "history": [], "correction_log": [],
        "last_event": {}, "player_graphic": {"visible": False}, "team_roles": {},
    }
    store.update(patch)

    def load():
        return copy.deepcopy(store)

    def save(value):
        store.clear()
        store.update(copy.deepcopy(dict(value)))

    tick = itertools.count(1000)

    class _Lock:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    rules = RulesService(
        load_state=load, save_state=save, push_history=lambda s: None,
        source_allowed=lambda s, src: True, locked_payload=lambda s: s,
        resolve_player=resolve or (lambda s, t, n: {}), show_player_graphic=lambda *a, **k: None,
        transaction_lock=threading.Lock(), now=lambda: next(tick),
    )
    events = EventService(
        load_state=load, save_state=save, public_state=lambda v: copy.deepcopy(dict(v)),
        push_history=lambda v: None, update_linked_status=lambda *a, **k: None,
        automation_player=lambda a, b: (None, None), manual_player=lambda *a, **k: None,
        player_display=lambda p: "", show_player_graphic=lambda *a, **k: None,
        apply_penalty=apply_penalty or (lambda *a, **k: {}), spot_to_coord=RulesService.spot_to_coord,
        coord_to_spot=RulesService.coord_to_spot, team_direction=RulesService.team_direction,
        normalize_state=lambda v: copy.deepcopy(dict(v)),
        default_player_graphic=lambda: {"visible": False}, transaction_lock=_Lock(),
        now=lambda: next(tick),
    )

    class Game:
        pass

    g = Game()
    g.store, g.rules, g.events = store, rules, events

    def run(team, start, end):
        result = rules.play({"team": team, "play_type": "run", "start_spot": start, "end_spot": end})
        assert result.ok, result.code
        return result

    def period(action, **kw):
        result = PeriodService.transition(store, action, **kw)
        assert result.ok, result.code
        save(result.state)

    def edit(index, **fields):
        result = events.edit(store["events"][index]["id"], {"source": "broadcaster", **fields})
        assert result.ok, result.code

    g.run, g.period, g.edit = run, period, edit
    return g


def _game_in_q2():
    """Two Q1 plays (+5, +3 -> LEFT 28), the Q1->Q2 break (ball mirrors to
    RIGHT 28, home now drives left), then a +5 Q2 play to RIGHT 33, with the
    Q2 clock at 5:01."""
    g = _live_game()
    g.run("home", "LEFT 20", "LEFT 25")
    g.run("home", "LEFT 25", "LEFT 28")
    g.period("end_quarter")
    assert g.store["ball_spot"] == "RIGHT 28"
    g.store["clock_seconds"] = 455
    g.run("home", "RIGHT 28", "RIGHT 33")
    g.store["clock_seconds"] = 301
    return g


def test_editing_an_early_play_keeps_quarter_clock_and_direction() -> None:
    g = _game_in_q2()
    assert (g.store["quarter"], g.store["clock_seconds"], g.store["home_direction"]) == ("2", 301, "left")

    g.edit(0, yards=6)  # play 1: +5 -> +6

    s = g.store
    assert s["quarter"] == "2"
    assert s["clock_seconds"] == 301
    assert (s["home_direction"], s["visitor_direction"]) == ("left", "right")


def test_editing_an_early_play_ripples_the_ball_spot_through_the_quarter_break() -> None:
    g = _game_in_q2()
    g.edit(0, yards=6)
    # +6, +3 in Q1 -> coord 29; change of ends mirrors it to 71; the Q2 play
    # drives left for 5 -> 66 == RIGHT 34.
    assert g.store["ball_spot"] == "RIGHT 34"
    assert (g.store["down"], g.store["distance"]) == ("1st", "10")


def test_editing_a_play_does_not_stop_a_running_clock() -> None:
    g = _game_in_q2()
    g.store.update(clock_running=True, clock_started_at=1234, clock_seconds=200)
    g.edit(1, yards=4)
    s = g.store
    assert (s["clock_running"], s["clock_started_at"], s["clock_seconds"]) == (True, 1234, 200)


def test_edit_keeps_each_events_recorded_direction_and_quarter() -> None:
    """rebuild() used to overwrite every event's `before` with the replayed
    state, so after any edit every play claimed Q1 and the first play's
    direction -- destroying the only record of which way a play was going."""
    g = _game_in_q2()
    g.edit(0, yards=6)
    recorded = [(e["before"]["quarter"], e["before"]["home_direction"]) for e in g.store["events"]]
    assert recorded == [("1", "right"), ("1", "right"), ("2", "left")]
    g.edit(2, yards=4)
    recorded = [(e["before"]["quarter"], e["before"]["home_direction"]) for e in g.store["events"]]
    assert recorded == [("1", "right"), ("1", "right"), ("2", "left")]


def test_editing_a_play_in_the_current_quarter_after_a_break_uses_that_plays_direction() -> None:
    g = _game_in_q2()
    g.edit(2, yards=8)  # the Q2 play: home drives LEFT, so +8 moves 72 -> 64
    assert g.store["ball_spot"] == "RIGHT 36"
    assert g.store["quarter"] == "2"


def test_undo_after_a_quarter_break_keeps_period_clock_and_ends() -> None:
    g = _game_in_q2()
    result = g.events.undo({})
    assert result.ok
    s = g.store
    assert (s["quarter"], s["clock_seconds"], s["home_direction"]) == ("2", 301, "left")
    assert s["ball_spot"] == "RIGHT 28"
    assert (s["down"], s["distance"]) == ("3rd", "2")
    assert len(s["events"]) == 2


def test_restore_after_a_quarter_break_keeps_period_clock_and_ends() -> None:
    g = _game_in_q2()
    assert g.events.undo({}).ok
    result = g.events.restore({})
    assert result.ok
    s = g.store
    assert (s["quarter"], s["clock_seconds"], s["home_direction"]) == ("2", 301, "left")
    assert s["ball_spot"] == "RIGHT 33"
    assert len(s["events"]) == 3


def test_rebuild_is_still_a_pure_baseline_reducer_by_default() -> None:
    """preserve_live is opt-in: without it the baseline still wins, which is
    what the canonical-state and undo-to-empty tests pin."""
    baseline = _state(quarter="1", clock_seconds=720)
    live = _state(quarter="3", clock_seconds=100, home_direction="left", visitor_direction="right")
    rebuilt = C.rebuild(live, [], [], baseline=baseline)
    assert (rebuilt["quarter"], rebuilt["clock_seconds"], rebuilt["home_direction"]) == ("1", 720, "right")
    kept = C.rebuild(live, [], [], baseline=baseline, preserve_live=True)
    assert (kept["quarter"], kept["clock_seconds"], kept["home_direction"]) == ("3", 100, "left")


# --- Bug 4a: the edit modal reads the play's own direction -------------------
#
# updateEditCalculation() used the live currentState direction, so any edit made
# after a change of ends computed yards with the wrong sign (correction
# COR-1789779045467: LEFT 49 -> RIGHT 49 on a 2-yard edit). No JS runtime in the
# test environment, so this pins the source; the recorded direction it relies
# on is guaranteed by test_edit_keeps_each_events_recorded_direction_and_quarter.


def _index_html() -> str:
    from pathlib import Path

    return (Path(__file__).resolve().parents[1] / "templates" / "index.html").read_text(encoding="utf-8")


def _js_function(source: str, name: str) -> str:
    start = source.index(f"function {name}(")
    return source[start : source.index("\nfunction ", start + 1)]


def test_edit_calculation_uses_the_recorded_play_direction() -> None:
    html = _index_html()
    calc = _js_function(html, "updateEditCalculation")
    assert "playDirection(ev,team)" in calc
    assert "currentState?.[team+'_direction']" not in calc


def test_edit_drive_arrow_uses_the_recorded_play_direction() -> None:
    opener = _js_function(_index_html(), "openEditEvent")
    assert "playDirection(ev,team)" in opener
    assert "currentState?.[team+'_direction']" not in opener


def test_play_direction_prefers_the_event_snapshot_and_falls_back_to_live() -> None:
    helper = _js_function(_index_html(), "playDirection")
    assert "ev?.before?.[team+'_direction']" in helper
    # legacy events without a recorded direction still resolve (live direction)
    assert "currentState?.[team+'_direction']" in helper


# --- Bug 6: fumble recovered by a teammate -----------------------------------
#
# Caleb Lang (#7) fumbled, teammate Medcalf (#22) recovered and ran it in. Not
# a turnover -- Caledonia kept the ball -- but the play form had no way to
# credit anyone except the single ball carrier. `recoverer_number` /
# `recovery_spot` are the new optional fields; yardage from the recovery spot
# on, and any touchdown, belong to the recoverer.

ROSTERS = {("home", "7"): "Caleb Lang", ("home", "22"): "Medcalf", ("home", "11"): "Wide Out",
           ("home", "12"): "Passer", ("visitor", "22"): "Visitor Twenty-Two"}


def _resolver(state, team, number):
    name = ROSTERS.get((team, str(number)))
    if not name:
        return {"resolved": False, "number": str(number)}
    return {"resolved": True, "number": str(number), "name": name, "player_id": f"{team}-{number}"}


def _lang_medcalf(**extra):
    """Home ball at LEFT 30. Lang (#7) runs to LEFT 40 and fumbles; Medcalf (#22)
    recovers there and returns it to the right goal line for a touchdown."""
    g = _live_game(resolve=_resolver, ball_spot="LEFT 30")
    payload = {
        "team": "home", "play_type": "run", "start_spot": "LEFT 30", "end_spot": "RIGHT GOAL",
        "player_number": "7", "fumble": True, "fumble_lost": False,
        "recoverer_number": "22", "recovery_spot": "LEFT 40",
    }
    payload.update(extra)
    result = g.rules.play(payload)
    assert result.ok, result.code
    return g, result.data["play"]


def test_own_recovery_touchdown_is_credited_to_the_recoverer_without_a_turnover() -> None:
    g, play = _lang_medcalf()
    s = g.store
    assert play["turnover"] is False and play["turnover_type"] == ""
    assert s["possession"] == "home" and s["home_score"] == 6
    assert s["special_game_phase"] == "pending_try"
    assert (play["recoverer_number"], play["recoverer_name"]) == ("22", "Medcalf")
    assert play["recovery_spot"] == "LEFT 40"
    assert play["yards"] == 70 and play["recovery_yards"] == 60
    # the ball carrier field is untouched -- it is still Lang's play
    assert (play["player_number"], play["player_name"]) == ("7", "Caleb Lang")
    assert "fumble recovered by #22 Medcalf at LEFT 40" in play["result"]
    assert play["result"].endswith("touchdown")


def test_own_recovery_touchdown_scorer_on_the_event_is_the_recoverer() -> None:
    g, _play = _lang_medcalf()
    automation = g.store["events"][-1]["automation"]
    assert (automation["player_number"], automation["player_name"]) == ("22", "Medcalf")
    assert (automation["recoverer_number"], automation["recovery_yards"]) == ("22", 60)
    assert automation["touchdown"] is True


def _report(game):
    from statistics_service import StatisticsService

    state = dict(game.store)
    return StatisticsService().report(state).data["statistics"]


def _player(report, number):
    return next(p for p in report["players"] if p["number"] == number)


def test_statistics_split_the_yardage_and_credit_the_touchdown_to_the_recoverer() -> None:
    g, _play = _lang_medcalf()
    report = _report(g)
    lang, medcalf = _player(report, "7"), _player(report, "22")

    assert (lang["rushing_attempts"], lang["rushing_yards"]) == (1, 10)
    assert lang["fumbles"] == 1 and lang["fumbles_lost"] == 0
    assert lang["touchdowns"] == 0 and lang["rushing_touchdowns"] == 0

    assert (medcalf["rushing_attempts"], medcalf["rushing_yards"]) == (0, 60)
    assert medcalf["rushing_touchdowns"] == 1 and medcalf["touchdowns"] == 1
    assert medcalf["points"] == 6
    assert medcalf["own_fumble_recoveries"] == 1

    home = report["teams"]["home"]
    assert home["rushing_yards"] == 70 and home["rushing_attempts"] == 1
    assert home["touchdowns"] == 1  # counted once, not once per player
    assert home["turnovers_gained"] == 0 and report["teams"]["visitor"]["turnovers_gained"] == 0
    assert report["reconciliation"]["all_reconciled"] is True


def test_recovery_without_a_spot_credits_the_touchdown_but_no_yardage() -> None:
    g, play = _lang_medcalf(recovery_spot="")
    assert play["recovery_yards"] == 0 and play["recovery_spot"] == "RIGHT GOAL"
    report = _report(g)
    lang, medcalf = _player(report, "7"), _player(report, "22")
    assert lang["rushing_yards"] == 70 and medcalf["rushing_yards"] == 0
    assert medcalf["touchdowns"] == 1 and lang["touchdowns"] == 0


def test_a_recovery_that_gains_nothing_after_a_real_fumble_keeps_totals_reconciled() -> None:
    g = _live_game(resolve=_resolver, ball_spot="LEFT 30")
    result = g.rules.play({
        "team": "home", "play_type": "run", "start_spot": "LEFT 30", "end_spot": "LEFT 38",
        "player_number": "7", "fumble": True, "recoverer_number": "22", "recovery_spot": "LEFT 36",
    })
    assert result.ok
    report = _report(g)
    assert (_player(report, "7")["rushing_yards"], _player(report, "22")["rushing_yards"]) == (6, 2)
    assert report["teams"]["home"]["rushing_yards"] == 8
    assert report["reconciliation"]["rushing_reconciled"] is True
    assert (g.store["down"], g.store["distance"], g.store["ball_spot"]) == ("2nd", "2", "LEFT 38")


def test_a_plain_fumble_with_no_recoverer_still_credits_the_carrier() -> None:
    g = _live_game(resolve=_resolver, ball_spot="LEFT 30")
    result = g.rules.play({
        "team": "home", "play_type": "run", "start_spot": "LEFT 30", "end_spot": "RIGHT GOAL",
        "player_number": "7", "fumble": True,
    })
    play = result.data["play"]
    assert play["recoverer_number"] == "" and play["recovery_yards"] == 0
    report = _report(g)
    assert _player(report, "7")["rushing_touchdowns"] == 1
    assert "recovered by #" not in play["result"]


def test_recoverer_equal_to_the_carrier_is_ignored() -> None:
    g, play = _lang_medcalf(recoverer_number="7")
    assert play["recoverer_number"] == "" and play["recovery_yards"] == 0
    assert _player(_report(g), "7")["rushing_touchdowns"] == 1


def test_a_lost_fumble_ignores_the_recoverer_field() -> None:
    g = _live_game(resolve=_resolver, ball_spot="LEFT 30")
    result = g.rules.play({
        "team": "home", "play_type": "run", "start_spot": "LEFT 30", "end_spot": "LEFT 34",
        "player_number": "7", "fumble": True, "fumble_lost": True,
        "recoverer_number": "22", "turnover_spot": "LEFT 34", "returner_number": "22",
    })
    assert result.ok
    play = result.data["play"]
    assert play["turnover"] is True and play["turnover_team"] == "visitor"
    assert play["recoverer_number"] == "" and play["recovery_yards"] == 0
    assert g.store["possession"] == "visitor"


def test_recoverer_must_be_on_the_offense() -> None:
    """#22 exists on both rosters here; a number that only resolves on the
    defence (visitor #22 under a home play, with no home #22) is rejected the
    same way the other offensive roles are."""
    only_visitor = {("home", "7"): "Caleb Lang", ("visitor", "22"): "Visitor Twenty-Two"}

    def resolver(state, team, number):
        name = only_visitor.get((team, str(number)))
        return {"resolved": bool(name), "number": str(number), "name": name or "", "player_id": ""}

    g = _live_game(resolve=resolver, ball_spot="LEFT 30")
    result = g.rules.play({
        "team": "home", "play_type": "run", "start_spot": "LEFT 30", "end_spot": "LEFT 40",
        "player_number": "7", "fumble": True, "recoverer_number": "22", "recovery_spot": "LEFT 35",
    })
    assert result.code == "PLAYER_TEAM_MISMATCH"
    assert result.data["role"] == "recoverer"
    assert g.store["events"] == []  # nothing recorded


def test_pass_fumble_recovered_by_a_teammate_splits_receiving_yards_and_the_td() -> None:
    g = _live_game(resolve=_resolver, ball_spot="LEFT 30")
    result = g.rules.play({
        "team": "home", "play_type": "pass", "pass_outcome": "complete",
        "start_spot": "LEFT 30", "end_spot": "RIGHT GOAL",
        "passer_number": "12", "receiver_number": "11", "fumble": True,
        "recoverer_number": "22", "recovery_spot": "50",
    })
    assert result.ok, result.code
    play = result.data["play"]
    assert (play["yards"], play["recovery_yards"]) == (70, 50)
    report = _report(g)
    passer, receiver, medcalf = _player(report, "12"), _player(report, "11"), _player(report, "22")
    assert passer["passing_yards"] == 70 and passer["completions"] == 1
    assert passer["passing_touchdowns"] == 0  # not a touchdown pass
    assert (receiver["receptions"], receiver["receiving_yards"]) == (1, 20)
    assert (medcalf["receiving_yards"], medcalf["receiving_touchdowns"], medcalf["touchdowns"]) == (50, 1, 1)
    assert report["teams"]["home"]["receiving_yards"] == 70
    assert report["reconciliation"]["all_reconciled"] is True


def test_a_yardage_edit_keeps_the_recoverers_share_and_reconciles() -> None:
    g, _play = _lang_medcalf()
    g.store["special_game_phase"] = ""  # the edit path replays plays; keep the scenario simple
    report_before = _report(g)
    assert report_before["reconciliation"]["rushing_reconciled"] is True
    g.store["plays"][0]["yards"] = 72  # what edit() writes
    report = _report(g)
    assert (_player(report, "7")["rushing_yards"], _player(report, "22")["rushing_yards"]) == (12, 60)
    assert report["reconciliation"]["rushing_reconciled"] is True


def test_enriched_play_text_keeps_the_recovery_visible() -> None:
    from state_service import StateService

    g, _play = _lang_medcalf()
    service = StateService(load_raw=lambda: dict(g.store), replace_raw=lambda s: dict(s),
                           default_state=lambda: {}, resolve_player=_resolver)
    public = service.public(dict(g.store)).data["state"]
    text = public["plays"][-1]["result"]
    assert "fumble recovered by #22 Medcalf" in text and text.endswith("touchdown")


def test_play_form_exposes_the_recovered_by_field() -> None:
    html = _index_html()
    assert 'id="playRecoverer"' in html and 'id="playRecovererWrap"' in html
    submit = _js_function(html, "submitPlayEntry") if "function submitPlayEntry(" in html else html[
        html.index("async function submitPlayEntry") :
    ]
    assert "recoverer_number:ownFumbleRecovery()" in submit
    assert "recovery_spot:ownFumbleRecovery()" in submit
    helper = _js_function(html, "ownFumbleRecovery")
    # shown for Fumble checked and Fumble lost NOT checked, on run/pass only
    assert "playFumble').checked&&!document.getElementById('playFumbleLost').checked" in helper
    assert "kind!=='run'&&kind!=='pass'" in helper


# --- Item 7: second-half kickoff direction is an operator choice ------------
#
# Which end each team attacks is a fresh decision at the second-half kickoff
# (same shape as the opening coin toss, whose direction is "the direction the
# receiving team's offense will drive"), not the mechanical mirror used for the
# in-half Q1->Q2 / Q3->Q4 breaks. `second_half_drive_direction` follows the coin
# toss's `opening_drive_direction`; empty keeps the historical mirror.


def _halftime(**patch):
    return _state(
        quarter="2",
        broadcast_phase="halftime",
        period_state="halftime",
        ball_spot="LEFT 40",
        # first half: home drove right, visitor left; home kicked off, so HOME
        # receives the second-half kickoff (the opening kicker receives)
        plays=[{"play_type": "kickoff", "offense": "home", "undone": False}],
        **patch,
    )


def _second_half(direction="", **patch):
    result = PeriodService.transition(_halftime(**patch), "start_second_half", second_half_drive_direction=direction)
    assert result.ok, result.code
    return result.state


def test_default_second_half_direction_is_still_the_mirror() -> None:
    s = _second_half("")
    assert (s["home_direction"], s["visitor_direction"]) == ("left", "right")
    s = _second_half("mirror")
    assert (s["home_direction"], s["visitor_direction"]) == ("left", "right")


@pytest.mark.parametrize("direction", ["right", "left"])
def test_explicit_direction_is_the_receiving_teams_drive_direction(direction) -> None:
    s = _second_half(direction)
    assert s["receiving_team"] == "home"
    assert s["home_direction"] == direction
    assert s["visitor_direction"] == ("left" if direction == "right" else "right")


def test_operator_can_keep_the_first_half_ends() -> None:
    """Home receives and keeps driving RIGHT: nobody changes ends."""
    s = _second_half("right")
    assert (s["home_direction"], s["visitor_direction"]) == ("right", "left")
    # the kickoff still lands on the kicking team's own 40 in the (unchanged)
    # orientation: visitor drives left, so its own 40 is RIGHT 40
    assert s["kicking_team"] == "visitor"
    assert s["ball_spot"] == C._team_own_yard_spot(s, "visitor", 40) == "RIGHT 40"


def test_operator_can_change_ends_for_the_second_half() -> None:
    s = _second_half("left")
    assert (s["home_direction"], s["visitor_direction"]) == ("left", "right")
    # visitor now drives right, so its own 40 is LEFT 40
    assert s["ball_spot"] == C._team_own_yard_spot(s, "visitor", 40) == "LEFT 40"


@pytest.mark.parametrize("direction", ["", "left", "right"])
@pytest.mark.parametrize("receiver", ["home", "visitor"])
def test_kickoff_spot_is_right_for_every_direction_choice_and_receiver(direction, receiver) -> None:
    """Whatever the choice, the kickoff is on the kicking team's own 40 for the
    directions that are actually in force afterwards."""
    result = PeriodService.transition(
        _halftime(), "start_second_half",
        second_half_receiving_team=receiver, second_half_drive_direction=direction,
    )
    assert result.ok
    s = result.state
    kicker = "visitor" if receiver == "home" else "home"
    assert s["special_game_phase"] == "kickoff" and s["kicking_team"] == kicker
    assert s["ball_spot"] == C._team_own_yard_spot(s, kicker, 40)
    if direction:
        assert s[f"{receiver}_direction"] == direction
    assert {s["home_direction"], s["visitor_direction"]} == {"left", "right"}


def test_ball_spot_mirrors_exactly_when_the_ends_change() -> None:
    """_set_directions is the shared machinery: mirror iff the ends changed,
    regardless of *why* -- and never when the chosen directions match the old
    ones. (The kickoff overwrites the spot afterwards, so this pins the helper.)"""
    changed = _state(ball_spot="LEFT 40")
    PeriodService._set_directions(changed, "left", "right")
    assert changed["ball_spot"] == "RIGHT 40"

    unchanged = _state(ball_spot="LEFT 40")
    PeriodService._set_directions(unchanged, "right", "left")
    assert unchanged["ball_spot"] == "LEFT 40"

    # a swap and an explicit choice that yields the same directions agree
    swapped = _state(ball_spot="LEFT 40")
    PeriodService._swap_directions(swapped)
    explicit = _state(ball_spot="LEFT 40")
    PeriodService._set_directions(explicit, "left", "right")
    assert swapped["ball_spot"] == explicit["ball_spot"] == "RIGHT 40"


def test_invalid_direction_is_rejected_without_changing_anything() -> None:
    result = PeriodService.transition(_halftime(), "start_second_half", second_half_drive_direction="up")
    assert result.code == "SECOND_HALF_DIRECTION_INVALID"
    assert result.state["quarter"] == "2" and result.state["broadcast_phase"] == "halftime"
    assert (result.state["home_direction"], result.state["visitor_direction"]) == ("right", "left")


def test_direction_choice_does_not_affect_the_in_half_breaks() -> None:
    q1 = PeriodService.transition(_state(), "end_quarter", second_half_drive_direction="left").state
    assert (q1["home_direction"], q1["visitor_direction"]) == ("left", "right")
    q3 = PeriodService.transition(
        _state(quarter="3", home_direction="left", visitor_direction="right"), "end_quarter",
        second_half_drive_direction="left",
    ).state
    assert (q3["home_direction"], q3["visitor_direction"]) == ("right", "left")


def _ops(state):
    from contextlib import nullcontext

    from game_operations_service import GameOperationsService

    store = {"state": state}
    service = GameOperationsService(
        load_state=lambda: store["state"], save_state=lambda v: store.update(state=dict(v)),
        default_state=lambda: _halftime(), push_history=lambda s: None,
        source_allowed=lambda s, source: True, locked_payload=lambda s: {"message": "locked"},
        update_linked_status=lambda *a: None, load_config=lambda: {},
        command_scorebug_visibility=lambda visible: None, transaction_lock=nullcontext(),
    )
    return service, store


def test_set_values_start_second_half_passes_the_direction_through() -> None:
    service, store = _ops(_halftime(game_data_authority="statistician"))
    result = service.set_values({
        "source": "statistician", "period_action": "start_second_half",
        "second_half_receiving_team": "visitor", "second_half_drive_direction": "left",
    })
    assert result.ok and store["state"]["quarter"] == "3"
    assert (store["state"]["home_direction"], store["state"]["visitor_direction"]) == ("right", "left")


def test_set_values_reports_an_invalid_direction_and_stays_at_halftime() -> None:
    service, store = _ops(_halftime(game_data_authority="statistician"))
    result = service.set_values({
        "source": "statistician", "period_action": "start_second_half",
        "second_half_receiving_team": "visitor", "second_half_drive_direction": "sideways",
    })
    assert result.ok  # the route returns the state with the error attached
    assert result.data["state"]["period_action_code"] == "SECOND_HALF_DIRECTION_INVALID"
    assert store["state"]["broadcast_phase"] == "halftime"


def test_halftime_toggle_passes_the_direction_through() -> None:
    service, store = _ops(_halftime())
    # home (the receiver) keeps driving right: a choice that differs from the mirror
    result = service.toggle_halftime({"second_half_drive_direction": "right"})
    assert result.ok
    s = store["state"]
    assert s["quarter"] == "3" and s["broadcast_phase"] == "live"
    assert (s["home_direction"], s["visitor_direction"]) == ("right", "left")


def test_halftime_toggle_without_a_choice_keeps_the_mirror() -> None:
    service, store = _ops(_halftime())
    assert service.toggle_halftime({}).ok
    s = store["state"]
    assert (s["home_direction"], s["visitor_direction"]) == ("left", "right")


def test_a_non_mirrored_second_half_survives_a_later_edit_of_a_first_half_play() -> None:
    """The recorded per-play direction (bug 4b) means a Q3 played in the SAME
    direction as Q2 must not be mirrored by a rebuild."""
    g = _live_game()
    g.run("home", "LEFT 20", "LEFT 25")
    g.period("end_quarter")                                  # Q2: home drives left
    g.store["clock_seconds"] = 500
    g.run("home", "RIGHT 25", "RIGHT 30")                    # 75 -> 70
    g.period("end_quarter")                                  # halftime
    g.store["plays"] = [{"play_type": "kickoff", "offense": "home", "undone": False}] + g.store["plays"]
    g.period("start_second_half", second_half_receiving_team="home", second_half_drive_direction="left")
    assert (g.store["home_direction"], g.store["quarter"]) == ("left", "3")   # ends NOT changed
    g.store.update(special_game_phase="", kicking_team="", receiving_team="", possession="home",
                   down="1st", distance="10", ball_spot="RIGHT 30", clock_seconds=610)
    g.run("home", "RIGHT 30", "RIGHT 36")                    # 70 -> 64, still driving left

    g.edit(0, yards=6)                                       # first-half play +5 -> +6

    s = g.store
    assert (s["quarter"], s["clock_seconds"], s["home_direction"]) == ("3", 610, "left")
    # Q1 +6 -> 26 (right); Q2 mirror -> 74 then -5 -> 69; Q3 unchanged ends: -6 -> 63
    assert s["ball_spot"] == "RIGHT 37"


def test_second_half_direction_controls_exist_in_both_consoles() -> None:
    html = _index_html()
    assert 'id="secondHalfDirection"' in html and 'id="broadcasterSecondHalfDirection"' in html
    toggle = html[html.index("async function toggleHalftime(") :]
    toggle = toggle[: toggle.index("\n}\n")]
    assert "second_half_drive_direction" in toggle
    assert "toggleHalftime('broadcaster')" in html and "toggleHalftime('statistician')" in html
    assert "second_half_drive_direction" in _js_function(html, "periodAction") or "second_half_drive_direction" in html[
        html.index("async function periodAction(") : html.index("async function changeProgramVisual")
    ]


# --- Item 9a: live play log shows the game clock -----------------------------
#
# The eventLog row showed only the wall-clock time the play was logged. It now
# also shows the running game clock (M:SS from clock_seconds), gated on
# clock_visible -- the operator's Show/Hide Clock switch. The gate reads the
# value recorded WITH the event: in the real incident game the first plays were
# logged with the clock hidden and frozen at 720, which must not render as 12:00.


def test_events_carry_the_game_clock_and_its_visibility_the_log_reads() -> None:
    g = _live_game(clock_visible=True, clock_seconds=512)
    g.run("home", "LEFT 20", "LEFT 25")
    after = g.store["events"][-1]["after"]
    assert after["clock_seconds"] == 512 and after["clock_visible"] is True

    g = _live_game(clock_visible=False, clock_seconds=720)
    g.run("home", "LEFT 20", "LEFT 25")
    after = g.store["events"][-1]["after"]
    assert after["clock_seconds"] == 720 and after["clock_visible"] is False


def test_recorded_clock_visibility_survives_an_edit_rebuild() -> None:
    """bug 4b's recorded-field preservation is what keeps 'clock was hidden when
    this play was logged' true after any later edit."""
    g = _live_game(clock_visible=False, clock_seconds=720)
    g.run("home", "LEFT 20", "LEFT 25")
    g.store.update(clock_visible=True, clock_seconds=400)
    g.run("home", "LEFT 25", "LEFT 29")
    g.edit(0, yards=6)
    flags = [(e["after"]["clock_visible"], e["after"]["clock_seconds"]) for e in g.store["events"]]
    assert flags == [(False, 720), (True, 400)]


def test_event_log_row_shows_the_gated_game_clock() -> None:
    html = _index_html()
    helper = _js_function(html, "eventClockText")
    # gated on clock_visible: the event's recorded value, live flag only as a fallback
    assert "a.clock_visible" in helper and "currentState?.clock_visible" in helper
    assert "clock_seconds" in helper and "padStart(2,'0')" in helper
    start = html.index("const eventLog=document.getElementById('eventLog')")
    block = html[start : html.index("const confirmation=document.getElementById('eventConfirmation')", start)]
    assert "eventClockText(ev)" in block
    assert "<time>${period}" in block
    # quarter is unchanged and still first
    assert "const period=[quarter,eventClockText(ev)]" in block


# --- Item 9b: live play log shows down & distance ----------------------------
#
# Down & distance after each play. Two gates: the engine's own convention (a
# real down and a real distance; "Off"/empty is not shown) and, since item 11,
# the per-broadcast down_distance_visible setting via eventDownDistanceEnabled().


def test_events_and_plays_carry_the_down_and_distance_the_log_reads() -> None:
    g = _live_game()
    g.run("home", "LEFT 20", "LEFT 25")  # 1st & 10, +5 -> 2nd & 5
    event = g.store["events"][-1]
    assert (event["after"]["down"], event["after"]["distance"]) == ("2nd", "5")
    # Live plays carry no resulting_* fields -- event.after is the reliable
    # source. Replayed plays (after an edit) do get them, so the row's fallback
    # to the play's resulting_down/resulting_distance still covers those.
    assert "resulting_down" not in g.store["plays"][-1]
    g.edit(0, yards=6)
    assert g.store["plays"][-1]["resulting_down"] == "2nd"
    assert g.store["plays"][-1]["resulting_distance"] == "4"


def test_kickoff_and_try_phases_record_off_which_the_log_hides() -> None:
    state = _state()
    C.enter_kickoff(state, "home")
    assert (state["down"], state["distance"]) == ("Off", "Off")


def test_event_log_row_shows_down_and_distance_after_the_play() -> None:
    html = _index_html()
    helper = _js_function(html, "eventDownDistanceText")
    assert "a.down??play.resulting_down" in helper and "a.distance??play.resulting_distance" in helper
    # a real down and a real distance only: "Off"/empty is hidden
    assert "toLowerCase()==='off'" in helper
    assert "eventDownDistanceEnabled()" in helper
    # (item 11: this was a `return true` stub until the real setting existed)
    assert "function eventDownDistanceEnabled(){return currentState?.down_distance_visible!==false}" in html
    start = html.index("const eventLog=document.getElementById('eventLog')")
    block = html[start : html.index("const confirmation=document.getElementById('eventConfirmation')", start)]
    assert "eventDownDistanceText(ev)" in block and 'class="event-situation"' in block
    # the clock (9a) and quarter are untouched
    assert "const period=[quarter,eventClockText(ev)]" in block


# --- Item 10: goal-to-go survives a penalty ---------------------------------
#
# Non-obvious, so pinned. Down/distance and goal-to-go are tracked
# independently: at "2nd & Goal from the 8" the stored distance is 10 (it is
# only *displayed* as Goal). A 10-yard holding penalty on the offense sets
# distance = old_distance + enforced yards = 20 at the new spot (18 yards from
# the goal), and because 18 <= 20 goal_to_go() still reads "2nd & Goal from the
# 18". That only works while penalty_service adds the SAME enforced yardage to
# distance that it moves the ball -- a future change to either file that breaks
# the lockstep flips this, so the numbers are asserted explicitly.


def _enforce(state, **kw):
    """The same wiring as app.apply_penalty_enforcement, on the real PenaltyService."""
    from penalty_service import PenaltyService
    from rules_service import RulesService

    defaults = dict(
        selected_team="home", requested_unit="Offensive", name="Holding", yards=10, outcome="accepted",
        spot_to_coord=lambda v: RulesService.spot_to_coord(v, state),
        coord_to_spot=lambda c: RulesService.coord_to_spot(c, state),
        team_direction=RulesService.team_direction,
    )
    defaults.update(kw)
    return PenaltyService.enforce(state, **defaults)


def _goal_line_state(spot="RIGHT 8", distance="10", down="2nd", **patch):
    return _state(ball_spot=spot, distance=distance, down=down, special_game_phase="", **patch)


def test_holding_at_2nd_and_goal_from_the_8_is_still_goal_to_go_from_the_18() -> None:
    state = _goal_line_state("RIGHT 8", "10", "2nd")
    assert (C.yards_to_goal(state), C.goal_to_go(state)) == (8, True)

    result = _enforce(state, name="Holding", yards=10)

    assert result["applied"] is True and result["enforced_yards"] == 10
    assert state["ball_spot"] == "RIGHT 18"
    assert (state["down"], state["distance"]) == ("2nd", "20")   # 10 stored + 10 enforced
    assert C.yards_to_goal(state) == 18
    assert C.goal_to_go(state) is True                             # 18 <= 20
    fs = C.field_state(state)
    assert fs["goal_to_go"] is True and fs["distance_display"] == "Goal"


def test_goal_to_go_after_a_penalty_reaches_the_overlay_as_goal() -> None:
    state = _goal_line_state("RIGHT 8", "10", "2nd", broadcast_id="B1")
    _enforce(state, name="Holding", yards=10)
    _service, runtime = _runtime(state)
    assert runtime["distance"] == "Goal"
    assert runtime["distance_yards"] == "20"
    assert runtime["canonical_field_state"]["yards_to_goal"] == 18


def test_full_trigger_path_penalty_keeps_goal_to_go() -> None:
    """EventService.trigger -> (app's apply_penalty_enforcement wiring) ->
    PenaltyService -> goal_to_go(), end to end, through the real event."""
    holder = {}

    def apply_penalty(state, category, name, yards, outcome):
        options = dict(state.get("_pending_penalty_options") or {})
        return _enforce(
            state, selected_team=options.get("selected_team") or state["possession"],
            requested_unit=options.get("requested_unit") or category,
            name=name, yards=yards, outcome=outcome,
        )

    g = _live_game(apply_penalty=apply_penalty, ball_spot="RIGHT 8", down="2nd", distance="10")
    holder["g"] = g
    result = g.events.trigger({
        "team": "home", "event": "PENALTY", "source": "broadcaster",
        "penalty_category": "Offensive", "penalty_name": "Holding",
        "penalty_yards": 10, "penalty_outcome": "accepted",
    })
    assert result.ok, result.code
    s = g.store
    assert (s["ball_spot"], s["down"], s["distance"]) == ("RIGHT 18", "2nd", "20")
    assert C.goal_to_go(s) is True
    assert s["events"][-1]["after"]["distance"] == "20"


@pytest.mark.parametrize("yards", [5, 10, 15])
@pytest.mark.parametrize("distance", ["10", "8", "3"])
def test_offensive_penalty_moves_ball_and_distance_in_lockstep(yards, distance) -> None:
    """The invariant behind the case above: both grow by exactly the enforced
    yardage, so a goal-to-go situation stays goal-to-go and a non-goal-to-go
    one stays that way."""
    state = _goal_line_state("RIGHT 8", distance, "2nd")
    was = C.goal_to_go(state)
    to_goal_before, distance_before = C.yards_to_goal(state), int(state["distance"])

    result = _enforce(state, name="Holding", yards=yards)

    assert result["applied"] is True
    assert C.yards_to_goal(state) - to_goal_before == int(state["distance"]) - distance_before == yards
    assert C.goal_to_go(state) is was


def test_a_penalty_that_pushes_the_offense_out_of_goal_to_go_range_is_not_goal_to_go() -> None:
    # 2nd & 3 from the 25 is not goal to go; a 10-yard holding makes it 2nd & 13
    # from the 35 -- still not.
    state = _goal_line_state("RIGHT 25", "3", "2nd")
    assert C.goal_to_go(state) is False
    _enforce(state, name="Holding", yards=10)
    assert (state["ball_spot"], state["distance"]) == ("RIGHT 35", "13")
    assert C.goal_to_go(state) is False and C.field_state(state)["distance_display"] == "13"


@pytest.mark.parametrize(
    "possession,spot,extra",
    [
        ("home", "RIGHT 8", {}),                                                   # home drives right
        ("visitor", "LEFT 8", {}),                                                  # visitor drives left
        ("home", "LEFT 8", {"home_direction": "left", "visitor_direction": "right"}),  # after a change of ends
    ],
)
def test_penalty_goal_to_go_holds_in_every_orientation(possession, spot, extra) -> None:
    state = _goal_line_state(spot, "10", "2nd", possession=possession, **extra)
    _enforce(state, selected_team=possession, name="Holding", yards=10)
    assert state["distance"] == "20"
    assert C.yards_to_goal(state) == 18 and C.goal_to_go(state) is True


# --- Item 11: down & distance in the play log is a real per-broadcast toggle -
#
# `down_distance_visible`, modelled on clock_visible / ball_spot_visible:
# an app.py default, a GameOperationsService settable field, and Hide/Show
# buttons beside the Clock Display ones. ON by default -- nothing changes for
# anyone who never touches the control. Read LIVE by the log (see the comment
# on eventDownDistanceEnabled() for why that differs from the clock).


def test_down_distance_visible_defaults_to_on_for_a_new_broadcast() -> None:
    import app

    assert app.DEFAULT_STATE["down_distance_visible"] is True


def test_states_saved_before_the_setting_existed_load_with_it_on(tmp_path) -> None:
    """The point of default-on: an existing broadcast's saved state has no such
    key and must come back as ON -- not off, not missing."""
    import json

    import app
    from core_repositories import StateRepository
    from persistence_engine import JsonPersistenceEngine

    legacy = {k: v for k, v in app.DEFAULT_STATE.items() if k != "down_distance_visible"}
    legacy.update(broadcast_id="OLD-GAME", home_score=7)
    path = tmp_path / "state.json"
    path.write_text(json.dumps(legacy), encoding="utf-8")
    engine = JsonPersistenceEngine(tmp_path / "bk", tmp_path / "q")

    loaded = StateRepository(engine, path, app.DEFAULT_STATE).load()

    assert loaded["broadcast_id"] == "OLD-GAME" and loaded["home_score"] == 7
    assert loaded["down_distance_visible"] is True


def test_a_saved_off_setting_survives_a_reload(tmp_path) -> None:
    import json

    import app
    from core_repositories import StateRepository
    from persistence_engine import JsonPersistenceEngine

    saved = {**app.DEFAULT_STATE, "broadcast_id": "G", "down_distance_visible": False}
    path = tmp_path / "state.json"
    path.write_text(json.dumps(saved), encoding="utf-8")
    loaded = StateRepository(JsonPersistenceEngine(tmp_path / "bk", tmp_path / "q"), path, app.DEFAULT_STATE).load()
    assert loaded["down_distance_visible"] is False


def test_state_service_normalize_keeps_an_off_setting_and_defaults_a_missing_one_to_on() -> None:
    import app
    from state_service import StateService

    service = StateService(load_raw=lambda: {}, replace_raw=lambda s: dict(s), default_state=lambda: dict(app.DEFAULT_STATE))
    assert service.normalize({"broadcast_id": "G"})["down_distance_visible"] is True
    assert service.normalize({"broadcast_id": "G", "down_distance_visible": False})["down_distance_visible"] is False
    assert service.normalize({"broadcast_id": "G", "down_distance_visible": True})["down_distance_visible"] is True


def test_down_distance_visible_is_settable_and_display_only() -> None:
    """Settable through GameOperationsService like clock_visible, and -- being a
    display flag, not game data -- not subject to the statistician authority lock
    and never touching the game itself."""
    from game_operations_service import GameOperationsService

    assert "down_distance_visible" in GameOperationsService.ALLOWED_SET_FIELDS
    assert "down_distance_visible" not in GameOperationsService.GAME_DATA_FIELDS

    service, store = _ops(_state(game_data_authority="statistician", down_distance_visible=True))
    before = {k: store["state"][k] for k in ("down", "distance", "ball_spot", "possession", "home_score")}

    # a broadcaster-source change is accepted even though the statistician holds game-data authority
    result = service.set_values({"source": "broadcaster", "down_distance_visible": False})
    assert result.ok and result.data["changes"] == {"down_distance_visible": False}
    assert store["state"]["down_distance_visible"] is False
    assert {k: store["state"][k] for k in before} == before

    assert service.set_values({"source": "broadcaster", "down_distance_visible": True}).ok
    assert store["state"]["down_distance_visible"] is True


def test_down_distance_toggle_control_sits_beside_the_clock_display_control() -> None:
    html = _index_html()
    assert 'id="downDistanceVisibilityButtons"' in html
    assert "setState('down_distance_visible',false)" in html and "setState('down_distance_visible',true)" in html
    # active state is highlighted the same way as the clock buttons, defaulting to ON when unset
    assert "markActive('downDistanceVisibilityButtons', String(currentState.down_distance_visible !== false))" in html
    # placed directly after the Clock Display control, before Quarter
    assert html.index('id="clockVisibilityButtons"') < html.index('id="downDistanceVisibilityButtons"') < html.index("<h3>Quarter</h3>")
    # it is labelled as a play-log control, not an on-air one
    assert "Play Log: Down &amp; Distance" in html


def test_event_log_gate_reads_the_setting_live_and_defaults_to_on() -> None:
    html = _index_html()
    assert "function eventDownDistanceEnabled(){return currentState?.down_distance_visible!==false}" in html
    # the row builder still goes through the gate
    text_fn = _js_function(html, "eventDownDistanceText")
    assert "if(!eventDownDistanceEnabled())return ''" in text_fn


# --- Item 13: toggle_halftime's "receiver unknown" fallback swaps the ends ---
#
# start_second_half returns SECOND_HALF_RECEIVER_REQUIRED only when there is no
# explicit receiver AND the opening kickoff was never recorded (stats started
# mid-game, etc.). toggle_halftime() then falls back to starting Q3 directly --
# and used to skip direction entirely, leaving home_direction / visitor_direction
# / ball_spot exactly as they were at the end of Q2. It now swaps the ends the
# same way every other quarter break does (mirroring the ball with them). A
# second_half_drive_direction is defined relative to the RECEIVING team, which is
# precisely what is unknown here, so it is ignored -- and the operator is told.
# The fallback still does no kickoff setup (that needs a known kicking team).


def _unknown_receiver_halftime(**patch):
    """Halftime with no receiver: no plays (so no opening kickoff to infer it
    from), no opening_kicking_team, no second_half_receiving_team."""
    fields = dict(
        quarter="2", broadcast_phase="halftime", period_state="halftime",
        ball_spot="LEFT 40", possession="home", down="2nd", distance="6",
    )
    fields.update(patch)
    return _state(**fields)


def test_the_precondition_receiver_really_is_unknown() -> None:
    state = _unknown_receiver_halftime()
    result = PeriodService.transition(state, "start_second_half")
    assert result.code == "SECOND_HALF_RECEIVER_REQUIRED"
    assert PeriodService._opening_kicking_team(state) == ""


def test_fallback_swaps_the_ends_and_mirrors_the_ball_like_the_other_quarter_breaks() -> None:
    service, store = _ops(_unknown_receiver_halftime())

    result = service.toggle_halftime({})

    assert result.ok
    s = store["state"]
    # the fallback still fired: Q3, live, with the fallback's own resets
    assert (s["quarter"], s["broadcast_phase"], s["period_state"]) == ("3", "live", "quarter")
    assert (s["down"], s["distance"], s["clock_seconds"], s["clock_running"]) == ("1st", "10", 720, False)
    assert s["scorebug_visible"] is True
    # ...and now the ends changed, with the ball mirrored -- exactly like Q1->Q2 / Q3->Q4
    assert (s["home_direction"], s["visitor_direction"]) == ("left", "right")
    assert s["ball_spot"] == "RIGHT 40"


def test_fallback_matches_what_an_in_half_quarter_break_does() -> None:
    """Same result as the mechanical swap used at Q1->Q2 and Q3->Q4."""
    for spot in ("LEFT 40", "RIGHT 12", "LEFT GOAL", "50", "RIGHT 3"):
        service, store = _ops(_unknown_receiver_halftime(ball_spot=spot))
        reference = _unknown_receiver_halftime(ball_spot=spot)
        PeriodService._swap_directions(reference)

        assert service.toggle_halftime({}).ok
        s = store["state"]
        assert (s["home_direction"], s["visitor_direction"], s["ball_spot"]) == (
            reference["home_direction"], reference["visitor_direction"], reference["ball_spot"],
        ), spot


def test_fallback_preserves_yards_to_goal_and_possession() -> None:
    for possession in ("home", "visitor"):
        before = _unknown_receiver_halftime(ball_spot="RIGHT 20", possession=possession)
        service, store = _ops(before)
        assert service.toggle_halftime({}).ok
        after = store["state"]
        assert C.yards_to_goal(after) == C.yards_to_goal(before), possession
        assert after["possession"] == possession


def test_fallback_still_does_no_kickoff_setup() -> None:
    """Out of scope by design: a kickoff needs a known kicking team."""
    service, store = _ops(_unknown_receiver_halftime())
    assert service.toggle_halftime({}).ok
    s = store["state"]
    assert s["special_game_phase"] == ""
    assert s["kicking_team"] == "" and s["receiving_team"] == ""
    assert s["possession"] == "home"


def test_an_explicit_direction_is_ignored_when_the_receiver_is_unknown_and_the_operator_is_told() -> None:
    for direction in ("right", "left"):
        service, store = _ops(_unknown_receiver_halftime())

        result = service.toggle_halftime({"second_half_drive_direction": direction})

        assert result.ok
        s = store["state"]
        # ignored: identical to the historical mirror whichever way was chosen
        assert (s["home_direction"], s["visitor_direction"], s["ball_spot"]) == ("left", "right", "RIGHT 40"), direction
        # surfaced, not silent: in the response the route returns...
        notice = result.data["state"]["period_action_notice"]
        assert direction.upper() in notice and "receiving team isn't known" in notice
        assert result.data["message"] == notice
        # ...but never persisted into the game state
        assert "period_action_notice" not in s


def test_no_notice_when_no_direction_was_chosen_or_the_mirror_was() -> None:
    for payload in ({}, {"second_half_drive_direction": ""}, {"second_half_drive_direction": "mirror"}):
        service, store = _ops(_unknown_receiver_halftime())
        result = service.toggle_halftime(payload)
        assert result.ok
        assert "period_action_notice" not in result.data["state"], payload
        assert "message" not in result.data, payload


def test_a_known_receiver_still_takes_the_item_7_path_not_the_fallback() -> None:
    """The fix is confined to the unknown-receiver branch."""
    service, store = _ops(_unknown_receiver_halftime())
    result = service.toggle_halftime({"second_half_receiving_team": "home", "second_half_drive_direction": "right"})
    assert result.ok
    s = store["state"]
    assert s["special_game_phase"] == "kickoff" and s["receiving_team"] == "home"
    assert (s["home_direction"], s["visitor_direction"]) == ("right", "left")  # the choice was honored
    assert "period_action_notice" not in result.data["state"]


def test_a_retried_command_does_not_swap_the_ends_twice() -> None:
    """A retry (same command_id) hits the idempotency ledger. It must not swap
    again. The ledger keeps the top-level `message` but, by design, strips
    `state` and rebuilds it from the current state, so the transient
    period_action_notice is not repeated in a retry's state."""
    service, store = _ops(_unknown_receiver_halftime())
    first = service.toggle_halftime({"command_id": "cmd-1", "second_half_drive_direction": "right"})
    second = service.toggle_halftime({"command_id": "cmd-1", "second_half_drive_direction": "right"})
    assert first.ok and second.ok
    assert second.data["message"] == first.data["message"]
    s = store["state"]
    assert (s["home_direction"], s["visitor_direction"], s["ball_spot"]) == ("left", "right", "RIGHT 40")
    assert s["quarter"] == "3"


def test_halftime_button_shows_the_notice() -> None:
    html = _index_html()
    toggle = html[html.index("async function toggleHalftime(") :]
    toggle = toggle[: toggle.index("\n}\n")]
    assert "const data = await GameStateManager.mutate('/api/toggle-halftime', payload)" in toggle
    assert "period_action_notice" in toggle and "showOperatorNotice(notice" in toggle
