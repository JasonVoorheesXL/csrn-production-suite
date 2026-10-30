"""Edit Play = re-enter the play (owner's "option 1", 2026-10-21).

Editing a recorded run/pass/punt/kickoff re-runs it through the same rules
engine that recorded it (RulesService._resolve_play) from the state recorded
just before it, then replays every later event: spots, downs, possession,
scoring, the result text and player credit all re-derive. The old event-edit
form only rewrote yards (Down/Distance and the description kept their old
values, and jerseys could not be changed at all).
"""

from __future__ import annotations

import copy
import itertools
import threading
from pathlib import Path

from event_service import EventService
from period_service import PeriodService
from rules_service import RulesService
from statistics_service import StatisticsService

ROSTER = {
    ("home", "7"): "Caleb Lang",
    ("home", "11"): "Wide Out",
    ("home", "12"): "Quarter Back",
    ("home", "9"): "Home Punter",
    ("visitor", "4"): "Visitor Returner",
    ("visitor", "8"): "Visitor Eight",
    ("visitor", "22"): "Visitor Back",
}


def _resolver(state, team, number):
    name = ROSTER.get((team, str(number)))
    if not name:
        return {"resolved": False, "number": str(number)}
    return {"resolved": True, "number": str(number), "name": name, "player_id": f"{team}-{number}"}


class Game:
    def __init__(self, **patch):
        self.store = {
            "broadcast_id": "B1", "status": "live", "broadcast_phase": "live",
            "game_data_authority": "statistician", "home_team": "Home", "visitor_team": "Visitor",
            "home_score": 0, "visitor_score": 0, "possession": "home", "down": "1st", "distance": "10",
            "ball_spot": "LEFT 20", "quarter": "1", "clock_seconds": 720, "clock_running": False,
            "clock_visible": True, "clock_started_at": 0,
            "home_direction": "right", "visitor_direction": "left", "special_game_phase": "",
            "kicking_team": "", "receiving_team": "",
            "next_play_number": 1, "events": [], "plays": [], "history": [], "correction_log": [],
            "last_event": {}, "player_graphic": {"visible": False}, "team_roles": {},
        }
        self.store.update(patch)
        tick = itertools.count(1000)
        self.graphics = []

        class _Lock:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        self.rules = RulesService(
            load_state=self.load, save_state=self.save, push_history=lambda s: None,
            source_allowed=EventService.source_allowed, locked_payload=EventService.locked_payload,
            resolve_player=_resolver,
            show_player_graphic=lambda *a, **k: self.graphics.append(a[2].get("number")),
            transaction_lock=threading.Lock(), now=lambda: next(tick),
        )
        self.events = EventService(
            load_state=self.load, save_state=self.save, public_state=lambda v: copy.deepcopy(dict(v)),
            push_history=lambda v: None, update_linked_status=lambda *a, **k: None,
            automation_player=lambda a, b: (None, None), manual_player=lambda *a, **k: None,
            player_display=lambda p: "", show_player_graphic=lambda *a, **k: None,
            apply_penalty=lambda *a, **k: {}, spot_to_coord=RulesService.spot_to_coord,
            coord_to_spot=RulesService.coord_to_spot, team_direction=RulesService.team_direction,
            normalize_state=lambda v: copy.deepcopy(dict(v)),
            default_player_graphic=lambda: {"visible": False}, transaction_lock=_Lock(),
            now=lambda: next(tick),
        )

    def load(self):
        return copy.deepcopy(self.store)

    def save(self, value):
        self.store.clear()
        self.store.update(copy.deepcopy(dict(value)))

    def play(self, **payload):
        result = self.rules.play(payload)
        assert result.ok, (result.code, result.data)
        return result.data["play"]

    def run(self, team, start, end, **extra):
        return self.play(team=team, play_type="run", start_spot=start, end_spot=end, **extra)

    def period(self, action, **kw):
        result = PeriodService.transition(self.store, action, **kw)
        assert result.ok, result.code
        self.save(result.state)

    def entry(self, index):
        """What the Edit button pre-fills the play form with."""
        play = self.store["plays"][index]
        event = next(e for e in self.store["events"] if e["id"] == play["event_id"])
        return RulesService.entry_from_play(play, event)

    def reenter(self, index, **changes):
        play = self.store["plays"][index]
        payload = {**self.entry(index), **changes, "source": "statistician"}
        return self.rules.reenter(play["event_id"], payload)

    def edit(self, index, **changes):
        result = self.reenter(index, **changes)
        assert result.ok, (result.code, result.data)
        return result.data

    def report(self):
        return StatisticsService().report(dict(self.store)).data["statistics"]

    def plays(self):
        return self.store["plays"]


