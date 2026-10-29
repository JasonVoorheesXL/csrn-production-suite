"""Box-score fixes found by the 2026-10-25 three-game simulation (step 6).

* Sacks are rushing plays for the passer and the team (NFHS / MaxPreps), so
  rushing + passing equals total offense.
* A turnover on downs is not a turnover in the box score.
* A kickoff-return touchdown counts as a touchdown (the stray-snap guard was
  throwing out every play recorded during the kickoff phase, kicks included).
* A lost fumble is charged to the player who had the ball, never to the
  defender stored on a defensive-return touchdown; return fumbles count.
* Plays with no player entered go to a TEAM line, so player rows reconcile.
* Penalties: a "new series" option and the missing NFHS fouls.
"""
from __future__ import annotations

from pathlib import Path

from penalty_service import PenaltyService
from statistics_service import StatisticsService
from tests.test_rules_service import base_state, build_service

HTML = (Path(__file__).resolve().parents[1] / "templates" / "index.html").read_text(encoding="utf-8")


def _report(state: dict) -> dict:
    return StatisticsService().report(state).data["statistics"]


def _player(report: dict, team: str, number: str, name: str | None = None) -> dict:
    rows = [p for p in report["players"] if p["team"] == team and p["number"] == number and (name is None or p["name"] == name)]
    assert rows, (team, number, [(p["team"], p["number"], p["name"]) for p in report["players"]])
    return rows[0]


def _team(report: dict, team: str) -> dict:
    return report["teams"][team]


def test_a_sack_is_a_rushing_play_for_the_passer() -> None:
    service, current, *_ = build_service()  # home at LEFT 20, driving right
    assert service.play({"team": "home", "play_type": "run", "player_number": "22", "player_name": "Back",
                         "start_spot": "LEFT 20", "end_spot": "LEFT 30"}).code == "OK"
    assert service.play({"team": "home", "play_type": "pass", "passer_number": "7", "passer_name": "Quarterback",
                         "pass_outcome": "sack", "sacker_number": "90", "start_spot": "LEFT 30",
                         "end_spot": "LEFT 22"}).code == "OK"
    report = _report(current)
    home = _team(report, "home")
    assert (home["rushing_attempts"], home["rushing_yards"]) == (2, 2)
    assert home["pass_attempts"] == 0
    assert home["rushing_yards"] + home["passing_yards"] == home["total_yards"] == 2
    qb = _player(report, "home", "7")
    assert (qb["rushing_attempts"], qb["rushing_yards"], qb["pass_attempts"]) == (1, -8, 0)
    assert _team(report, "visitor")["sacks"] == 1
    assert report["reconciliation"]["all_reconciled"] is True


def test_a_turnover_on_downs_is_not_a_turnover() -> None:
    state = base_state()
    state.update({"down": "4th", "distance": "5", "ball_spot": "LEFT 40"})
    service, current, *_ = build_service(state)
    result = service.play({"team": "home", "play_type": "pass", "passer_number": "7", "pass_outcome": "incomplete",
                           "start_spot": "LEFT 40", "end_spot": "LEFT 40"})
    assert result.code == "OK" and current["possession"] == "visitor"
    assert _team(_report(current), "visitor")["turnovers_gained"] == 0


def test_turnover_button_on_downs_is_not_counted_either() -> None:
    state = base_state()
    state["events"] = [{"id": "e1", "event": "TURNOVER", "team": "visitor", "broadcast_id": state["broadcast_id"],
                        "automation": {"turnover_type": "downs"}},
                       {"id": "e2", "event": "TURNOVER", "team": "visitor", "broadcast_id": state["broadcast_id"],
                        "automation": {"turnover_type": "interception"}}]
    visitor = _team(_report(state), "visitor")
    assert (visitor["turnovers_gained"], visitor["interceptions_gained"]) == (1, 1)


def test_a_kickoff_return_touchdown_counts() -> None:
    state = base_state()
    state.update({"special_game_phase": "kickoff", "kicking_team": "visitor", "possession": "visitor"})
    service, current, *_ = build_service(state)
    result = service.play({"team": "visitor", "play_type": "kickoff", "kicker_number": "11", "start_spot": "RIGHT 40",
                           "landing_spot": "LEFT 4", "end_spot": "RIGHT GOAL", "returner_number": "3",
                           "returner_name": "Novara"})
    assert result.code == "OK" and current["home_score"] == 6
    report = _report(current)
    assert _team(report, "home")["touchdowns"] == 1
    returner = _player(report, "home", "3")
    assert (returner["return_touchdowns"], returner["touchdowns"], returner["kickoff_return_yards"]) == (1, 1, 96)


