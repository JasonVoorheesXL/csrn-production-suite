from __future__ import annotations

from typing import Any

from statistics_service import StatisticsService


def base_state() -> dict[str, Any]:
    return {
        "broadcast_id": "FB-2026-01",
        "sport": "Football",
        "season": "2026",
        "date": "2026-08-21",
        "venue": "Cavalier Stadium",
        "quarter": "2",
        "status": "live",
        "home_team": "Caledonia",
        "visitor_team": "New Hope",
        "home_score": 14,
        "visitor_score": 7,
        "events": [],
        "plays": [],
    }


def service() -> StatisticsService:
    return StatisticsService(now=lambda: 1_700_000_000.9)


def report(state: dict[str, Any]) -> dict[str, Any]:
    result = service().report(state)
    assert result.ok
    return result.data["statistics"]


def test_canonical_team_helpers_accept_names_and_away_alias() -> None:
    state = base_state()
    assert StatisticsService.canonical_team_key(state, "Caledonia") == "home"
    assert StatisticsService.canonical_team_key(state, "away") == "visitor"
    assert StatisticsService.canonical_team_name(state, "home") == "Caledonia"
    assert StatisticsService.canonical_team_name(state, "New Hope") == "New Hope"


def test_empty_report_preserves_metadata_and_score() -> None:
    result = report(base_state())
    assert result["broadcast_id"] == "FB-2026-01"
    assert result["sport"] == "Football"
    assert result["teams"]["home"]["score"] == 14
    assert result["teams"]["visitor"]["score"] == 7
    assert result["event_count"] == 0
    assert result["play_count"] == 0
    assert result["generated_at"] == 1_700_000_000


def test_report_filters_undone_and_other_broadcast_rows() -> None:
    state = base_state()
    state["events"] = [
        {"id": "keep", "broadcast_id": "FB-2026-01", "event": "TD", "team": "home", "score_delta": 6},
        {"id": "undone", "broadcast_id": "FB-2026-01", "event": "TD", "team": "home", "score_delta": 6, "undone": True},
        {"id": "other", "broadcast_id": "FB-2026-02", "event": "TD", "team": "home", "score_delta": 6},
    ]
    state["plays"] = [
        {"play_id": "keep", "broadcast_id": "FB-2026-01", "play_type": "run", "offense": "home", "yards": 4},
        {"play_id": "other", "broadcast_id": "FB-2026-02", "play_type": "run", "offense": "home", "yards": 10},
    ]
    result = report(state)
    assert result["event_count"] == 1
    assert result["play_count"] == 1
    assert result["teams"]["home"]["touchdowns"] == 1
    assert result["teams"]["home"]["total_yards"] == 4


def test_manual_touchdown_builds_team_player_and_scoring_summary() -> None:
    state = base_state()
    state["events"] = [
        {
            "id": "E1",
            "broadcast_id": "FB-2026-01",
            "event": "TD",
            "team": "home",
            "label": "Touchdown",
            "description": "Jordan Runner scores",
            "score_delta": 6,
            "quarter": "1",
            "created_at": 100,
            "automation": {"player_number": "22", "player_name": "Jordan Runner"},
            "after": {"home_score": 6, "visitor_score": 0},
        }
    ]
    result = report(state)
    assert result["teams"]["home"]["touchdowns"] == 1
    assert result["players"][0]["touchdowns"] == 1
    assert result["players"][0]["points"] == 6
    assert result["scoring_summary"][0]["home_score"] == 6


def test_rules_engine_play_event_counts_touchdown() -> None:
    state = base_state()
    state["events"] = [
        {
            "id": "E1",
            "play_id": "P1",
            "event": "PLAY",
            "team": "home",
            "score_delta": 6,
            "automation": {"touchdown": True, "player_number": "22", "player_name": "Jordan Runner"},
            "after": {"home_score": 6, "visitor_score": 0},
        }
    ]
    state["plays"] = [
        {"play_id": "P1", "event_id": "E1", "play_type": "run", "offense": "home", "defense": "visitor", "yards": 30, "touchdown": True, "player_number": "22", "player_name": "Jordan Runner"}
    ]
    result = report(state)
    assert result["teams"]["home"]["touchdowns"] == 1
    player = next(row for row in result["players"] if row["number"] == "22")
    assert player["touchdowns"] == 1
    assert result["scoring_event_count"] == 1


def test_field_goal_extra_point_and_two_point_totals() -> None:
    state = base_state()
    state["events"] = [
        {"event": "FG", "team": "home", "score_delta": 3, "automation": {"player_number": "7", "player_name": "Kicker"}},
        {"event": "XP", "team": "home", "score_delta": 1, "automation": {"player_number": "7", "player_name": "Kicker"}},
        {"event": "2PT", "team": "visitor", "score_delta": 2, "automation": {"player_number": "4", "player_name": "Runner"}},
    ]
    result = report(state)
    assert result["teams"]["home"]["field_goals"] == 1
    assert result["teams"]["home"]["extra_points"] == 1
    assert result["teams"]["visitor"]["two_point_conversions"] == 1
    kicker = next(row for row in result["players"] if row["number"] == "7")
    assert kicker["points"] == 4


def test_run_play_accumulates_team_and_player_yardage() -> None:
    state = base_state()
    state["plays"] = [
        {"play_id": "P1", "play_type": "run", "offense": "Caledonia", "defense": "New Hope", "yards": 12, "player_number": "22", "player_name": "Jordan Runner"}
    ]
    result = report(state)
    team = result["teams"]["home"]
    assert team["rushing_attempts"] == 1
    assert team["rushing_yards"] == 12
    assert team["total_plays"] == 1
    assert result["players"][0]["rushing_yards"] == 12


