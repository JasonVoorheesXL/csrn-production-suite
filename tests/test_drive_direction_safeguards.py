"""Wrong-drive-direction safeguards (2026-10-23).

Every 2026 football game had plays entered with the drive arrow pointing the
wrong way: spots are screen-fixed (LEFT/RIGHT) and yards come from the team's
drive direction, so every gain was saved as a loss (Pontotoc Q1 plays 2-12, a
false turnover on downs), and kicks went "backwards". In all five games with
usable data the teams kept their 2nd-quarter ends for the second half, but the
halftime default mirrored them.

1. Halftime: "keep" / "swap" (relative to the 2nd quarter) join the receiver's
   LEFT/RIGHT; the console makes the operator pick (empty stays the mirror for
   API callers).
2. The play form can ask play() to stop before saving a play that looks like a
   wrong arrow (DIRECTION_SUSPECT): a kick that lands behind the kicker, or a
   streak of losses by one offense.
3. Flipping the drive arrow can keep the ball's yard line (mirror the screen
   spot) instead of leaving it where it is on the field.
4. repair_direction(): re-run a range of recorded plays with the arrow flipped.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from period_service import PeriodService
from test_edit_play_reentry import Game
from test_football_incident_20260918 import _halftime, _ops, _unknown_receiver_halftime

import app as app_module
from rules_service import RulesResult

INDEX = (Path(__file__).resolve().parents[1] / "templates" / "index.html").read_text(encoding="utf-8")


# --- 1. halftime ---------------------------------------------------------------


@pytest.mark.parametrize("choice", ["keep", "same", "KEEP"])
def test_second_half_can_keep_the_2nd_quarter_ends(choice) -> None:
    result = PeriodService.transition(_halftime(), "start_second_half", second_half_drive_direction=choice)
    assert result.ok, result.code
    s = result.state
    assert (s["home_direction"], s["visitor_direction"]) == ("right", "left")
    assert s["quarter"] == "3" and s["special_game_phase"] == "kickoff"


@pytest.mark.parametrize("choice", ["swap", "switch", "mirror", ""])
def test_second_half_swap_is_the_historical_mirror(choice) -> None:
    result = PeriodService.transition(_halftime(), "start_second_half", second_half_drive_direction=choice)
    assert result.ok, result.code
    assert (result.state["home_direction"], result.state["visitor_direction"]) == ("left", "right")


def test_direction_choice_normalisation() -> None:
    choice = PeriodService.second_half_direction_choice
    assert [choice(v) for v in ("", None, "auto", "swap", "keep", "same", "left", "RIGHT", "up")] == [
        "swap", "swap", "swap", "swap", "keep", "keep", "left", "right", None,
    ]


def test_keep_applies_even_when_the_second_half_receiver_is_unknown() -> None:
    """keep/swap need no receiver, unlike LEFT/RIGHT (receiver-relative)."""
    service, store = _ops(_unknown_receiver_halftime())
    result = service.toggle_halftime({"second_half_drive_direction": "keep"})
    assert result.ok
    s = store["state"]
    assert (s["home_direction"], s["visitor_direction"], s["ball_spot"]) == ("right", "left", "LEFT 40")
    assert s["quarter"] == "3" and s["broadcast_phase"] == "live"
    assert "period_action_notice" not in result.data["state"]


def test_swap_with_unknown_receiver_still_mirrors_the_ball_without_a_notice() -> None:
    service, store = _ops(_unknown_receiver_halftime())
    result = service.toggle_halftime({"second_half_drive_direction": "swap"})
    s = store["state"]
    assert (s["home_direction"], s["visitor_direction"], s["ball_spot"]) == ("left", "right", "RIGHT 40")
    assert "period_action_notice" not in result.data["state"]


def test_set_values_start_second_half_passes_keep_through() -> None:
    service, store = _ops(_halftime(game_data_authority="statistician"))
    result = service.set_values({
        "source": "statistician", "period_action": "start_second_half",
        "second_half_drive_direction": "keep",
    })
    assert result.ok, result.code
    s = store["state"]
    assert s["quarter"] == "3"
    assert (s["home_direction"], s["visitor_direction"]) == ("right", "left")


# --- 3. flipping the arrow -----------------------------------------------------


def _flip(g, **payload):
    result = g.rules.field_direction(payload)
    assert result.ok, result.code
    return g.store


def test_flipping_the_arrow_leaves_the_ball_on_the_field_by_default() -> None:
    g = Game(ball_spot="LEFT 28")
    s = _flip(g, team="home", direction="left")
    assert (s["home_direction"], s["visitor_direction"], s["ball_spot"]) == ("left", "right", "LEFT 28")


def test_flipping_the_arrow_can_keep_the_yard_line() -> None:
    g = Game(ball_spot="LEFT 28")
    s = _flip(g, team="home", direction="left", ball="yard_line")
    assert (s["home_direction"], s["visitor_direction"], s["ball_spot"]) == ("left", "right", "RIGHT 28")


def test_keeping_the_yard_line_without_a_real_flip_does_not_move_the_ball() -> None:
    g = Game(ball_spot="LEFT 28")
    s = _flip(g, team="home", direction="right", ball="yard_line")
    assert s["ball_spot"] == "LEFT 28"
    # visitor's arrow set to the direction it already has
    s = _flip(g, team="visitor", direction="left", ball="yard_line")
    assert s["ball_spot"] == "LEFT 28"


def test_flipping_the_arrow_rejects_an_unknown_ball_choice() -> None:
    g = Game(ball_spot="LEFT 28")
    result = g.rules.field_direction({"team": "home", "direction": "left", "ball": "teleport"})
    assert result.code == "INVALID_DIRECTION"
    assert (g.store["home_direction"], g.store["ball_spot"]) == ("right", "LEFT 28")


# --- 2. the play-form sanity check ---------------------------------------------


def _wrong_arrow_game(**patch):
    """Home really drives RIGHT, but the arrow says LEFT (Pontotoc Q1)."""
    fields = dict(home_direction="left", visitor_direction="right", ball_spot="LEFT 16")
    fields.update(patch)
    return Game(**fields)


def _checked_run(g, start, end, **extra):
    return g.rules.play({
        "team": "home", "play_type": "run", "start_spot": start, "end_spot": end,
        "direction_check": True, **extra,
    })


def test_third_loss_in_a_row_stops_before_saving() -> None:
    g = _wrong_arrow_game()
    assert _checked_run(g, "LEFT 16", "LEFT 15").ok   # +1
    assert _checked_run(g, "LEFT 15", "LEFT 24").ok   # -9
    assert _checked_run(g, "LEFT 24", "LEFT 25").ok   # -1 (two losses, only 10 yards)
    saved = len(g.plays())

    result = _checked_run(g, "LEFT 25", "LEFT 27")    # -2: third loss

    assert result.code == "DIRECTION_SUSPECT"
    assert len(g.plays()) == saved and g.store["ball_spot"] == "LEFT 25"
    data = result.data
    assert data["error"] == "DIRECTION_SUSPECT" and data["reason"] == "loss_streak"
    assert (data["team"], data["team_direction"], data["yards"], data["flipped_yards"]) == ("home", "left", -2, 2)
    assert data["losses"] == [-9, -1, -2]
    assert "3 losses in a row" in data["message"] and "LEFT" in data["message"]


def test_two_big_losses_in_a_row_stop_before_saving() -> None:
    g = _wrong_arrow_game(ball_spot="LEFT 22")
    assert _checked_run(g, "LEFT 22", "LEFT 33").ok   # -11
    result = _checked_run(g, "LEFT 33", "LEFT 47")    # -14
    assert result.code == "DIRECTION_SUSPECT"
    assert result.data["losses"] == [-11, -14]


def test_confirming_saves_the_play_as_entered() -> None:
    g = _wrong_arrow_game(ball_spot="LEFT 22")
    assert _checked_run(g, "LEFT 22", "LEFT 33").ok
    result = _checked_run(g, "LEFT 33", "LEFT 47", direction_confirmed=True)
    assert result.ok
    assert g.plays()[-1]["yards"] == -14


def test_flipping_the_arrow_then_saving_turns_the_loss_into_the_gain() -> None:
    """What the console's "Flip arrow and save" button does."""
    g = _wrong_arrow_game(ball_spot="LEFT 22")
    assert _checked_run(g, "LEFT 22", "LEFT 33").ok
    assert _checked_run(g, "LEFT 33", "LEFT 47").code == "DIRECTION_SUSPECT"

    _flip(g, team="home", direction="right")          # ball stays where it was set
    result = _checked_run(g, "LEFT 33", "LEFT 47")

    assert result.ok, result.data
    assert g.plays()[-1]["yards"] == 14


