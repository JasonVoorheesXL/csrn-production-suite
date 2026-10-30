"""Statistician-console usability fixes from the 2026-10-25 simulation (step 7),
plus the step 6 leftovers (fumbled-at spot, half-distance rounding).

* The play register reads like a stat sheet: team yard lines ("Caledonia 30"),
  "1 yard", "no gain", "a loss of 6 yards", the kicker's name.
* Football timeouts: three per half, one per overtime period; a timeout
  stops the clock and is undoable like any other event.
* A rejected event never answers 200 (the console would treat it as saved).
* Half the distance is automatic once a foul is more than half the distance
  to the goal, and the half yard is walked off (11 to go -> 6).
* "Fumbled at" credits a lost fumble's gain to where the ball came loose.
* An optional tackler, credited with tackles and tackles for loss.
"""
from __future__ import annotations

from pathlib import Path

from event_service import EventResult, EventService
from penalty_service import PenaltyService
from rules_service import RulesService
from statistics_service import StatisticsService
from tests.test_event_routes import event_client  # noqa: F401  (pytest fixture)
from tests.test_event_service import base_state as event_base_state
from tests.test_event_service import build_service as build_event_service
from tests.test_rules_service import base_state, build_service

HTML = (Path(__file__).resolve().parents[1] / "templates" / "index.html").read_text(encoding="utf-8")


# ---------------------------------------------------------------- register wording
def test_register_text_uses_team_yard_lines_and_plain_yardage() -> None:
    state = base_state()  # Caledonia (home) drives right: the left half is Caledonia's
    text = RulesService.register_text("run for 1 yards to LEFT 30, returned 1 yards to RIGHT GOAL", state)
    assert text == "run for 1 yard to Caledonia 30, returned 1 yard to New Hope goal line"
    assert RulesService.register_text("run for 0 yards", state) == "run for no gain"
    assert RulesService.register_text("run for -1 yards", state) == "run for a loss of 1 yard"
    assert RulesService.register_text("#7 sacked by #55 for 3 yards", state) == "#7 sacked by #55 for a gain of 3 yards"
    assert RulesService.register_text("run for 11 yards", state) == "run for 11 yards"
    state["home_abbreviation"] = "CAL"
    assert RulesService.team_spot(state, "LEFT 12") == "CAL 12"
    state.update(home_direction="left", visitor_direction="right")
    assert RulesService.team_spot(state, "LEFT 12") == "New Hope 12"


def test_a_recorded_play_reads_like_a_stat_sheet() -> None:
    service, current, *_ = build_service()  # home at LEFT 20
    assert service.play({"team": "home", "play_type": "run", "player_number": "22", "player_name": "Jordan Runner",
                         "start_spot": "LEFT 20", "end_spot": "LEFT 19"}).code == "OK"
    assert current["plays"][-1]["result"] == "#22 Jordan Runner run for a loss of 1 yard"


def test_kicks_name_the_kicker() -> None:
    state = base_state()
    state.update({"down": "4th", "distance": "8", "ball_spot": "LEFT 30"})
    service, current, *_ = build_service(state)
    assert service.play({"team": "home", "play_type": "punt", "kicker_number": "7", "kicker_name": "Caledonia Kicker",
                         "start_spot": "LEFT 30", "landing_spot": "RIGHT 20", "end_spot": "RIGHT 20",
                         "fair_catch": True}).code == "OK"
    assert current["plays"][-1]["result"].startswith("Punt by #7 Caledonia Kicker landed at New Hope 20")


# ---------------------------------------------------------------- timeouts
def _timeout(service, team="home", **extra):
    return service.trigger({"team": team, "event": "TIMEOUT", "source": "broadcaster", **extra})