def _player(report, team, number):
    return next(
        (p for p in report["players"] if p["number"] == number and p.get("team") in {team, None}),
        None,
    )


def _down(state):
    return (state["down"], state["distance"], state["ball_spot"])


# --- the end spot fix --------------------------------------------------------


def test_moving_the_end_spot_recomputes_down_distance_first_down_and_the_result_text():
    g = Game()
    g.run("home", "LEFT 20", "LEFT 25", player_number="7")
    assert _down(g.store) == ("2nd", "5", "LEFT 25")

    data = g.edit(0, end_spot="LEFT 32")

    assert _down(g.store) == ("1st", "10", "LEFT 32")
    play = g.plays()[0]
    assert (play["yards"], play["first_down"], play["end_spot"]) == (12, True, "LEFT 32")
    assert play["result"] == "#7 Caleb Lang run for 12 yards, first down"
    event = g.store["events"][0]
    assert event["description"] == play["result"]
    assert (event["after"]["down"], event["after"]["distance"]) == ("1st", "10")
    assert event["automation"]["yards"] == "12"
    assert data["play"]["result"] == play["result"]


def test_fixing_an_early_play_re_derives_the_rest_of_the_drive():
    g = Game()
    g.run("home", "LEFT 20", "LEFT 25")  # 2nd & 5
    g.run("home", "LEFT 25", "LEFT 28")  # 3rd & 2
    g.run("home", "LEFT 28", "LEFT 31")  # 1st & 10 (gained 3, needed 2)
    assert g.plays()[2]["first_down"] is True

    # Play 1 really went to LEFT 22: play 2 now starts there (its end spot stays
    # where it was set on the field), and play 3 comes up a yard short.
    g.edit(0, end_spot="LEFT 22")

    p1, p2, p3 = g.plays()
    assert (p1["yards"], p1["end_spot"]) == (2, "LEFT 22")
    assert (p2["ball_spot"], p2["end_spot"], p2["yards"], p2["down"], p2["distance"]) == ("LEFT 22", "LEFT 28", 6, "2nd", "8")
    assert p2["first_down"] is False and p2["result"] == "Home run for 6 yards"
    assert (p3["down"], p3["distance"], p3["yards"], p3["first_down"]) == ("3rd", "2", 3, True)
    assert _down(g.store) == ("1st", "10", "LEFT 31")
    afters = [(e["after"]["down"], e["after"]["distance"]) for e in g.store["events"]]
    assert afters == [("2nd", "8"), ("3rd", "2"), ("1st", "10")]


def test_a_start_spot_the_statistician_corrected_is_kept_on_replay():
    g = Game()
    g.run("home", "LEFT 20", "LEFT 25")
    g.run("home", "LEFT 30", "LEFT 33")  # start spot corrected by hand to LEFT 30
    g.edit(0, end_spot="LEFT 27")
    assert g.plays()[1]["ball_spot"] == "LEFT 30"
    assert g.plays()[1]["yards"] == 3


# --- jerseys -----------------------------------------------------------------


def test_fixing_an_unresolved_jersey_after_the_game_moves_the_stats_credit():
    g = Game()
    g.play(team="home", play_type="pass", start_spot="LEFT 20", end_spot="LEFT 45",
           passer_number="12", receiver_number="81", pass_outcome="complete")
    assert g.plays()[0]["unresolved_players"] == ["receiver"]
    assert _player(g.report(), "home", "11") is None

    g.edit(0, receiver_number="11", receiver_name="")

    play = g.plays()[0]
    assert play["unresolved_players"] == []
    assert play["receiver_name"] == "Wide Out"
    assert play["result"] == "#12 Quarter Back complete to #11 Wide Out for 25 yards, first down"
    report = g.report()
    receiver = _player(report, "home", "11")
    assert (receiver["receptions"], receiver["receiving_yards"]) == (1, 25)
    stale = _player(report, "home", "81")
    assert stale is None or stale["receiving_yards"] == 0