def test_no_check_unless_the_form_asks_for_it() -> None:
    g = _wrong_arrow_game(ball_spot="LEFT 22")
    g.run("home", "LEFT 22", "LEFT 33")
    g.run("home", "LEFT 33", "LEFT 47")
    g.run("home", "LEFT 47", "LEFT 48")
    assert [p["yards"] for p in g.plays()] == [-11, -14, -1]


def test_a_gain_breaks_the_streak_and_zero_yard_plays_are_skipped() -> None:
    g = Game(ball_spot="LEFT 30")
    assert _checked_run(g, "LEFT 30", "LEFT 27").ok   # -3
    assert _checked_run(g, "LEFT 27", "LEFT 41").ok   # +14 breaks it
    assert _checked_run(g, "LEFT 41", "LEFT 39").ok   # -2
    assert g.rules.play({
        "team": "home", "play_type": "pass", "start_spot": "LEFT 39", "end_spot": "LEFT 39",
        "pass_outcome": "incomplete", "direction_check": True,
    }).ok
    assert _checked_run(g, "LEFT 39", "LEFT 37").ok   # -2: only two losses, 4 yards
    assert _checked_run(g, "LEFT 37", "LEFT 35").code == "DIRECTION_SUSPECT"  # third (incomplete skipped)


def test_sacks_and_kneels_are_expected_losses() -> None:
    g = Game(ball_spot="LEFT 40")
    sack = {"team": "home", "play_type": "pass", "pass_outcome": "sack", "direction_check": True}
    assert g.rules.play({**sack, "start_spot": "LEFT 40", "end_spot": "LEFT 30"}).ok
    assert g.rules.play({**sack, "start_spot": "LEFT 30", "end_spot": "LEFT 20"}).ok
    assert _checked_run(g, "LEFT 20", "LEFT 19").ok   # one counted loss
    assert _checked_run(g, "LEFT 19", "LEFT 17", kneel=True).ok