def test_a_timeout_stops_the_clock_and_counts_down_per_half() -> None:
    state = event_base_state()
    state.update(clock_running=True, clock_started_at=990)
    service, store, *_ = build_event_service(state)
    first = _timeout(service, clock="4:32")
    assert first.code == "OK"
    assert store["clock_running"] is False
    assert store["events"][-1]["event"] == "TIMEOUT"
    assert store["events"][-1]["description"] == "Timeout Home at 4:32 (2 left)"
    assert EventService.timeouts_remaining(store, "home") == 2
    assert EventService.timeouts_remaining(store, "visitor") == 3
    assert _timeout(service).code == "OK" and _timeout(service).code == "OK"
    refused = _timeout(service)
    assert refused.code == "NO_TIMEOUTS_LEFT" and "no timeouts left in this half" in refused.data["message"]
    # A new half brings three more; overtime gets one per period.
    store["quarter"] = "3"
    assert EventService.timeouts_remaining(store, "home") == 3
    store["quarter"] = "OT"
    assert EventService.timeouts_remaining(store, "home") == 1


def test_a_timeout_is_allowed_while_a_try_or_kickoff_is_pending() -> None:
    state = event_base_state()
    state.update(special_game_phase="kickoff", kicking_team="home", receiving_team="visitor")
    service, store, *_ = build_event_service(state)
    assert _timeout(service, team="visitor").code == "OK"
    assert store["special_game_phase"] == "kickoff"


def test_a_rejected_event_is_not_answered_with_200(event_client) -> None:  # noqa: F811
    client, service = event_client
    service.trigger_result = EventResult("NO_TIMEOUTS_LEFT", {"team": "home", "message": "Home has no timeouts left in this half."})
    response = client.post("/api/event-trigger", json={"team": "home", "event": "TIMEOUT"})
    assert response.status_code == 409
    assert response.get_json()["error"] == "NO_TIMEOUTS_LEFT"


# ---------------------------------------------------------------- half the distance
def _enforce(state, **kwargs):
    PenaltyService.enforce(
        state, spot_to_coord=lambda v: int(str(v)), coord_to_spot=lambda c: str(int(c)),
        team_direction=lambda s, team: 1, **kwargs,
    )


def test_half_the_distance_is_automatic_and_walks_off_the_half_yard() -> None:
    # Offense at its own 11 (coord 11), driving right: a 15-yard holding foul.
    state = {"possession": "home", "down": "2nd", "distance": "10", "ball_spot": "11"}
    _enforce(state, selected_team="home", requested_unit="Offensive", name="Holding", yards=10, outcome="accepted")
    assert state["ball_spot"] == "5"  # 11 -> half is 5.5, officials walk off 6
    state = {"possession": "home", "down": "2nd", "distance": "10", "ball_spot": "30"}
    _enforce(state, selected_team="home", requested_unit="Offensive", name="Holding", yards=10, outcome="accepted")
    assert state["ball_spot"] == "20"  # a full 10: not more than half the distance


def test_half_the_distance_never_reaches_the_goal_line() -> None:
    state = {"possession": "home", "down": "1st", "distance": "Goal", "ball_spot": "98"}
    _enforce(state, selected_team="visitor", requested_unit="Defensive", name="Offside", yards=5, outcome="accepted")
    assert state["ball_spot"] == "99"


# ---------------------------------------------------------------- fumbled at / tackler
def test_a_lost_fumble_credits_the_gain_to_where_the_ball_came_loose() -> None:
    service, current, *_ = build_service()  # home at LEFT 20, driving right
    result = service.play({"team": "home", "play_type": "pass", "passer_number": "12", "receiver_number": "22",
                           "pass_outcome": "complete", "fumble": True, "fumble_lost": True,
                           "start_spot": "LEFT 20", "fumble_spot": "RIGHT 37", "turnover_spot": "RIGHT 29",
                           "return_end_spot": "RIGHT 29", "end_spot": "RIGHT 29", "returner_number": "55"})
    assert result.code == "OK"
    play = current["plays"][-1]
    assert play["yards"] == 43 and play["fumble_spot"] == "RIGHT 37"
    assert play["entry"]["fumble_spot"] == "RIGHT 37"


