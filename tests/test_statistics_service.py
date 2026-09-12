"""Coverage for StatisticsService.report().

Two layers live in this file:

* The broad unit coverage (team/player accumulation, scoring totals,
  turnover tracking, play-register normalisation, sort order) that has
  guarded report() since it was written -- the ``base_state`` / ``service``
  / ``report`` helpers below.
* A regression suite for the 2026-09 Caledonia vs. Amory incident, in
  which Caledonia's report showed 5 touchdowns for a 27-7 final where only
  4 were legitimate. The 5th was a phantom scrimmage play ("Touchdown Run")
  recorded while the game was still in "pending_try" from a real touchdown
  the play before -- the ball was parked dead on the goal line, so the
  client-submitted ``automation.touchdown`` flag (and, before the
  canonical_state_service.py fix, the derived ``play["touchdown"]`` flag
  too) both said touchdown even though the score was never actually
  incremented for it. See tests/test_canonical_state_service.py for the
  canonical-engine half of this same incident.

report() trusts events/plays as given -- it does not call rebuild() -- so
the incident tests pin the report-layer defence
(``_recorded_during_special_phase``) independently: report() must ignore a
touchdown flag on any event/play whose own recorded ``before`` snapshot
shows a special phase already active, regardless of whether the canonical
layer has since been fixed or rebuilt.
"""
from __future__ import annotations

import json
from typing import Any

import ruleset_service
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


# --------------------------------------------------------------------------
# 2026-09 Caledonia vs. Amory phantom-touchdown incident (report-layer half)
#
# These use StatisticsService().report() directly rather than the
# module-level report() helper above -- both idioms are fine, they exercise
# the same entry point. See the module docstring and
# tests/test_canonical_state_service.py for the full incident write-up.
# --------------------------------------------------------------------------


def _incident_base_state(**overrides) -> dict:
    state = {
        "home_team": "Caledonia",
        "visitor_team": "Amory",
        "home_score": 14,
        "visitor_score": 7,
        "broadcast_id": "",
    }
    state.update(overrides)
    return state


def caledonia_incident_state() -> dict:
    # Trimmed reconstruction of the real play 49 (legitimate TD) -> 50
    # (phantom TD, recorded during pending_try) -> 51 (XP) sequence.
    events = [
        {
            "id": "evt-49",
            "play_id": "play-49",
            "play_number": 49,
            "event": "PLAY",
            "team": "home",
            "before": {"special_game_phase": ""},
            "automation": {"touchdown": False, "play_type": "run"},
        },
        {
            "id": "evt-50",
            "play_id": "play-50",
            "play_number": 50,
            "event": "PLAY",
            "team": "home",
            # The ball was already parked on the goal line from play 49's
            # real touchdown -- this is the smoking gun a legitimate new
            # scrimmage snap could never show.
            "before": {"special_game_phase": "pending_try"},
            "automation": {"touchdown": True, "play_type": "run"},
        },
        {
            "id": "evt-51",
            "play_id": "play-51",
            "play_number": 51,
            "event": "XP",
            "team": "home",
            "before": {"special_game_phase": "pending_try"},
            "score_delta": 1,
            "conversion_outcome": "good",
            "automation": {},
        },
    ]
    plays = [
        {
            "play_id": "play-49",
            "event_id": "evt-49",
            "play_type": "run",
            "yards": 5,
            "offense": "home",
            "defense": "visitor",
            "player_name": "Tyler Long",
            "player_number": "10",
            "touchdown": True,
        },
        {
            "play_id": "play-50",
            "event_id": "evt-50",
            "play_type": "run",
            "yards": 12,
            "offense": "home",
            "defense": "visitor",
            "player_name": "Caleb Lang",
            "player_number": "1",
            # Even if this stray flag were never cleaned up by a rebuild,
            # the report layer must not trust it either.
            "touchdown": True,
        },
    ]
    return _incident_base_state(events=events, plays=plays)


def test_report_does_not_count_a_touchdown_recorded_during_a_pending_try() -> None:
    service = StatisticsService()
    result = service.report(caledonia_incident_state())
    home = result.data["statistics"]["teams"]["home"]
    assert home["touchdowns"] == 1


def test_report_does_not_credit_the_phantom_players_touchdown() -> None:
    service = StatisticsService()
    result = service.report(caledonia_incident_state())
    players_by_name = {p["name"]: p for p in result.data["statistics"]["players"]}
    assert players_by_name["Tyler Long"]["rushing_touchdowns"] == 1
    assert players_by_name["Tyler Long"]["touchdowns"] == 1
    assert players_by_name["Caleb Lang"]["rushing_touchdowns"] == 0
    assert players_by_name["Caleb Lang"]["touchdowns"] == 0