def test_a_quarter_break_or_the_other_offense_starts_a_new_streak() -> None:
    g = Game(ball_spot="LEFT 40")
    assert _checked_run(g, "LEFT 40", "LEFT 30").ok   # -10
    g.store["quarter"] = "2"
    assert _checked_run(g, "LEFT 30", "LEFT 20").ok   # -10, new quarter


def test_a_kick_that_lands_behind_the_kicker_stops_before_saving() -> None:
    g = Game(ball_spot="LEFT 40", special_game_phase="kickoff", kicking_team="home", receiving_team="visitor")
    kick = {"team": "home", "play_type": "kickoff", "start_spot": "LEFT 40", "direction_check": True}

    result = g.rules.play({**kick, "landing_spot": "LEFT 22", "end_spot": "LEFT 22"})

    assert result.code == "DIRECTION_SUSPECT"
    assert result.data["reason"] == "kick_backwards"
    assert (result.data["yards"], result.data["flipped_yards"]) == (-18, 18)
    assert "BEHIND the kicker" in result.data["message"]
    assert g.plays() == []
    assert g.rules.play({**kick, "landing_spot": "RIGHT 5", "end_spot": "RIGHT 25"}).ok


def test_a_backwards_punt_warns_but_a_blocked_one_does_not() -> None:
    punt = {"team": "home", "play_type": "punt", "start_spot": "LEFT 30", "direction_check": True}
    g = Game(ball_spot="LEFT 30", down="4th")
    assert g.rules.play({**punt, "landing_spot": "LEFT 10", "end_spot": "LEFT 10"}).code == "DIRECTION_SUSPECT"
    assert g.rules.play({**punt, "landing_spot": "LEFT 20", "end_spot": "LEFT 20", "blocked": True}).ok


