"""What the basketball board shows beyond the score. The overlay itself is driven in
a throwaway app; these pin the rules the owner set: both teams treated alike, facts
only, foul trouble automatic, the big screens only on request."""

from __future__ import annotations

from pathlib import Path

import pytest

from hoops_box_score_service import HoopsBoxScoreService
from hoops_broadcast_panel import attacks_right, build_broadcast, screen_spot
from hoops_event_service import HoopsEventService
from hoops_overlay_panel import build_panel, roster_lookup
from hoops_period_service import HoopsPeriodService
from hoops_rules_service import HoopsRulesService as Rules

ROOT = Path(__file__).resolve().parents[1]
NAMES = {
    "home": {f"h{i}": {"name": f"Home Player{i}", "last": f"Player{i}", "number": str(i)} for i in range(1, 9)},
    "visitor": {f"v{i}": {"name": f"Road Guy{i}", "last": f"Guy{i}", "number": str(i)} for i in range(1, 9)},
}


def game(period: str = "1") -> dict:
    state = {"sport": "basketball", "ruleset_id": "basketball/us-ms-mhsaa", "hoops": {}, "home_team": "Riverside", "visitor_team": "Northgate"}
    HoopsPeriodService.start_game(state, Rules.active_ruleset(state))
    state["period"] = period
    return state


def panel(state) -> dict:
    return build_broadcast(state, HoopsBoxScoreService._rebuilt_events(state), NAMES)


def shot(state, team="home", shooter="h1", made=True, points=2, x=70.0, y=25.0, **extra):
    return Rules.shot(state, {"team": team, "made": made, "points": points, "shooterId": shooter, "spotX": x, "spotY": y, **extra}).data["event"]


def test_ends_switch_at_halftime_and_stay_through_overtime() -> None:
    assert attacks_right(game("1"), "home") and attacks_right(game("2"), "home")
    assert not attacks_right(game("3"), "home") and not attacks_right(game("4"), "home") and not attacks_right(game("OT"), "home")
    assert not attacks_right(game("1"), "visitor") and attacks_right(game("3"), "visitor")


def test_a_shot_is_marked_at_the_end_its_team_attacks() -> None:
    state = game()
    assert screen_spot(state, "home", 70, 30) == {"x": 70, "y": 30}
    assert screen_spot(state, "visitor", 70, 30) == {"x": 14, "y": 20}
    Rules.set_direction(state, {"homeFirstHalfAttacks": "left"})
    assert screen_spot(state, "home", 70, 30) == {"x": 14, "y": 20}


def test_marker_shows_made_miss_and_shot_type() -> None:
    state = game()
    shot(state, points=3, x=62, y=40)
    marker = panel(state)["marker"]
    assert marker["kind"] == "made" and marker["text"] == "#1 Player1 · 3 PT · Right wing" and marker["x"] == 62
    shot(state, shooter="h2", x=77, y=26, shotType="Dunk")
    assert panel(state)["marker"]["text"] == "#2 Player2 · DUNK · At the rim"
    shot(state, team="visitor", shooter="v1", made=False, x=70, y=25)
    marker = panel(state)["marker"]
    assert marker["kind"] == "miss" and "Missed 2" in marker["text"] and marker["x"] == 14


@pytest.mark.parametrize("stays", [
    lambda s: Rules.rebound(s, {"team": "home", "kind": "defensive"}),
    lambda s: Rules.free_throw(s, {"team": "home", "made": True}),
    lambda s: Rules.foul(s, {"team": "home", "foulType": "personal"}),
])
def test_marker_stays_through_the_rest_of_the_play(stays) -> None:
    state = game()
    shot(state)
    stays(state)
    assert panel(state)["marker"]["kind"] == "made"


@pytest.mark.parametrize("clears", [
    lambda s: Rules.timeout(s, {"team": "home"}),
    lambda s: Rules.turnover(s, {"team": "home", "stealPlayerId": "v1"}),
    lambda s: Rules.turnover(s, {"team": "home"}),
    lambda s: Rules.violation(s, {"team": "home", "violationType": "traveling", "possessionTo": "visitor"}),
    lambda s: Rules.end_period(s),
])
def test_marker_clears_on_a_change_of_play(clears) -> None:
    state = game()
    shot(state)
    clears(state)
    assert panel(state)["marker"] is None


def test_shot_with_no_spot_shows_no_marker() -> None:
    state = game()
    Rules.shot(state, {"team": "home", "made": True, "points": 2})
    assert panel(state)["marker"] is None