def test_report_still_counts_a_legitimate_touchdown_outside_any_special_phase() -> None:
    # Sanity check: a normal touchdown (no special phase pending beforehand)
    # must still be counted -- this fix must not suppress real scoring.
    events = [
        {
            "id": "evt-1",
            "play_id": "play-1",
            "event": "PLAY",
            "team": "home",
            "before": {"special_game_phase": ""},
            "automation": {"touchdown": True, "play_type": "run"},
        },
    ]
    plays = [
        {
            "play_id": "play-1",
            "event_id": "evt-1",
            "play_type": "run",
            "yards": 5,
            "offense": "home",
            "defense": "visitor",
            "player_name": "Tyler Long",
            "player_number": "10",
            "touchdown": True,
        },
    ]
    service = StatisticsService()
    result = service.report(_incident_base_state(events=events, plays=plays))
    assert result.data["statistics"]["teams"]["home"]["touchdowns"] == 1
    players_by_name = {p["name"]: p for p in result.data["statistics"]["players"]}
    assert players_by_name["Tyler Long"]["rushing_touchdowns"] == 1


# --------------------------------------------------------------------------
# Round 26 (Phase A 4/7): the single (rouge) and a PAT are both +1-point
# events, so the report layer must classify them by EVENT CODE, never by
# the delta. This proves the disambiguation now -- against a test-only
# Canadian-shaped ruleset -- before the real ca-base.json exists (7/7).
# --------------------------------------------------------------------------


def _write_test_ca_ruleset(tmp_path) -> str:
    football = tmp_path / "football"
    football.mkdir()
    (football / "test-ca.json").write_text(
        json.dumps(
            {
                "id": "football/test-ca",
                "sport": "football",
                "period": {"downs_per_set": 3},
                "field": {"no_fair_catch": True, "field_goal_play": True},
                "scoring": {"single": 1},
            }
        ),
        encoding="utf-8",
    )
    return "football/test-ca"


def test_single_and_pat_in_the_same_game_are_never_cross_attributed(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("CSRN_RULESETS_DIR", str(tmp_path))
    ruleset_service.clear_cache()
    try:
        ca = ruleset_service.load_ruleset(_write_test_ca_ruleset(tmp_path))
        # The fixture really does enable the Canadian shape.
        assert ruleset_service.no_fair_catch(ca) is True
        assert ruleset_service.scoring_values(ca)["single"] == 1
        assert "field_goal" in ruleset_service.valid_play_types(ca)

        # One game, one kicker (#9). He kicks the PAT after a TD (an "XP"
        # event, recorded during pending_try) AND, on a later drive, a rouge
        # (a "SINGLE" event, in open play). Both deltas are +1.
        state = _incident_base_state(
            home_score=8,
            visitor_score=0,
            events=[
                {
                    "id": "e-td",
                    "event": "TD",
                    "team": "home",
                    "score_delta": 6,
                    "before": {"special_game_phase": ""},
                    "automation": {"player_number": "20", "player_name": "RB One"},
                },
                {
                    "id": "e-xp",
                    "event": "XP",
                    "team": "home",
                    "score_delta": 1,
                    "conversion_outcome": "good",
                    "before": {"special_game_phase": "pending_try"},
                    "automation": {"player_number": "9", "player_name": "K Nine"},
                },
                {
                    "id": "e-single",
                    "event": "SINGLE",
                    "team": "home",
                    "score_delta": 1,
                    "before": {"special_game_phase": ""},
                    "automation": {"player_number": "9", "player_name": "K Nine"},
                },
            ],
        )
        result = StatisticsService().report(state)
        home = result.data["statistics"]["teams"]["home"]

        # The PAT is a PAT and only a PAT.
        assert home["extra_points"] == 1
        assert home["extra_point_attempts"] == 1  # the SINGLE added no attempt
        # The single is a single and only a single.
        assert home["singles"] == 1
        assert home["two_point_conversions"] == 0
        assert home["field_goals"] == 0
        assert home["field_goal_attempts"] == 0

        players = {p["name"]: p for p in result.data["statistics"]["players"]}
        assert players["K Nine"]["extra_points"] == 1
        assert players["K Nine"]["extra_point_attempts"] == 1
        assert players["K Nine"]["singles"] == 1
        assert players["K Nine"]["points"] == 2  # 1 (PAT) + 1 (rouge)
    finally:
        ruleset_service.clear_cache()


def test_a_single_is_not_counted_as_a_pat_even_with_no_conversion_context() -> None:
    # A bare SINGLE event with a +1 delta and no pending_try / conversion
    # fields at all must still never touch the extra-point tallies.
    state = _incident_base_state(
        home_score=1,
        visitor_score=0,
        events=[
            {
                "id": "e-single",
                "event": "SINGLE",
                "team": "home",
                "score_delta": 1,
                "automation": {"player_number": "12", "player_name": "P Twelve"},
            }
        ],
    )
    result = StatisticsService().report(state)
    home = result.data["statistics"]["teams"]["home"]
    assert home["singles"] == 1
    assert home["extra_points"] == 0
    assert home["extra_point_attempts"] == 0
    players = {p["name"]: p for p in result.data["statistics"]["players"]}
    assert players["P Twelve"]["singles"] == 1
    assert players["P Twelve"]["extra_points"] == 0
    assert players["P Twelve"]["points"] == 1