# --- 4. post-game repair -------------------------------------------------------


def _repair(g, first, last, **payload):
    plays = g.plays()
    return g.rules.repair_direction(
        plays[first]["event_id"],
        {"last_event_id": plays[last]["event_id"], "source": "statistician", **payload},
    )


def test_repair_turns_the_losses_back_into_gains_and_removes_a_false_turnover_on_downs() -> None:
    g = _wrong_arrow_game()
    g.run("home", "LEFT 16", "LEFT 15")
    g.run("home", "LEFT 15", "LEFT 24")
    g.run("home", "LEFT 24", "LEFT 25")
    g.run("home", "LEFT 25", "LEFT 27")
    assert [p["yards"] for p in g.plays()] == [1, -9, -1, -2]
    assert g.plays()[-1]["turnover_type"] == "downs" and g.store["possession"] == "visitor"

    result = _repair(g, 0, 3, note="arrow was wrong")

    assert result.ok, result.data
    plays = g.plays()
    assert [p["yards"] for p in plays] == [-1, 9, 1, 2]
    assert [(p["down"], p["distance"]) for p in plays] == [("1st", "10"), ("2nd", "11"), ("3rd", "2"), ("4th", "1")]
    assert plays[-1]["first_down"] is True and not plays[-1]["turnover"]
    assert (g.store["possession"], g.store["down"], g.store["distance"], g.store["ball_spot"]) == ("home", "1st", "10", "LEFT 27")
    # the repaired events now say which way the team really drove
    assert all(e["before"]["home_direction"] == "right" for e in g.store["events"])
    # a repair never changes the live arrow
    assert g.store["home_direction"] == "left"
    log = g.store["correction_log"][-1]
    assert (log["kind"], log["flipped_events"], log["note"]) == ("direction_repair", 4, "arrow was wrong")


def test_repair_leaves_plays_after_the_range_where_they_were_set() -> None:
    """The operator noticed and flipped the arrow mid-drive (ball left on the field)."""
    g = _wrong_arrow_game()
    g.run("home", "LEFT 16", "LEFT 15")              # +1 (really -1)
    g.run("home", "LEFT 15", "LEFT 24")              # -9 (really +9): 3rd & 18
    _flip(g, team="home", direction="right")
    g.run("home", "LEFT 24", "LEFT 30")              # +6: 4th & 12

    assert _repair(g, 0, 1).ok

    p1, p2, p3 = g.plays()
    assert (p1["yards"], p2["yards"]) == (-1, 9)
    assert (p3["ball_spot"], p3["yards"], p3["down"], p3["distance"], p3["first_down"]) == ("LEFT 24", 6, "3rd", "2", True)
    assert (g.store["down"], g.store["distance"], g.store["ball_spot"]) == ("1st", "10", "LEFT 30")
    assert g.store["events"][2]["before"]["home_direction"] == "right"


def test_repair_that_would_change_possession_under_a_later_play_is_refused() -> None:
    g = _wrong_arrow_game()
    for start, end in (("LEFT 16", "LEFT 15"), ("LEFT 15", "LEFT 24"), ("LEFT 24", "LEFT 25"), ("LEFT 25", "LEFT 27")):
        g.run("home", start, end)
    g.run("visitor", "LEFT 27", "LEFT 30")           # the false turnover on downs gave visitor the ball
    before = g.load()

    result = _repair(g, 0, 3)

    assert result.code == "EDIT_CONFLICTS_WITH_LATER_EVENTS"
    assert "possession" in result.data["message"]
    assert g.load() == before


def test_repair_rejects_a_range_that_ends_before_it_starts() -> None:
    g = Game()
    g.run("home", "LEFT 20", "LEFT 25")
    g.run("home", "LEFT 25", "LEFT 30")
    result = _repair(g, 1, 0)
    assert result.code == "INVALID_REPAIR_RANGE"