def test_marked_steal_and_fouled_shot() -> None:
    state = game()
    event = Rules.turnover(state, {"team": "visitor", "stealPlayerId": "h2"}).data["event"]
    Rules.play_note(state, {"targetEventId": event["event_id"], "spotX": 50, "spotY": 18})
    marker = panel(state)["marker"]
    assert marker["kind"] == "steal" and marker["text"] == "#2 Player2" and marker["x"] == 50
    Rules.foul(state, {"team": "visitor", "playerId": "v3", "foulType": "shooting", "drewFoulOn": "h1", "spotX": 62, "spotY": 40})
    marker = panel(state)["marker"]
    assert marker["kind"] == "fouled" and "Player1" in marker["text"] and marker["x"] == 62


def test_runs_count_only_since_the_other_team_scored() -> None:
    state = game()
    shot(state, team="visitor", shooter="v1")
    shot(state, points=3)
    assert panel(state)["run"] is None
    shot(state)
    assert panel(state)["run"] == {"team": "home", "points": 5}
    shot(state, team="visitor", shooter="v1")
    assert panel(state)["run"] is None


def test_on_floor_has_points_and_fouls_for_both_teams() -> None:
    state = game()
    for side, prefix in (("home", "h"), ("visitor", "v")):
        state["hoops"][f"{side}_on_floor"] = [f"{prefix}{i}" for i in range(1, 6)]
    shot(state, shooter="h1")
    Rules.foul(state, {"team": "visitor", "playerId": "v2", "foulType": "personal"})
    floor = panel(state)["on_floor"]
    assert floor["home"][0] == {"number": "1", "last": "Player1", "pts": 2, "fouls": 0}
    assert floor["visitor"][1]["fouls"] == 1 and len(floor["visitor"]) == 5


def test_hot_hand_needs_three_makes_and_reports_facts() -> None:
    state = game()
    shot(state, x=62, y=40, points=3)
    shot(state, x=60, y=12, points=3)
    assert panel(state)["hot_hand"]["home"] is None
    shot(state, x=58, y=25, points=3)
    hot = panel(state)["hot_hand"]["home"]
    assert hot["title"] == "#1 Player1" and hot["line"] == "9 pts · 3 of 3 from three" and len(hot["shots"]) == 3
    assert panel(state)["hot_hand"]["visitor"] is None


def test_notes_are_facts_about_both_teams_and_never_call_out_a_miss() -> None:
    state = game()
    for _ in range(4):
        shot(state, team="visitor", shooter="v1", points=3, x=62, y=40)
    shot(state, shooter="h1", made=False, points=3, x=62, y=40)
    notes = panel(state)["notes"]
    assert "NORTHGATE ON A 12-0 RUN" in notes and "#1 GUY1 4 OF 4 FROM THREE" in notes and "#1 GUY1 LEADS ALL SCORERS WITH 12" in notes
    assert not any("PLAYER1" in note or "MISS" in note or "COLD" in note for note in notes)
    # A bad shooting night never becomes a note, however long it runs.
    state = game()
    for _ in range(8):
        shot(state, shooter="h1", made=False, points=3, x=62, y=40)
    assert not any("PLAYER1" in note for note in panel(state)["notes"])


def test_bonus_and_team_drought_notes() -> None:
    state = game()
    for _ in range(4):
        Rules.foul(state, {"team": "visitor", "foulType": "personal"})
    assert "RIVERSIDE IN THE BONUS ON THE NEXT FOUL" in panel(state)["notes"]
    Rules.foul(state, {"team": "visitor", "foulType": "personal"})
    assert "RIVERSIDE IN THE BONUS" in panel(state)["notes"]
    state = game()
    shot(state, clockSeconds=400, period="1")
    shot(state, team="visitor", shooter="v1", clockSeconds=200, period="1")
    assert "RIVERSIDE NO FIELD GOAL SINCE 6:40" in panel(state)["notes"]


def test_foul_trouble_starts_at_four_and_says_when_fouled_out() -> None:
    state = game()
    for _ in range(3):
        Rules.foul(state, {"team": "visitor", "playerId": "v3", "foulType": "personal"})
    assert panel(state)["alert"] is None
    Rules.foul(state, {"team": "visitor", "playerId": "v3", "foulType": "personal"})
    alert = panel(state)["alert"]
    assert alert["tag"] == "4 FOULS" and alert["tag2"] == "FOUL TROUBLE" and alert["name"] == "Road Guy3" and not alert["muted"]
    first = alert["sequence"]
    Rules.foul(state, {"team": "visitor", "playerId": "v3", "foulType": "personal"})
    alert = panel(state)["alert"]
    assert alert["tag"] == "FOULED OUT" and alert["sequence"] > first