def test_fixing_a_team_mismatch_jersey_clears_the_flag():
    g = Game()
    g.run("home", "LEFT 20", "LEFT 24", player_number="22")  # #22 is a visitor
    assert g.plays()[0]["team_mismatch_players"][0]["number"] == "22"
    g.edit(0, player_number="7")
    play = g.plays()[0]
    assert play["team_mismatch_players"] == [] and play["unresolved_players"] == []
    assert play["player_name"] == "Caleb Lang"
    assert _player(g.report(), "home", "7")["rushing_yards"] == 4


def test_a_jersey_fix_on_a_touchdown_keeps_the_try_and_the_kickoff_after_it():
    g = Game(ball_spot="RIGHT 10")
    g.run("home", "RIGHT 10", "RIGHT GOAL", player_number="70")
    assert g.store["special_game_phase"] == "pending_try"
    xp = g.events.trigger({"event": "XP", "team": "home", "source": "statistician"})
    assert xp.ok, xp.code
    assert g.store["home_score"] == 7 and g.store["special_game_phase"] == "kickoff"
    g.play(team="home", play_type="kickoff", landing_spot="RIGHT 5", end_spot="RIGHT 30",
           kicker_number="9", returner_number="4")
    g.run("visitor", "RIGHT 30", "RIGHT 36")
    graphics_before = list(g.graphics)

    g.edit(0, player_number="7", player_name="")

    assert g.store["home_score"] == 7 and g.store["visitor_score"] == 0
    assert g.plays()[0]["result"] == "#7 Caleb Lang run for 10 yards, touchdown"
    assert g.store["events"][0]["automation"]["player_number"] == "7"
    assert _down(g.store) == ("2nd", "4", "RIGHT 36")
    assert g.store["possession"] == "visitor"
    assert g.graphics == graphics_before  # no spotlight replayed for a past play
    assert _player(g.report(), "home", "7")["touchdowns"] == 1


# --- across a quarter change ---------------------------------------------------


def _game_into_q2():
    g = Game()
    g.run("home", "LEFT 20", "LEFT 25")  # 2nd & 5
    g.run("home", "LEFT 25", "LEFT 28")  # 3rd & 2
    g.period("end_quarter")  # ends change: ball mirrors to RIGHT 28, home now drives left
    assert g.store["ball_spot"] == "RIGHT 28"
    g.store["clock_seconds"] = 455
    g.run("home", "RIGHT 28", "RIGHT 33")  # 3rd & 2 -> 5 yards, 1st & 10
    g.store["clock_seconds"] = 301
    return g


def test_an_older_play_edit_ripples_across_the_quarter_change_with_mirrored_spots():
    g = _game_into_q2()

    g.edit(0, end_spot="LEFT 22")  # play 1: +5 -> +2

    p1, p2, p3 = g.plays()
    assert (p1["yards"], p2["ball_spot"], p2["yards"]) == (2, "LEFT 22", 6)
    assert (p2["down"], p2["distance"]) == ("2nd", "8")
    # Play 2 still ends at LEFT 28 (2 yards short of the line to gain), the
    # break mirrors it to RIGHT 28, and the Q2 play starts 3rd & 2 from there.
    assert (p3["ball_spot"], p3["down"], p3["distance"], p3["quarter"]) == ("RIGHT 28", "3rd", "2", "2")
    assert (p3["end_spot"], p3["yards"], p3["first_down"]) == ("RIGHT 33", 5, True)
    s = g.store
    assert (s["quarter"], s["clock_seconds"], s["home_direction"]) == ("2", 301, "left")
    assert _down(s) == ("1st", "10", "RIGHT 33")
    recorded = [(e["before"]["quarter"], e["before"]["home_direction"]) for e in s["events"]]
    assert recorded == [("1", "right"), ("1", "right"), ("2", "left")]


def test_an_older_play_edit_moves_the_mirrored_start_of_the_next_quarters_play():
    g = _game_into_q2()
    g.edit(1, end_spot="LEFT 35")  # play 2 really reached LEFT 35: 1st & 10
    p3 = g.plays()[2]
    # LEFT 35 mirrors to RIGHT 35 at the change of ends; home drives left.
    assert (p3["ball_spot"], p3["down"], p3["distance"]) == ("RIGHT 35", "1st", "10")
    assert (p3["end_spot"], p3["yards"]) == ("RIGHT 33", -2)
    assert _down(g.store) == ("2nd", "12", "RIGHT 33")