def test_repair_of_a_kick_sends_it_forward() -> None:
    g = Game(ball_spot="LEFT 40", home_direction="left", visitor_direction="right",
             special_game_phase="kickoff", kicking_team="home", receiving_team="visitor")
    g.play(team="home", play_type="kickoff", start_spot="LEFT 40", landing_spot="RIGHT 5", end_spot="RIGHT 25")
    assert (g.plays()[0]["yards"], g.plays()[0]["return_yards"]) == (-35, 0)

    assert _repair(g, 0, 0).ok

    play = g.plays()[0]
    assert (play["yards"], play["return_yards"]) == (35, 20)
    assert g.store["possession"] == "visitor" and g.store["ball_spot"] == "RIGHT 25"


# --- routes -------------------------------------------------------------------


class _StubRules:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def play(self, payload):
        self.calls.append(("play", payload))
        return self.result

    def repair_direction(self, event_id, payload):
        self.calls.append(("repair", event_id, payload))
        return self.result


@pytest.fixture
def stub_client(monkeypatch):
    def make(result):
        service = _StubRules(result)
        monkeypatch.setattr(app_module, "RULES_SERVICE", service, raising=False)
        monkeypatch.setattr(app_module, "pin_is_configured", lambda: True)
        monkeypatch.setitem(app_module.app.config, "TESTING", True)
        monkeypatch.setitem(app_module.app.config, "SECRET_KEY", "direction-route-test")
        client = app_module.app.test_client()
        with client.session_transaction() as active_session:
            active_session["authenticated"] = True
        return client, service

    return make


def test_rules_play_route_returns_409_for_a_suspect_direction(stub_client) -> None:
    client, _ = stub_client(RulesResult("DIRECTION_SUSPECT", {"error": "DIRECTION_SUSPECT", "message": "flip?"}))
    response = client.post("/api/rules-play", json={"team": "home", "play_type": "run", "direction_check": True})
    assert response.status_code == 409
    assert response.get_json()["error"] == "DIRECTION_SUSPECT"


@pytest.mark.parametrize(
    "code,status",
    [("OK", 200), ("EVENT_NOT_FOUND", 404), ("INVALID_REPAIR_RANGE", 400), ("EDIT_CONFLICTS_WITH_LATER_EVENTS", 409)],
)
def test_repair_direction_route(stub_client, code, status) -> None:
    client, service = stub_client(RulesResult(code, {"state": {}} if code == "OK" else {}))
    response = client.post("/api/plays/evt-1/repair-direction", json={"last_event_id": "evt-4"})
    assert response.status_code == status
    assert service.calls[0][:2] == ("repair", "evt-1")
    assert service.calls[0][2]["last_event_id"] == "evt-4"
    if code != "OK":
        assert response.get_json()["error"] == code


# --- console wiring -------------------------------------------------------------



def test_console_never_silently_mirrors_at_halftime() -> None:
    assert "Mirror first half (default)" not in INDEX
    assert INDEX.count('<option value="">Ask when the half starts</option><option value="keep">Same ends as 2nd quarter</option><option value="swap">Switch ends</option>') == 2
    # both the halftime toggle and Start Second Half ask when nothing was picked
    assert "await secondHalfDirectionChoice(document.getElementById(dirId)?.value || '')" in INDEX
    assert "await secondHalfDirectionChoice(selected)" in INDEX


def test_console_play_form_asks_for_the_direction_check_and_handles_the_warning() -> None:
    assert "payload.direction_check=true;await submitRulesPlay(payload)" in INDEX
    assert "if(e?.data?.error==='DIRECTION_SUSPECT'){await resolveDirectionSuspect(payload,e.data);return}" in INDEX
    assert "{team:warning.team,direction:flipped,ball:'screen'}" in INDEX
    assert "direction_confirmed:true" in INDEX
    # a warning is not reported as a failed command
    assert "if(data.error!=='DIRECTION_SUSPECT')commandClientStatus(" in INDEX


def test_console_arrow_flip_asks_where_the_ball_is_and_offers_the_repair() -> None:
    assert "Flip the drive arrow — where is the ball?" in INDEX
    assert "payload.ball=choice" in INDEX
    assert 'id="directionChoiceDialog"' in INDEX and 'id="directionRepairDialog"' in INDEX
    assert "/repair-direction`" in INDEX and "onclick=\"openDirectionRepair()\"" in INDEX
