"""Basketball engine P2 (docs/BASKETBALL_ENGINE_SCOPING_PLAN.md Sec.10 P2
row): hoops_event_service (operator boundary, edit/undo/restore), a
lightweight hoops_lineup_service (5 + bench, free subs, DQ tracking), and
hoops_box_score_service (PTS/REB/AST/STL/BLK/TO/PF, FG/3P/FT splits, team
totals). Gate: "Undo/redo parity with football; a foul entered late and
corrected keeps team fouls + bonus + DQ right."

No UI, no routes -- direct service-to-service calls, matching P0/P1's own
discipline.
"""

from __future__ import annotations

from hoops_box_score_service import HoopsBoxScoreService
from hoops_event_service import HoopsEventService
from hoops_lineup_service import HoopsLineupService
from hoops_period_service import HoopsPeriodService
from hoops_rules_service import HoopsRulesService


def _new_game() -> tuple[dict, dict]:
    state = {
        "sport": "basketball", "country": "US", "region": None, "association": "NFHS",
        "home_team": "Home", "visitor_team": "Visitor",
        "home_score": 0, "visitor_score": 0,
    }
    ruleset = HoopsRulesService.active_ruleset(state)
    HoopsPeriodService.start_game(state, ruleset)
    return state, ruleset


# --- hoops_event_service: undo/redo/void/correct ----------------------------

def test_undo_voids_the_most_recent_contributing_event_and_rebuilds():
    state, ruleset = _new_game()
    HoopsRulesService.shot(state, {"team": "home", "made": True, "points": 2, "shooterId": "H1"})
    HoopsRulesService.shot(state, {"team": "visitor", "made": True, "points": 3, "shooterId": "V1"})
    assert state["home_score"] == 2
    assert state["visitor_score"] == 3

    result = HoopsEventService.undo(state)
    assert result.ok
    assert state["visitor_score"] == 0  # the 3-pointer is undone
    assert state["home_score"] == 2  # the earlier shot is untouched


def test_redo_restores_the_most_recently_undone_event():
    state, ruleset = _new_game()
    HoopsRulesService.shot(state, {"team": "home", "made": True, "points": 2, "shooterId": "H1"})
    HoopsEventService.undo(state)
    assert state["home_score"] == 0

    result = HoopsEventService.redo(state)
    assert result.ok
    assert state["home_score"] == 2


def test_undo_with_only_game_start_in_the_ledger_refuses_rather_than_erroring():
    # GAME_START is itself the only contributing event this early -- undo()
    # refuses it by name (CANNOT_UNDO_GAME_START), a more specific result
    # than a generic "nothing to undo" would be, and still never raises.
    state, ruleset = _new_game()
    result = HoopsEventService.undo(state)
    assert result.code == "CANNOT_UNDO_GAME_START"


def test_undo_with_truly_no_events_at_all_reports_it_rather_than_erroring():
    state = {"hoops": {"hoops_events": []}}
    result = HoopsEventService.undo(state)
    assert result.code == "NO_EVENTS_TO_UNDO"


def test_game_start_can_never_be_undone_voided_or_corrected():
    state, ruleset = _new_game()
    game_start_id = state["hoops"]["hoops_events"][0]["event_id"]

    assert HoopsEventService.undo(state).code == "CANNOT_UNDO_GAME_START"
    assert HoopsEventService.void_event(state, game_start_id).code == "CANNOT_VOID_GAME_START"
    assert HoopsEventService.correct_event(state, game_start_id, {}).code == "CANNOT_CORRECT_GAME_START"


def test_void_event_targets_a_specific_earlier_event_not_just_the_latest():
    state, ruleset = _new_game()
    first = HoopsRulesService.shot(state, {"team": "home", "made": True, "points": 2, "shooterId": "H1"})
    HoopsRulesService.shot(state, {"team": "visitor", "made": True, "points": 3, "shooterId": "V1"})
    assert state["home_score"] == 2
    assert state["visitor_score"] == 3

    result = HoopsEventService.void_event(state, first.data["event"]["event_id"], reason="mis-recorded")
    assert result.ok
    assert state["home_score"] == 0  # the earlier (voided) shot
    assert state["visitor_score"] == 3  # the later shot is untouched

    # The voided event stays visible in the ledger (audit trail).
    voided_ids = [e["event_id"] for e in state["hoops"]["hoops_events"] if e.get("voided")]
    assert first.data["event"]["event_id"] in voided_ids