# --- scoring -----------------------------------------------------------------


def test_moving_the_end_spot_into_the_end_zone_scores_the_touchdown():
    g = Game(ball_spot="RIGHT 10")
    g.run("home", "RIGHT 10", "RIGHT 2", player_number="7")
    assert g.store["home_score"] == 0

    g.edit(0, end_spot="RIGHT GOAL")

    s = g.store
    assert s["home_score"] == 6 and s["special_game_phase"] == "pending_try"
    play = g.plays()[0]
    assert play["touchdown"] is True and play["label"] == "Touchdown Run"
    assert play["result"] == "#7 Caleb Lang run for 10 yards, touchdown"
    assert s["events"][0]["score_delta"] == 6
    assert _player(g.report(), "home", "7")["touchdowns"] == 1


def test_moving_the_end_spot_out_of_the_end_zone_takes_the_touchdown_back():
    g = Game(ball_spot="RIGHT 10")
    g.run("home", "RIGHT 10", "RIGHT GOAL", player_number="7")
    assert g.store["home_score"] == 6

    g.edit(0, end_spot="RIGHT 1")

    s = g.store
    assert s["home_score"] == 0 and s["special_game_phase"] == ""
    assert _down(s) == ("2nd", "1", "RIGHT 1")
    play = g.plays()[0]
    assert play["touchdown"] is False and play["label"] == "Run"
    assert s["events"][0]["score_delta"] == 0


def test_a_safety_edit_scores_for_the_defense():
    g = Game(ball_spot="LEFT 3")
    g.run("home", "LEFT 3", "LEFT 1")
    g.edit(0, end_spot="LEFT GOAL")
    s = g.store
    assert (s["home_score"], s["visitor_score"], s["special_game_phase"]) == (0, 2, "free_kick")


def test_an_edit_that_changes_scoring_under_later_plays_is_refused_and_nothing_changes():
    g = Game(ball_spot="RIGHT 10")
    g.run("home", "RIGHT 10", "RIGHT 5")
    g.run("home", "RIGHT 5", "RIGHT 2")
    snapshot = copy.deepcopy(g.store)

    result = g.reenter(0, end_spot="RIGHT GOAL")

    assert result.code == "EDIT_CONFLICTS_WITH_LATER_EVENTS"
    assert result.data["play_number"] == 2
    assert g.store == snapshot


def test_removing_a_touchdown_that_has_a_try_after_it_is_refused():
    g = Game(ball_spot="RIGHT 10")
    g.run("home", "RIGHT 10", "RIGHT GOAL")
    assert g.events.trigger({"event": "XP", "team": "home", "source": "statistician"}).ok
    result = g.reenter(0, end_spot="RIGHT 1")
    assert result.code == "EDIT_CONFLICTS_WITH_LATER_EVENTS"
    assert g.store["home_score"] == 7


# --- turnovers and kicks ---------------------------------------------------------


def test_adding_a_lost_fumble_to_the_latest_play_turns_the_ball_over():
    g = Game()
    g.run("home", "LEFT 20", "LEFT 30", player_number="7")
    g.edit(0, fumble=True, fumble_lost=True, turnover_spot="LEFT 30", return_end_spot="LEFT 26",
           returner_number="8")
    s = g.store
    assert s["possession"] == "visitor" and _down(s) == ("1st", "10", "LEFT 26")
    play = g.plays()[0]
    assert play["turnover_type"] == "fumble_recovery" and play["turnover_player_number"] == "8"
    assert "fumble lost, recovered by #8 Visitor Eight at Home 30" in play["result"]


def test_a_punt_edit_recomputes_the_return_and_the_next_series():
    g = Game(down="4th", distance="8", ball_spot="LEFT 30")
    # Visitor returns toward the LEFT goal.
    g.play(team="home", play_type="punt", landing_spot="RIGHT 30", end_spot="RIGHT 35",
           kicker_number="9", returner_number="4")
    g.run("visitor", "RIGHT 35", "RIGHT 40")
    assert g.plays()[0]["return_yards"] == 5

    g.edit(0, end_spot="RIGHT 45")

    punt, run = g.plays()
    assert punt["return_yards"] == 15
    assert punt["result"] == "Punt by #9 Home Punter landed at Visitor 30, returned by #4 Visitor Returner for 15 yards to Visitor 45"
    assert (run["ball_spot"], run["yards"], run["down"]) == ("RIGHT 45", -5, "1st")
    assert _down(g.store) == ("2nd", "15", "RIGHT 40")