def test_the_tackler_is_recorded_and_credited() -> None:
    service, current, *_ = build_service()
    assert service.play({"team": "home", "play_type": "run", "player_number": "22", "tackler_number": "55",
                         "start_spot": "LEFT 20", "end_spot": "LEFT 17"}).code == "OK"
    play = current["plays"][-1]
    assert (play["tackler_number"], play["tackler_name"]) == ("55", "New Hope Defender")
    assert play["result"].endswith("(tackle #55 New Hope Defender)")
    report = StatisticsService().report(current).data["statistics"]
    row = next(p for p in report["players"] if p["team"] == "visitor" and p["number"] == "55")
    assert (row["tackles"], row["tackles_for_loss"]) == (1, 1)


def test_a_kick_return_tackle_goes_to_the_kicking_team() -> None:
    state = base_state()
    state.update({"down": "4th", "distance": "8", "ball_spot": "LEFT 30"})
    service, current, *_ = build_service(state)
    assert service.play({"team": "home", "play_type": "punt", "kicker_number": "7", "returner_number": "4",
                         "tackler_number": "22", "start_spot": "LEFT 30", "landing_spot": "RIGHT 20",
                         "end_spot": "RIGHT 28"}).code == "OK"
    report = StatisticsService().report(current).data["statistics"]
    row = next(p for p in report["players"] if p["team"] == "home" and p["number"] == "22")
    assert (row["tackles"], row["tackles_for_loss"]) == (1, 0)


# ---------------------------------------------------------------- console markup
def test_console_has_the_new_controls() -> None:
    for needle in (
        'id="statHomeTimeout"', 'id="statVisitorTimeout"', "function callTimeout(team)",
        'id="playStartTyped"', 'id="playEndTyped"', "function parseTypedSpot(", "gainNudge(10)", 'id="playGain"',
        'id="playTackler"', 'id="playEntryClock"', 'id="playFumbleCoord"', "fumble_spot:", "tackler_number:",
        "clock:document.getElementById('playEntryClock')", "function confirmPlayEntryWarnings(",
        'id="confirmFinalButton"', "async function prepareFinalGame()",
        "askTypedConfirm('Delete this game?'", 'class="game-card-more"',
        'list="automationJerseyList"', 'id="coinTossLeftEndName"', "function arrowText(direction){const names=loadEndNames()",
    ):
        assert needle in HTML, needle
    assert '<select id="automationKickerNumber"' not in HTML
    assert "msg.textContent = 'Unable to log in.';" not in HTML


# ---------------------------------------------------------------- laterals (B15)
def test_a_lateral_splits_the_yardage_between_the_two_ball_carriers() -> None:
    service, current, *_ = build_service()  # home at LEFT 20, driving right
    result = service.play({"team": "home", "play_type": "pass", "passer_number": "12", "receiver_number": "7",
                           "pass_outcome": "complete", "lateral": True, "recoverer_number": "22",
                           "recovery_spot": "LEFT 45", "start_spot": "LEFT 20", "end_spot": "RIGHT 40"})
    assert result.code == "OK"
    play = current["plays"][-1]
    assert play["lateral"] is True and play["yards"] == 40 and play["recovery_yards"] == 15
    assert ", lateral to #22 Jordan Runner at Caledonia 45" in play["result"]
    report = StatisticsService().report(current).data["statistics"]
    receiver = next(p for p in report["players"] if p["team"] == "home" and p["number"] == "7")
    trailer = next(p for p in report["players"] if p["team"] == "home" and p["number"] == "22")
    assert receiver["receiving_yards"] == 25 and trailer["receiving_yards"] == 15
    assert trailer["own_fumble_recoveries"] == 0
    assert report["reconciliation"]["all_reconciled"] is True


def test_the_lateral_option_is_in_the_play_form() -> None:
    for needle in ('id="playLateral"', "function playLateral()", "lateral:playLateral()", "'Lateral Spot'"):
        assert needle in HTML, needle