def test_complete_pass_accumulates_passing_and_receiving_stats() -> None:
    state = base_state()
    state["plays"] = [
        {"play_id": "P1", "play_type": "pass", "pass_outcome": "complete", "offense": "home", "defense": "visitor", "yards": 18, "passer_number": "12", "passer_name": "Jason Quarterback", "player_number": "22", "player_name": "Jordan Receiver"}
    ]
    result = report(state)
    team = result["teams"]["home"]
    assert team["pass_attempts"] == 1
    assert team["completions"] == 1
    assert team["passing_yards"] == 18
    passer = next(row for row in result["players"] if row["number"] == "12")
    receiver = next(row for row in result["players"] if row["number"] == "22")
    assert passer["passing_yards"] == 18
    assert receiver["receptions"] == 1
    assert receiver["receiving_yards"] == 18


def test_pass_touchdown_tracks_passing_touchdown_without_double_counting_team_td() -> None:
    state = base_state()
    state["events"] = [
        {"id": "E1", "play_id": "P1", "event": "PLAY", "team": "home", "score_delta": 6, "automation": {"touchdown": True, "player_number": "22", "player_name": "Jordan Receiver"}}
    ]
    state["plays"] = [
        {"play_id": "P1", "event_id": "E1", "play_type": "pass", "pass_outcome": "complete", "offense": "home", "defense": "visitor", "yards": 25, "touchdown": True, "passer_number": "12", "passer_name": "Jason Quarterback", "player_number": "22", "player_name": "Jordan Receiver"}
    ]
    result = report(state)
    assert result["teams"]["home"]["touchdowns"] == 1
    passer = next(row for row in result["players"] if row["number"] == "12")
    assert passer["passing_touchdowns"] == 1


def test_interception_outcome_can_be_recovered_from_linked_event() -> None:
    state = base_state()
    state["events"] = [
        {"id": "E1", "event": "PLAY", "team": "home", "automation": {"pass_outcome": "interception", "turnover": True}}
    ]
    state["plays"] = [
        {"play_id": "P1", "event_id": "E1", "play_type": "pass", "offense": "home", "defense": "visitor", "yards": 0, "turnover": True, "passer_number": "12", "passer_name": "Jason Quarterback"}
    ]
    result = report(state)
    assert result["teams"]["home"]["interceptions"] == 1
    assert result["teams"]["visitor"]["turnovers_gained"] == 1
    passer = next(row for row in result["players"] if row["number"] == "12")
    assert passer["interceptions_thrown"] == 1


def test_fumble_and_fumble_lost_are_tracked_for_ball_carrier() -> None:
    state = base_state()
    state["plays"] = [
        {"play_id": "P1", "play_type": "run", "offense": "home", "defense": "visitor", "yards": 3, "fumble": True, "fumble_lost": True, "turnover": True, "player_number": "22", "player_name": "Jordan Runner"}
    ]
    result = report(state)
    player = result["players"][0]
    assert player["fumbles"] == 1
    assert player["fumbles_lost"] == 1
    assert result["teams"]["visitor"]["turnovers_gained"] == 1


def test_manual_turnover_event_counts_defensive_gain_once() -> None:
    state = base_state()
    state["events"] = [
        {"id": "E1", "event": "TURNOVER", "team": "visitor", "score_delta": 0}
    ]
    state["plays"] = [
        {"play_id": "P1", "event_id": "E1", "play_type": "pass", "offense": "home", "defense": "visitor", "yards": 0, "turnover": True}
    ]
    result = report(state)
    assert result["teams"]["visitor"]["turnovers_gained"] == 1


def test_yards_per_play_is_rounded_and_zero_safe() -> None:
    state = base_state()
    state["plays"] = [
        {"play_id": "P1", "play_type": "run", "offense": "home", "yards": 4},
        {"play_id": "P2", "play_type": "run", "offense": "home", "yards": 5},
    ]
    result = report(state)
    assert result["teams"]["home"]["yards_per_play"] == 4.5
    assert result["teams"]["visitor"]["yards_per_play"] == 0


def test_play_register_normalizes_team_keys_and_names_without_mutating_source() -> None:
    state = base_state()
    play = {"play_id": "P1", "play_type": "run", "offense": "Caledonia", "defense": "New Hope", "yards": 1}
    state["plays"] = [play]
    result = report(state)
    normalized = result["play_register"][0]
    assert normalized["offense"] == "home"
    assert normalized["defense"] == "visitor"
    assert normalized["offense_name"] == "Caledonia"
    assert normalized["defense_name"] == "New Hope"
    assert play["offense"] == "Caledonia"


def test_players_sort_by_team_then_numeric_jersey_then_name() -> None:
    state = base_state()
    state["plays"] = [
        {"play_type": "run", "offense": "home", "yards": 1, "player_number": "22", "player_name": "B"},
        {"play_type": "run", "offense": "home", "yards": 1, "player_number": "3", "player_name": "A"},
        {"play_type": "run", "offense": "visitor", "yards": 1, "player_number": "1", "player_name": "C"},
    ]
    result = report(state)
    assert [(row["team"], row["number"]) for row in result["players"]] == [
        ("home", "3"),
        ("home", "22"),
        ("visitor", "1"),
    ]


def test_touchdown_play_without_event_still_counts_team_and_player() -> None:
    state = base_state()
    state["plays"] = [
        {"play_id": "P1", "play_type": "run", "offense": "home", "defense": "visitor", "yards": 80, "touchdown": True, "player_number": "22", "player_name": "Jordan Runner"}
    ]
    result = report(state)
    assert result["teams"]["home"]["touchdowns"] == 1
    assert result["players"][0]["touchdowns"] == 1