def test_a_punt_can_be_changed_to_a_fair_catch():
    g = Game(down="4th", distance="8", ball_spot="LEFT 30")
    g.play(team="home", play_type="punt", landing_spot="RIGHT 30", end_spot="RIGHT 25",
           kicker_number="9", returner_number="4")
    g.edit(0, fair_catch=True, end_spot="RIGHT 30")
    punt = g.plays()[0]
    assert punt["result"].endswith("— fair catch") and punt["entry"]["fair_catch"] is True
    assert _player(g.report(), "visitor", "4") is None or _player(g.report(), "visitor", "4")["punt_returns"] == 0


# --- history plumbing ---------------------------------------------------------------


def test_the_edit_is_logged_with_its_note_and_bumps_the_revision():
    g = Game()
    g.run("home", "LEFT 20", "LEFT 25")
    revision = int(g.store.get("state_revision", 0) or 0)
    g.edit(0, end_spot="LEFT 27", note="spotted at the 27")
    entry = g.store["correction_log"][-1]
    assert entry["kind"] == "play_edit" and entry["note"] == "spotted at the 27"
    assert entry["play_before"]["end_spot"] == "LEFT 25" and entry["play_after"]["end_spot"] == "LEFT 27"
    assert int(g.store["state_revision"]) == revision + 1


def test_a_repeated_command_id_is_applied_once():
    g = Game()
    g.run("home", "LEFT 20", "LEFT 25")
    first = g.edit(0, end_spot="LEFT 27", command_id="cmd-edit-1")
    log_length = len(g.store["correction_log"])
    second = g.edit(0, end_spot="LEFT 40", command_id="cmd-edit-1")
    assert second["play"]["end_spot"] == first["play"]["end_spot"] == "LEFT 27"
    assert len(g.store["correction_log"]) == log_length


def test_ids_numbers_and_counter_are_kept():
    g = Game()
    g.run("home", "LEFT 20", "LEFT 25")
    g.run("home", "LEFT 25", "LEFT 28")
    ids = [(p["play_id"], p["event_id"], p["play_number"], p["created_at"]) for p in g.plays()]
    g.edit(0, end_spot="LEFT 23")
    assert [(p["play_id"], p["event_id"], p["play_number"], p["created_at"]) for p in g.plays()] == ids
    assert g.store["next_play_number"] == 3
    assert g.store["last_event"]["id"] == g.store["events"][-1]["id"]
    assert g.store["last_event"]["description"] == g.plays()[-1]["result"]


def test_undo_and_restore_still_work_after_an_edit():
    g = Game()
    g.run("home", "LEFT 20", "LEFT 25")
    g.run("home", "LEFT 25", "LEFT 28")
    g.edit(0, end_spot="LEFT 22")
    assert g.events.undo({}).ok
    assert len(g.plays()) == 1 and _down(g.store) == ("2nd", "8", "LEFT 22")
    assert g.events.restore({}).ok
    assert len(g.plays()) == 2 and _down(g.store) == ("3rd", "2", "LEFT 28")


def test_a_quick_correction_between_plays_still_stands_after_an_edit():
    g = Game()
    g.run("home", "LEFT 20", "LEFT 25")
    assert g.events.quick_correction({"source": "statistician", "down": "3rd", "distance": "5", "ball_spot": "LEFT 25"}).ok
    g.run("home", "LEFT 25", "LEFT 27")
    g.edit(0, end_spot="LEFT 24", player_number="7")
    # The hand-corrected down stands. Distance and spot were not changed by the
    # correction, so they follow the edited play (and the start spot, which
    # followed the ball, follows the corrected ball).
    p2 = g.plays()[1]
    assert (p2["down"], p2["distance"], p2["ball_spot"]) == ("3rd", "6", "LEFT 24")
    assert (p2["yards"], g.store["down"]) == (3, "4th")


