"""Issue 10 from the 10-game simulation (2026-10-30).

* An onside kick recovered by the kicking team stays with the kicking team.
* A blocked (or short) field goal can be returned by the defense, for a
  touchdown too.
* A lateral on a kick return splits the return between the two players.
* A second lateral (hook-and-ladder) splits the yards three ways.
* A school can carry a short abbreviation; a loaded game uses it.
"""
from __future__ import annotations

from pathlib import Path

from school_service import SchoolService
from statistics_service import StatisticsService
from tests.test_gate184_r4_scoring_lifecycle import base_state as fg_state
from tests.test_gate184_r4_scoring_lifecycle import event_service
from tests.test_rules_service import base_state, build_service

HTML = (Path(__file__).resolve().parents[1] / "templates" / "index.html").read_text(encoding="utf-8")


def _stats(current: dict) -> dict:
    return StatisticsService().report(current).data["statistics"]


def _row(report: dict, team: str, number: str) -> dict:
    return next(p for p in report["players"] if p["team"] == team and p["number"] == number)


# ---------------------------------------------------------------- onside kick
def test_an_onside_kick_recovered_by_the_kicking_team_stays_with_it() -> None:
    state = base_state()  # Caledonia (home) drives right
    state.update(ball_spot="LEFT 40", special_game_phase="kickoff", kicking_team="home", receiving_team="visitor")
    service, current, *_ = build_service(state)
    result = service.play({"team": "home", "play_type": "kickoff", "kicker_number": "7",
                           "start_spot": "LEFT 40", "landing_spot": "50", "end_spot": "50",
                           "kicking_team_recovered": True, "kick_recoverer_number": "22"})
    assert result.code == "OK"
    assert (current["possession"], current["ball_spot"], current["down"], current["distance"]) == ("home", "50", "1st", "10")
    assert not current.get("special_game_phase")
    play = current["plays"][-1]
    assert play["kicking_team_recovered"] is True and play["entry"]["kicking_team_recovered"] is True
    assert "recovered by the kicking team (#22 Jordan Runner) at 50" in play["result"]
    report = _stats(current)
    assert report["teams"]["visitor"]["kickoff_returns"] == 0


# ---------------------------------------------------------------- blocked field goal return
def test_a_blocked_field_goal_returned_for_a_touchdown() -> None:
    svc, h = event_service(fg_state())  # home kicks, visitor drives left
    r = svc.trigger({"team": "home", "event": "FG", "source": "statistician", "kick_outcome": "blocked",
                     "kick_result_spot": "LEFT GOAL", "kick_recovery_spot": "RIGHT 40", "kick_returner_number": "24"})
    assert r.ok
    st = h["state"]
    assert (st["visitor_score"], st["home_score"], st["special_game_phase"], st["possession"]) == (6, 0, "pending_try", "visitor")
    event = st["events"][-1]
    assert "blocked, returned 60 yards by #24 for a touchdown" in event["description"]
    assert event["kick_return"]["touchdown"] is True


def test_a_blocked_field_goal_returned_short_of_the_goal() -> None:
    svc, h = event_service(fg_state())
    r = svc.trigger({"team": "home", "event": "FG", "source": "statistician", "kick_outcome": "blocked",
                     "kick_result_spot": "RIGHT 32", "kick_recovery_spot": "RIGHT 25", "kick_returner_number": "24"})
    assert r.ok
    st = h["state"]
    assert (st["possession"], st["ball_spot"], st["visitor_score"]) == ("visitor", "RIGHT 32", 0)
    assert "returned 7 yards by #24 to RIGHT 32" in st["events"][-1]["description"]


# ---------------------------------------------------------------- kick-return lateral
def test_a_lateral_on_a_punt_return_splits_the_return() -> None:
    state = base_state()
    state.update(ball_spot="LEFT 30", down="4th", distance="8")
    service, current, *_ = build_service(state)
    # New Hope (visitor) drives left: RIGHT 20 is its own 20.
    result = service.play({"team": "home", "play_type": "punt", "kicker_number": "7", "returner_number": "4",
                           "start_spot": "LEFT 30", "landing_spot": "RIGHT 20", "end_spot": "RIGHT 45",
                           "lateral": True, "recoverer_number": "55", "recovery_spot": "RIGHT 30"})
    assert result.code == "OK"
    play = current["plays"][-1]
    assert (play["return_yards"], play["recovery_yards"], play["lateral"]) == (25, 15, True)
    assert ", lateral to #55 New Hope Defender at New Hope 30" in play["result"]
    report = _stats(current)
    assert _row(report, "visitor", "4")["punt_return_yards"] == 10
    assert _row(report, "visitor", "55")["punt_return_yards"] == 15
    assert report["teams"]["visitor"]["punt_return_yards"] == 25
    assert report["reconciliation"]["returns_reconciled"] is True


# ---------------------------------------------------------------- second lateral
def test_a_hook_and_ladder_splits_three_ways() -> None:
    service, current, *_ = build_service()  # home at LEFT 20, driving right
    result = service.play({"team": "home", "play_type": "pass", "passer_number": "12", "receiver_number": "7",
                           "pass_outcome": "complete", "start_spot": "LEFT 20", "end_spot": "LEFT 45",
                           "lateral": True, "recoverer_number": "22", "recovery_spot": "LEFT 30",
                           "lateral2_number": "12", "lateral2_spot": "LEFT 40"})
    assert result.code == "OK"
    play = current["plays"][-1]
    assert (play["yards"], play["recovery_yards"], play["lateral2_yards"]) == (25, 10, 5)
    assert ", lateral to #22 Jordan Runner at Caledonia 30, lateral to #12 Jason Quarterback at Caledonia 40" in play["result"]
    report = _stats(current)
    assert _row(report, "home", "7")["receiving_yards"] == 10
    assert _row(report, "home", "22")["receiving_yards"] == 10
    assert _row(report, "home", "12")["receiving_yards"] == 5
    assert report["reconciliation"]["all_reconciled"] is True


# ---------------------------------------------------------------- team abbreviation
def test_school_abbreviations_are_short_and_upper_case() -> None:
    assert SchoolService.normalize_abbreviation(" mtp! ") == "MTP"
    assert SchoolService.normalize_abbreviation("Caledonia") == "CALEDO"


def test_the_console_has_the_new_controls() -> None:
    for needle in (
        'id="playKickRecovered"', "kicking_team_recovered:kickTeamRecovered()", 'id="playKickRecoverer"',
        'id="playLateral2On"', 'id="playLateral2Coord"', "lateral2:['playLateral2Coord','playLateral2SpotLabel','playLateral2Typed']",
        "lateral2_spot:secondLateral()", "function kickLateral()",
        "show('playLateralWrap',['run','pass','kickoff','punt'].includes(kind))",
        'id="automationKickReturner"', 'id="automationKickRecoverySpot"', "payload.kick_returner_number=",
        "function fieldSpotText(value)", 'id="schoolAbbreviation"', "abbreviation: document.getElementById('schoolAbbreviation')",
    ):
        assert needle in HTML, needle
    assert "teamName.split(/\\s+/).map(x=>x[0])" not in HTML
