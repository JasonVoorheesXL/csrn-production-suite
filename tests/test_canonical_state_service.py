"""Regression coverage for CanonicalStateFoundation's scrimmage-play engine.

2026-09 incident (Caledonia vs. Amory): a genuine touchdown run correctly
entered "pending_try" and parked the ball at the goal line. A second
scrimmage play ("Touchdown Run", 12 yards) was then recorded -- by whatever
means -- while the game was still in that pending_try window. Because
_apply_scrimmage_play() derived the play's start coordinate from the
CURRENT canonical ball_spot (still sitting on the goal line from the real
score) rather than anything that actually happened on the field, any
nonzero yardage in the scoring direction trivially "crossed" the goal line
again -- manufacturing a second, phantom touchdown and a bogus +6 to the
score. The team's touchdown count in statistics_service.py was inflated
by exactly this phantom play (see tests/test_statistics_service.py for the
stats-layer half of this same incident).

Both RulesService.play() and EventService.trigger() already refuse to
record a *new* scrimmage submission while a special phase (pending_try /
kickoff / free_kick) is pending -- but rebuild() must not manufacture a
score out of a play that reaches it anyway (bad/legacy data, an import, or
some other bypass of those two guards). These tests pin that the canonical
engine itself is now safe regardless of how such a play got there.
"""
from __future__ import annotations

from canonical_state_service import CanonicalStateFoundation


def base_state(**overrides) -> dict:
    state = {
        "possession": "home",
        "down": "2nd",
        "distance": "10",
        "ball_spot": "LEFT 2",
        "home_direction": "left",
        "visitor_direction": "right",
        "home_score": 7,
        "visitor_score": 7,
        "special_game_phase": "",
        "kicking_team": "",
        "receiving_team": "",
        "quarter": "2",
        "clock_seconds": 560,
        "clock_visible": True,
        "clock_running": False,
        "clock_started_at": 0,
        "broadcast_phase": "live",
    }
    state.update(overrides)
    return state


def test_apply_scrimmage_play_scores_a_normal_touchdown() -> None:
    # Sanity check: the legitimate case (play 49 in the real incident) must
    # keep working exactly as before -- this fix must not touch the normal
    # path at all.
    state = base_state()
    play = {"play_type": "run", "yards": 5, "offense": "home"}
    CanonicalStateFoundation._apply_scrimmage_play(state, play)
    assert play["touchdown"] is True
    assert state["home_score"] == 13
    assert state["special_game_phase"] == "pending_try"


def test_apply_scrimmage_play_never_scores_a_snap_recorded_during_pending_try() -> None:
    # Play 50 in the real incident: the ball is already parked dead on the
    # goal line (special_game_phase == "pending_try") from the prior,
    # legitimate touchdown. A second "run" here must never be treated as a
    # live snap -- no score change, no ball movement, and the client's own
    # (possibly mistaken) touchdown flag must not survive onto the play.
    state = base_state(
        ball_spot="LEFT GOAL",
        down="Off",
        distance="Off",
        special_game_phase="pending_try",
        home_score=13,
    )
    play = {
        "play_type": "run",
        "yards": 12,
        "offense": "home",
        "touchdown": True,  # statistician mistakenly checked "Touchdown"
    }
    before_spot = state["ball_spot"]
    CanonicalStateFoundation._apply_scrimmage_play(state, play)
    assert state["home_score"] == 13  # unchanged -- no phantom +6
    assert state["ball_spot"] == before_spot
    assert state["special_game_phase"] == "pending_try"
    assert play["touchdown"] is False
    assert play["safety"] is False
    assert play["invalid_during_special_phase"] is True


def test_apply_scrimmage_play_never_scores_during_kickoff_or_free_kick() -> None:
    for phase in ("kickoff", "free_kick"):
        state = base_state(special_game_phase=phase, ball_spot="RIGHT GOAL", home_score=13)
        play = {"play_type": "pass", "yards": 8, "offense": "home", "touchdown": True}
        CanonicalStateFoundation._apply_scrimmage_play(state, play)
        assert state["home_score"] == 13, phase
        assert play["touchdown"] is False, phase


def test_rebuild_reproduces_the_caledonia_incident_without_the_phantom_touchdown() -> None:
    # A trimmed reconstruction of the real play 49 -> 50 -> 51 sequence,
    # run through the actual rebuild() replay used by edit()/undo()/
    # restore(). The phantom play must net to zero, leaving only the one
    # legitimate touchdown (+6) plus the extra point (+1) in the score.
    baseline = base_state(home_score=7)
    events = [
        {
            "id": "evt-49",
            "play_id": "play-49",
            "play_number": 49,
            "created_at": 1,
            "event": "PLAY",
            "team": "home",
            "automation": {"touchdown": False, "play_type": "run"},
        },
        {
            "id": "evt-50",
            "play_id": "play-50",
            "play_number": 50,
            "created_at": 2,
            "event": "PLAY",
            "team": "home",
            "automation": {"touchdown": True, "play_type": "run"},
        },
        {
            "id": "evt-51",
            "play_id": "play-51",
            "play_number": 51,
            "created_at": 3,
            "event": "XP",
            "team": "home",
            "before": {},
            "after": {"home_score": 14, "special_game_phase": "kickoff"},
        },
    ]
    plays = [
        {
            "play_id": "play-49",
            "event_id": "evt-49",
            "play_number": 49,
            "play_type": "run",
            "yards": 5,
            "offense": "home",
            "player_name": "Tyler Long",
        },
        {
            "play_id": "play-50",
            "event_id": "evt-50",
            "play_number": 50,
            "play_type": "run",
            "yards": 12,
            "offense": "home",
            "player_name": "Caleb Lang",
            "touchdown": True,
        },
    ]

    rebuilt = CanonicalStateFoundation.rebuild(baseline, events, plays, baseline=baseline)

    # 7 (start) + 6 (play 49's real touchdown) + 1 (the XP) == 14, never 19
    # or 20 -- the phantom play 50 contributes nothing.
    assert rebuilt["home_score"] == 14
    play_50 = next(p for p in plays if p["play_id"] == "play-50")
    assert play_50["touchdown"] is False
    assert play_50["invalid_during_special_phase"] is True
    play_49 = next(p for p in plays if p["play_id"] == "play-49")
    assert play_49["touchdown"] is True