def test_a_play_recorded_before_this_change_is_reconstructed_for_replay():
    g = Game(down="4th", distance="8", ball_spot="LEFT 30")
    g.play(team="home", play_type="punt", landing_spot="RIGHT 30", end_spot="RIGHT 25",
           kicker_number="9", returner_number="4", touchback=False)
    g.play(team="visitor", play_type="pass", end_spot="RIGHT 35", passer_number="22",
           receiver_number="8", pass_outcome="complete")
    g.run("visitor", "RIGHT 35", "RIGHT 38")
    for play in g.plays():
        play.pop("entry")
    g.edit(0, end_spot="RIGHT 30")
    _punt, catch, run = g.plays()
    assert (catch["ball_spot"], catch["yards"], catch["result"]) == (
        "RIGHT 30", 5, "#22 Visitor Back complete to #8 Visitor Eight for 5 yards",
    )
    assert (run["down"], run["distance"]) == ("2nd", "5")


def test_entry_from_play_reconstructs_kick_flags_from_the_result_text():
    legacy = {
        "play_type": "punt", "kicking_team": "home", "offense": "visitor", "ball_spot": "LEFT 30",
        "end_spot": "RIGHT 20", "landing_spot": "RIGHT 5", "kicker_number": "9",
        "result": "Punt by #9 landed at RIGHT 5, ball at RIGHT 20 — touchback",
    }
    entry = RulesService.entry_from_play(legacy)
    assert entry["team"] == "home" and entry["touchback"] is True and entry["fair_catch"] is False


def test_non_play_events_are_not_re_entered():
    g = Game()
    g.run("home", "LEFT 20", "LEFT 25")
    assert g.events.trigger({"event": "FIRST_DOWN", "team": "home", "source": "statistician"}).ok
    other = g.store["events"][-1]
    assert other["event"] != "PLAY"
    result = g.rules.reenter(other["id"], {"team": "home", "play_type": "run", "source": "statistician"})
    assert result.code == "NOT_A_RULES_PLAY"


def test_a_locked_console_cannot_re_enter():
    g = Game()
    g.run("home", "LEFT 20", "LEFT 25")
    g.store["game_data_authority"] = "broadcaster"
    assert g.reenter(0, end_spot="LEFT 30").code == "CONTROL_SOURCE_LOCKED"


def test_live_play_entry_records_the_form_inputs_for_later_edits():
    g = Game(down="4th", distance="8", ball_spot="LEFT 30")
    play = g.play(team="home", play_type="punt", landing_spot="RIGHT 30", end_spot="RIGHT 30",
                  kicker_number="9", returner_number="4", fair_catch=True, blocked=False, notes="wind")
    entry = play["entry"]
    assert (entry["team"], entry["play_type"], entry["start_spot"], entry["landing_spot"]) == (
        "home", "punt", "LEFT 30", "RIGHT 30",
    )
    assert entry["fair_catch"] is True and entry["kicker_number"] == "9" and entry["notes"] == "wind"


# --- console wiring -------------------------------------------------------------------


def _index_html() -> str:
    return (Path(__file__).resolve().parents[1] / "templates" / "index.html").read_text(encoding="utf-8")


def _js_function(source: str, name: str) -> str:
    start = source.index(f"function {name}(")
    return source[start: source.index("\nfunction ", start + 1)]


def test_edit_and_quick_edit_open_the_play_form_for_rules_plays():
    html = _index_html()
    open_edit = _js_function(html, "openEditEvent")
    assert "openPlayEditor(" in open_edit
    quick = _js_function(html, "quickEditLastPlay")
    assert "openEditEvent(" in quick
    editor = _js_function(html, "openPlayEditor")
    for field in ("playBallCarrier", "playPasser", "playReceiver", "playSacker", "playKicker",
                  "playReturner", "playRecoverer", "playPassOutcome", "playNotes"):
        assert field in editor or field in _js_function(html, "fillPlayEntryFromRecord")
    fill = _js_function(html, "fillPlayEntryFromRecord")
    for flag in ("kneel", "fumble", "fumble_lost", "muffed_punt", "downed", "out_of_bounds",
                 "touchback", "fair_catch", "blocked"):
        assert f"entry.{flag}" in fill


def test_saving_an_edit_posts_the_play_form_to_the_reentry_route():
    html = _index_html()
    submit = html[html.index("async function submitPlayEntry"):]
    submit = submit[: submit.index("\nasync function ") if "\nasync function " in submit[1:] else len(submit)]
    assert "/api/plays/${encodeURIComponent(playEntryEdit.eventId)}/reenter" in html
    assert 'id="playEditNote"' in html