def test_a_sack_fumble_returned_for_a_touchdown_charges_the_quarterback() -> None:
    # D2 final: Amedt sacked, fumbles, OLSM's Daniel Taylor Jr. returns it 59
    # yards. The lost fumble belongs to the quarterback, not to a phantom
    # "#15 Daniel Taylor Jr." on the offense.
    state = base_state()
    state.update({"ball_spot": "RIGHT 44", "down": "3rd", "distance": "8"})
    service, current, *_ = build_service(state)
    result = service.play({"team": "home", "play_type": "pass", "passer_number": "12", "passer_name": "Amedt",
                           "pass_outcome": "sack", "sacker_number": "23", "fumble_lost": True,
                           "start_spot": "RIGHT 44", "turnover_spot": "RIGHT 41", "returner_number": "15",
                           "returner_name": "Taylor", "end_spot": "LEFT GOAL", "return_end_spot": "LEFT GOAL"})
    assert result.code == "OK" and current["visitor_score"] == 6
    report = _report(current)
    qb = _player(report, "home", "12")
    assert (qb["fumbles"], qb["fumbles_lost"]) == (1, 1)
    assert not [p for p in report["players"] if p["team"] == "home" and p["number"] == "15"]


def test_a_kick_return_fumble_is_charged_to_the_returner() -> None:
    state = base_state()
    state.update({"special_game_phase": "kickoff", "kicking_team": "visitor", "possession": "visitor"})
    service, current, *_ = build_service(state)
    result = service.play({"team": "visitor", "play_type": "kickoff", "kicker_number": "39", "start_spot": "RIGHT 40",
                           "landing_spot": "LEFT 21", "end_spot": "LEFT 28", "returner_number": "13",
                           "returner_name": "Taylor", "fumble": True})
    assert result.code == "OK"
    returner = _player(_report(current), "home", "13")
    assert (returner["fumbles"], returner["fumbles_lost"]) == (1, 0)


def test_plays_with_no_player_go_to_the_team_line_and_reconcile() -> None:
    service, current, *_ = build_service()
    assert service.play({"team": "home", "play_type": "run", "player_number": "22", "start_spot": "LEFT 20",
                         "end_spot": "LEFT 26"}).code == "OK"
    assert service.play({"team": "home", "play_type": "run", "start_spot": "LEFT 26", "end_spot": "LEFT 25",
                         "kneel": True}).code == "OK"
    report = _report(current)
    team_line = _player(report, "home", "", "TEAM")
    assert (team_line["rushing_attempts"], team_line["rushing_yards"]) == (1, -1)
    assert report["reconciliation"]["rushing_reconciled"] is True


def test_new_series_penalty_option_awards_first_and_ten() -> None:
    state = {"possession": "home", "down": "1st", "distance": "10", "ball_spot": "31"}
    PenaltyService.enforce(
        state, selected_team="home", requested_unit="Offensive", name="Personal Foul", yards=15,
        outcome="accepted", spot_to_coord=lambda v: int(str(v)), coord_to_spot=lambda c: str(int(c)),
        team_direction=lambda s, team: 1, new_series=True,
    )
    assert (state["ball_spot"], state["down"], state["distance"]) == ("16", "1st", "10")


def test_nfhs_fouls_are_in_the_catalog() -> None:
    rules = PenaltyService.RULES
    for key in [("Defensive", "Illegal Use of Hands"), ("Defensive", "Illegal Participation"),
                ("Offensive", "Pass Interference"), ("Special Teams", "Offside"),
                ("Special Teams", "Roughing the Snapper"), ("Offensive", "Illegal Forward Pass")]:
        assert key in rules, key
    assert rules[("Special Teams", "Roughing the Snapper")]["automatic_first_down"] is True
    assert rules[("Offensive", "Illegal Forward Pass")]["loss_of_down"] is True
    assert "['Illegal Use of Hands',10]" in HTML and "['Sideline Interference',5]" in HTML
    assert 'id="penaltyNewSeries"' in HTML and "penalty_new_series:" in HTML