def test_correcting_a_late_foul_keeps_team_fouls_bonus_and_disqualification_right():
    # The gate example, verbatim.
    state, ruleset = _new_game()

    # Four uncorrected personal fouls on the visitor, one per different
    # player -- none of these trip the bonus or a foul-out yet.
    HoopsRulesService.foul(state, {"team": "visitor", "playerId": "V1", "foulType": "personal"})
    HoopsRulesService.foul(state, {"team": "visitor", "playerId": "V2", "foulType": "personal"})
    HoopsRulesService.foul(state, {"team": "visitor", "playerId": "V3", "foulType": "personal"})
    fourth = HoopsRulesService.foul(state, {"team": "visitor", "playerId": "V1", "foulType": "personal"})
    assert state["hoops"]["visitor_team_fouls"] == 4
    assert state["hoops"]["home_bonus"] == "NONE"
    assert state["hoops"]["player_fouls"]["V1"] == 2

    # The 4th foul was entered late/wrong -- it should have been charged
    # to V4, not V1 (V1 only actually fouled once). Correct it.
    fourth_event_id = fourth.data["event"]["event_id"]
    corrected = HoopsRulesService.correct_event_for_foul(
        state, fourth_event_id, {"team": "visitor", "playerId": "V4", "foulType": "personal"},
        reason="mis-attributed to V1",
    )
    assert corrected.ok

    # Team fouls: still 4 (the correction replaces the 4th foul, it
    # doesn't add a 5th) -- bonus still NONE.
    assert state["hoops"]["visitor_team_fouls"] == 4
    assert state["hoops"]["home_bonus"] == "NONE"
    # Personal fouls: V1 is back down to 1 (the mis-attributed foul is
    # gone), V4 now correctly shows 1.
    assert state["hoops"]["player_fouls"]["V1"] == 1
    assert state["hoops"]["player_fouls"]["V4"] == 1
    assert "V1" not in state["hoops"]["disqualified"]
    assert "V4" not in state["hoops"]["disqualified"]

    # Now push V4 to the foul-out threshold across 4 more fouls -- DQ
    # tracking should reflect the CORRECTED attribution, not the original.
    for _ in range(4):
        HoopsRulesService.foul(state, {"team": "visitor", "playerId": "V4", "foulType": "personal"})
    assert state["hoops"]["player_fouls"]["V4"] == 5
    assert "V4" in state["hoops"]["disqualified"]
    assert state["hoops"]["home_bonus"] == "DOUBLE"  # visitor's 8th team foul


# --- hoops_lineup_service ----------------------------------------------------

def test_set_starting_five_requires_exactly_five_distinct_players():
    state, ruleset = _new_game()
    ok = HoopsLineupService.set_starting_five(state, "home", ["H1", "H2", "H3", "H4", "H5"])
    assert ok.ok
    assert state["hoops"]["home_on_floor"] == ["H1", "H2", "H3", "H4", "H5"]

    too_few = HoopsLineupService.set_starting_five(state, "visitor", ["V1", "V2"])
    assert too_few.code == "INVALID_ROSTER_SIZE"


def test_substitution_is_free_but_gated_structurally():
    state, ruleset = _new_game()
    HoopsLineupService.set_starting_five(state, "home", ["H1", "H2", "H3", "H4", "H5"])

    ok = HoopsLineupService.substitute(state, "home", "H1", "H6")
    assert ok.ok
    assert state["hoops"]["home_on_floor"] == ["H6", "H2", "H3", "H4", "H5"]

    not_on_floor = HoopsLineupService.substitute(state, "home", "H1", "H7")
    assert not_on_floor.code == "PLAYER_NOT_ON_FLOOR"

    already_on_floor = HoopsLineupService.substitute(state, "home", "H2", "H3")
    assert already_on_floor.code == "PLAYER_ALREADY_ON_FLOOR"


