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


def _live_game(**patch):
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
        resolve_player=lambda s, t, n: {}, show_player_graphic=lambda *a, **k: None,
        transaction_lock=threading.Lock(), now=lambda: next(tick),
    )
    events = EventService(
        load_state=load, save_state=save, public_state=lambda v: copy.deepcopy(dict(v)),
        push_history=lambda v: None, update_linked_status=lambda *a, **k: None,
        automation_player=lambda a, b: (None, None), manual_player=lambda *a, **k: None,
        player_display=lambda p: "", show_player_graphic=lambda *a, **k: None,
        apply_penalty=lambda *a, **k: {}, spot_to_coord=RulesService.spot_to_coord,
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
