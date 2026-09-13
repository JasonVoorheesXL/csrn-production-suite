"""Baseball engine P3 acceptance (docs/BASEBALL_SOFTBALL_ENGINE_SCOPING_PLAN.md
P3 row): "box_score_service.report(state) matches a hand-scored test game;
overlay payload validates against DIAMOND_OVERLAY_CONTRACT.md."
"""

from __future__ import annotations

from at_bat_rules_service import AtBatRulesService
from box_score_service import BoxScoreService
from diamond_state_service import default_state
from overlay_serializer import OverlaySerializer


def _new_game() -> dict:
    state = {
        "sport": "baseball",
        "status": "live",
        "home_score": 0,
        "visitor_score": 0,
        "home_team": "Caledonia",
        "visitor_team": "New Hope",
    }
    state.update(default_state())
    return state


def _play_the_hand_scored_top_of_the_first(state: dict) -> None:
    # A hand-scoreable top-of-the-first: b1 walks, b2 homers (scoring both),
    # b3/b4/b5 make outs. One pitcher (p1) throughout.
    AtBatRulesService.record_plate_appearance(state, {
        "battingTeam": "visitor", "batterId": "b1", "pitcherId": "p1",
        "resultCode": "BB", "runnerOutcomes": [{"from": "batter", "to": "first", "playerId": "b1"}],
        "outsRecorded": 0,
    })
    AtBatRulesService.record_plate_appearance(state, {
        "battingTeam": "visitor", "batterId": "b2", "pitcherId": "p1",
        "resultCode": "HR",
        "runnerOutcomes": [
            {"from": "batter", "to": "score", "playerId": "b2"},
            {"from": "first", "to": "score"},
        ],
        "outsRecorded": 0, "hits": 1,
    })
    AtBatRulesService.record_plate_appearance(state, {
        "battingTeam": "visitor", "batterId": "b3", "pitcherId": "p1",
        "resultCode": "SO", "runnerOutcomes": [], "outsRecorded": 1,
    })
    AtBatRulesService.record_plate_appearance(state, {
        "battingTeam": "visitor", "batterId": "b4", "pitcherId": "p1",
        "resultCode": "OUT", "runnerOutcomes": [], "outsRecorded": 1,
    })
    AtBatRulesService.record_plate_appearance(state, {
        "battingTeam": "visitor", "batterId": "b5", "pitcherId": "p1",
        "resultCode": "OUT", "runnerOutcomes": [], "outsRecorded": 1,
    })


def test_box_score_matches_a_hand_scored_half_inning() -> None:
    state = _new_game()
    _play_the_hand_scored_top_of_the_first(state)
    # half-inning should have closed on the third out.
    assert state["inning_half"] == "BOTTOM"
    assert state["visitor_score"] == 2

    report = BoxScoreService.report(state)

    assert report["line_score"]["visitor"]["runs"] == 2
    assert report["line_score"]["visitor"]["hits"] == 1
    assert report["line_score"]["visitor"]["innings"][0] == 2

    batting = report["batting"]
    assert batting["b1"] == {"ab": 0, "h": 0, "r": 1, "rbi": 0, "bb": 1, "so": 0, "hbp": 0}
    assert batting["b2"] == {"ab": 1, "h": 1, "r": 1, "rbi": 2, "bb": 0, "so": 0, "hbp": 0}
    assert batting["b3"] == {"ab": 1, "h": 0, "r": 0, "rbi": 0, "bb": 0, "so": 1, "hbp": 0}
    assert batting["b4"] == {"ab": 1, "h": 0, "r": 0, "rbi": 0, "bb": 0, "so": 0, "hbp": 0}
    assert batting["b5"] == {"ab": 1, "h": 0, "r": 0, "rbi": 0, "bb": 0, "so": 0, "hbp": 0}

    pitching = report["pitching"]
    assert pitching["p1"] == {"h": 1, "r": 2, "bb": 1, "so": 1, "ip": "1.0"}

    assert "earned_runs" in report["notes"]


def test_box_score_report_is_stable_across_repeated_calls_and_does_not_mutate_state() -> None:
    # report() rebuilds internally (for before/after stamps) -- must never
    # mutate the caller's live state.
    state = _new_game()
    _play_the_hand_scored_top_of_the_first(state)
    before = {k: v for k, v in state.items() if k != "diamond_events"}
    BoxScoreService.report(state)
    BoxScoreService.report(state)
    after = {k: v for k, v in state.items() if k != "diamond_events"}
    assert before == after


def test_box_score_ignores_voided_plate_appearances() -> None:
    from diamond_event_service import DiamondEventService

    state = _new_game()
    _play_the_hand_scored_top_of_the_first(state)
    # void the strikeout (b3) -- box score should stop counting it.
    events = [e for e in state["diamond_events"] if not e.get("voided")]
    strikeout_event_id = next(e["event_id"] for e in events if e["payload"].get("batterId") == "b3")
    DiamondEventService.void_event(state, strikeout_event_id)
    report = BoxScoreService.report(state)
    assert "b3" not in report["batting"]


# --- overlay serializer / DIAMOND_OVERLAY_CONTRACT.md conformance -----------


def test_overlay_serializer_emits_the_documented_wire_fields() -> None:
    state = _new_game()
    _play_the_hand_scored_top_of_the_first(state)
    state["current_batter_id"] = "b6"
    state["pitcher_name"] = ""  # overlay serializer resolves display names, not raw ids
    payload = OverlaySerializer.serialize(state, pitcher_name="P. Ace", batter_name="B. Six", batter_position="SS")

    # Sec.1 table: exact wire names the already-shipped renderer reads.
    for key in (
        "inning", "inning_half", "balls", "strikes", "outs", "bases",
        "pitcher_name", "batter_name", "batter_position",
        "home_hits", "visitor_hits", "home_errors", "visitor_errors",
        "line_score", "home_score", "visitor_score", "regulation_innings",
    ):
        assert key in payload, key

    assert payload["inning_half"] in {"TOP", "BOTTOM"}
    assert isinstance(payload["bases"], list) and len(payload["bases"]) == 3
    assert all(isinstance(b, bool) for b in payload["bases"])
    assert payload["line_score"] == {"home": [], "visitor": [2]}
    assert payload["pitcher_name"] == "P. Ace"
    assert payload["batter_name"] == "B. Six"
    assert payload["batter_position"] == "SS"
    # Sec.2 fix: regulation_innings now comes from the real ruleset instead
    # of the renderer's own hardcoded 9-inning fallback.
    assert payload["regulation_innings"] == 7