def test_a_disqualified_player_can_never_be_subbed_back_in_and_must_be_subbed_out():
    state, ruleset = _new_game()
    HoopsLineupService.set_starting_five(state, "visitor", ["V1", "V2", "V3", "V4", "V5"])
    for _ in range(5):
        HoopsRulesService.foul(state, {"team": "visitor", "playerId": "V1", "foulType": "personal"})
    assert "V1" in state["hoops"]["disqualified"]
    assert HoopsLineupService.players_needing_substitution(state, "visitor") == ["V1"]

    # Sub V1 out (required before play resumes) -- succeeds.
    subbed = HoopsLineupService.substitute(state, "visitor", "V1", "V6")
    assert subbed.ok
    assert HoopsLineupService.players_needing_substitution(state, "visitor") == []

    # Now that V1 is off the floor, attempting to bring the same
    # (disqualified) player back in over someone else is refused for
    # being disqualified specifically -- not merely "already on floor".
    refused = HoopsLineupService.substitute(state, "visitor", "V2", "V1")
    assert refused.code == "PLAYER_DISQUALIFIED"
    assert HoopsLineupService.players_needing_substitution(state, "visitor") == []


# --- hoops_box_score_service --------------------------------------------------

def test_box_score_reports_points_rebounds_assists_steals_blocks_turnovers_fouls():
    state, ruleset = _new_game()

    # H1 makes a 2, assisted by H2.
    HoopsRulesService.shot(state, {"team": "home", "made": True, "points": 2, "shooterId": "H1", "assistId": "H2"})
    # H3 makes a 3, unassisted.
    HoopsRulesService.shot(state, {"team": "home", "made": True, "points": 3, "shooterId": "H3"})
    # V1's shot is blocked by H4 (missed).
    HoopsRulesService.shot(state, {"team": "visitor", "made": False, "points": 2, "shooterId": "V1", "blockPlayerId": "H4"})
    # H1 grabs the defensive rebound.
    HoopsRulesService.rebound(state, {"team": "home", "playerId": "H1", "kind": "defensive"})
    # H1 makes 1 of 2 free throws.
    HoopsRulesService.free_throw(state, {"team": "home", "made": True, "shooterId": "H1"})
    HoopsRulesService.free_throw(state, {"team": "home", "made": False, "shooterId": "H1"})
    # V2 turns it over, stolen by H2.
    HoopsRulesService.turnover(state, {"team": "visitor", "playerId": "V2", "stealPlayerId": "H2"})
    # V3 commits a personal foul.
    HoopsRulesService.foul(state, {"team": "visitor", "playerId": "V3", "foulType": "personal"})

    report = HoopsBoxScoreService.report(state)
    players = report["players"]

    assert players["H1"]["pts"] == 3  # 2 (made shot) + 1 (made FT)
    assert players["H1"]["fgm"] == 1 and players["H1"]["fga"] == 1
    assert players["H1"]["ftm"] == 1 and players["H1"]["fta"] == 2
    assert players["H1"]["reb"] == 1
    assert players["H3"]["pts"] == 3
    assert players["H3"]["fg3m"] == 1 and players["H3"]["fg3a"] == 1
    assert players["H2"]["ast"] == 1
    assert players["H2"]["stl"] == 1
    assert players["H4"]["blk"] == 1
    assert players["V1"]["fga"] == 1 and players["V1"]["fgm"] == 0
    assert players["V2"]["to"] == 1
    assert players["V3"]["pf"] == 1

    totals = report["team_totals"]
    assert totals["home"]["score"] == 6  # 2 + 3 + 1
    assert totals["visitor"]["team_fouls"] == 1


def test_box_score_reflects_a_correction_not_the_original_mistaken_event():
    state, ruleset = _new_game()
    shot = HoopsRulesService.shot(state, {"team": "home", "made": True, "points": 2, "shooterId": "H1"})
    # Correcting a SHOT uses the generic primitive directly -- shots need
    # no ruleset re-resolution the way a foul correction does (see
    # correct_event_for_foul(), tested above for the FOUL case).
    HoopsEventService.correct_event(
        state, shot.data["event"]["event_id"],
        {"team": "home", "made": True, "points": 2, "shooterId": "H9"},  # actually H9, not H1
        reason="wrong shooter recorded",
    )
    players = HoopsBoxScoreService.player_box(state)
    assert players.get("H1", {"pts": 0})["pts"] == 0
    assert players["H9"]["pts"] == 2