def test_alerts_off_is_muted_and_does_not_affect_the_game() -> None:
    state = game()
    Rules.set_display(state, {"alerts": False})
    for _ in range(4):
        Rules.foul(state, {"team": "visitor", "playerId": "v3", "foulType": "personal"})
    assert panel(state)["alert"]["muted"]
    Rules.set_display(state, {"alerts": True})
    assert not panel(state)["alert"]["muted"]


def test_screens_only_when_asked_and_undo_leaves_them() -> None:
    state = game()
    shot(state, points=3, x=62, y=40)
    shot(state, team="visitor", shooter="v1", x=70, y=25, made=False)
    assert panel(state)["screen"] is None
    Rules.set_display(state, {"screen": "shot_chart", "team": "home"})
    screen = panel(state)["screen"]
    assert screen["title"] == "RIVERSIDE SHOT CHART" and len(screen["shots"]) == 1
    assert {z["label"]: z["line"] for z in screen["zones"]}["Above the arc"] == "1 of 1"
    HoopsEventService.undo(state)
    assert panel(state)["screen"] is not None
    Rules.set_display(state, {"screen": "shot_chart", "team": "home", "player": "h1"})
    assert panel(state)["screen"]["title"] == "#1 PLAYER1 SHOT CHART"
    Rules.set_display(state, {"screen": ""})
    assert panel(state)["screen"] is None
    with pytest.raises(ValueError):
        Rules.set_display(state, {"screen": "shot_chart"})
    with pytest.raises(ValueError):
        Rules.set_display(state, {"screen": "bogus"})


def test_comparison_numbers() -> None:
    state = game()
    shot(state, x=70, y=25, points=2)  # paint
    Rules.rebound(state, {"team": "visitor", "kind": "defensive"})
    shot(state, team="visitor", shooter="v1", made=False, x=70, y=25)
    Rules.rebound(state, {"team": "visitor", "kind": "offensive"})
    first = shot(state, team="visitor", shooter="v1", points=3, x=62, y=40)
    Rules.play_note(state, {"targetEventId": first["event_id"], "tags": ["off_turnover"]})
    Rules.set_display(state, {"screen": "comparison"})
    screen = panel(state)["screen"]
    rows = {row["label"]: row for row in screen["rows"]}
    assert screen["left"] == "NORTHGATE" and screen["right"] == "RIVERSIDE"
    assert rows["Field goals"]["left"] == "50%" and rows["Field goals"]["right"] == "100%"
    assert rows["Three-pointers"]["left"] == "1 of 1" and rows["Points in paint"]["right"] == "2"
    assert rows["Second-chance"]["left"] == "3" and rows["Off turnovers"]["left"] == "3"
    assert screen["leaders"]["left"]["pts"] == 3


def test_panel_feed_carries_it_and_a_note_assist_counts_for_the_leader() -> None:
    state = game()
    event = shot(state, shooter="h1")
    Rules.play_note(state, {"targetEventId": event["event_id"], "assistId": "h2"})
    built = build_panel(state, NAMES)
    assert built["broadcast"]["marker"]["kind"] == "made"
    assert "broadcast" in built


def test_roster_lookup_uses_the_games_boys_or_girls_roster() -> None:
    rosters = [
        {"school_id": "s", "sport": "Basketball", "division": "Boys", "players": [{"id": "b1", "first_name": "Bo", "last_name": "Yes", "number": "1"}]},
        {"school_id": "s", "sport": "Basketball", "division": "Girls", "players": [{"id": "g1", "first_name": "Gi", "last_name": "Yes", "number": "1"}]},
    ]
    assert list(roster_lookup(rosters, {"home_school_id": "s", "division": "Girls"})["home"]) == ["g1"]
    assert list(roster_lookup(rosters, {"home_school_id": "s", "division": "Boys"})["home"]) == ["b1"]
    assert set(roster_lookup(rosters, {"home_school_id": "s"})["home"]) == {"b1", "g1"}


def test_layer_stays_off_other_sports() -> None:
    js = (ROOT / "static/csrn-hoops-broadcast.js").read_text(encoding="utf-8")
    css = (ROOT / "static/csrn-hoops-broadcast.css").read_text(encoding="utf-8")
    assert '.bl-collegiate-tech.bl-sport-basketball' in js and "if (!board)" in js
    for rule in css.split("}"):
        selector = rule.split("{")[0].strip()
        if selector and not selector.startswith("/*"):
            for part in selector.split(","):
                part = part.strip().split("*/")[-1].strip()
                assert ".hb-" in part or ".bl-sport-basketball" in part, part
