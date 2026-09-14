"""Baseball engine P2 followup round (2026-09-14,
docs/BASEBALL_SOFTBALL_ENGINE_SCOPING_PLAN.md): four owner-directed
changes to already-merged P1/P2 code, investigated and confirmed before
any code was touched (see this round's chat report for the investigation
findings this file's tests are built against).

1. GAME_END_CONFIRMED becomes a real, voidable ledger event (was a direct
   status mutation) -- closes a real gap: an unrelated undo after a
   manual game-end used to strand status="completed" with
   official_game_end_reason=None.
2. Courtesy runner's PITCHER/CATCHER-only restriction removed -- any
   player, any association, any time.
3. International tiebreaker wired into the live dispatch table with an
   operator-supplied starting inning, not ruleset-derived.
4. Regulation length gets a narrow per-broadcast override field, checked
   before the ruleset's own scheduledInnings.
"""

from __future__ import annotations

from pathlib import Path

from at_bat_rules_service import AtBatRulesService
from diamond_event_service import DiamondEventService
from diamond_state_service import DiamondStateFoundation, default_state
from game_end_evaluator import GameEndEvaluator
from lineup_service import LineupService
from lineup_service import default_state as lineup_default_state

ROOT = Path(__file__).resolve().parents[1]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def _start_baseball_lineup(state: dict, side: str, dh_mode: str = "NONE") -> None:
    starters = {i: f"{side}-p{i}" for i in range(1, 10)}
    defense = {"P": f"{side}-p1", "C": f"{side}-p2"}
    LineupService.start_lineup(state, side, starters, defense, sport="baseball", dh_mode=dh_mode)


def _new_game(**overrides) -> dict:
    state = {"sport": "baseball", "status": "live", "home_score": 0, "visitor_score": 0}
    state.update(default_state())
    state.update(lineup_default_state())
    state.update(overrides)
    return state


def _score(team: str, runs: int) -> dict:
    return {
        "battingTeam": team,
        "runnerOutcomes": [{"from": "batter", "to": "score"} for _ in range(runs)],
        "outsRecorded": 0,
    }


# === 1. GAME_END_CONFIRMED ledger event ====================================


def test_confirm_game_end_appends_a_real_voidable_ledger_event() -> None:
    state = _new_game()
    result = AtBatRulesService.confirm_game_end(state, "RUN_RULE")
    assert result.ok
    assert state["status"] == "completed"
    assert state["official_game_end_reason"] == "RUN_RULE"

    events = [e for e in state["diamond_events"] if e["event_type"] == "GAME_END_CONFIRMED"]
    assert len(events) == 1
    assert events[0]["payload"] == {"reason": "RUN_RULE"}
    assert events[0]["voided"] is False


def test_void_event_on_game_end_confirmed_reopens_the_game() -> None:
    # "Reopen if ended by mistake" -- no separate reopen method, just the
    # existing generic void_event() on the GAME_END_CONFIRMED event id.
    state = _new_game()
    AtBatRulesService.record_plate_appearance(state, _score("home", 3))
    result = AtBatRulesService.confirm_game_end(state, "RUN_RULE")
    event_id = result.data["event"]["event_id"]
    assert state["status"] == "completed"

    reopen = DiamondEventService.void_event(state, event_id)
    assert reopen.ok
    assert state["status"] == "live"
    assert state["official_game_end_reason"] is None
    # the score the game actually had stays intact -- only the end-of-game
    # flag is reversed, not the plays that led to it.
    assert state["home_score"] == 3


def test_undo_immediately_after_confirm_game_end_reopens_it() -> None:
    # The common "oops, hit confirm by mistake" case: confirm_game_end was
    # the most recent event, so plain undo() (not a targeted void_event())
    # already reaches it.
    state = _new_game()
    AtBatRulesService.confirm_game_end(state, "RUN_RULE")
    assert state["status"] == "completed"

    result = DiamondEventService.undo(state)
    assert result.ok
    assert state["status"] == "live"
    assert state["official_game_end_reason"] is None


def test_voiding_an_unrelated_earlier_event_after_game_end_does_not_strand_the_game() -> None:
    # The actual bug this round fixes: before, official_game_end_reason
    # (a CANONICAL_FIELDS entry) got wiped to None by ANY rebuild -- even
    # one voiding a play that happened before the game ended -- while
    # status (untouched by the old code's rebuild) stayed "completed".
    # That combination (completed + no reason) is the strand. Now, voiding
    # an earlier, unrelated event must leave the game correctly still
    # completed, reason intact, because GAME_END_CONFIRMED itself is
    # still a non-voided, surviving event.
    state = _new_game()
    first = AtBatRulesService.record_plate_appearance(state, _score("home", 1))
    AtBatRulesService.record_plate_appearance(state, _score("visitor", 1))
    AtBatRulesService.confirm_game_end(state, "RUN_RULE")
    assert state["status"] == "completed"
    assert state["official_game_end_reason"] == "RUN_RULE"

    result = DiamondEventService.void_event(state, first.data["event"]["event_id"])
    assert result.ok
    # game-end state survives untouched -- the voided event was unrelated.
    assert state["status"] == "completed"
    assert state["official_game_end_reason"] == "RUN_RULE"
    # but the voided play's own effect is gone, same as any other void.
    assert state["home_score"] == 0
    assert state["visitor_score"] == 1


def test_redo_after_reopening_re_ends_the_game() -> None:
    state = _new_game()
    AtBatRulesService.confirm_game_end(state, "WALK_OFF")
    DiamondEventService.undo(state)
    assert state["status"] == "live"

    result = DiamondEventService.redo(state)
    assert result.ok
    assert state["status"] == "completed"
    assert state["official_game_end_reason"] == "WALK_OFF"


def test_walk_off_and_regulation_confirm_flows_are_unchanged() -> None:
    # Explicitly NOT in scope for this round's mercy-rule change -- confirm
    # they still behave exactly as before (status flips, reason recorded).
    state = _new_game(inning=7, inning_half="BOTTOM", home_score=4, visitor_score=3)
    candidate = GameEndEvaluator.evaluate(state)
    assert candidate == {"reason": "WALK_OFF", "inning": 7, "half": "BOTTOM"}
    result = AtBatRulesService.confirm_game_end(state, "WALK_OFF")
    assert result.ok
    assert state["status"] == "completed"
    assert state["official_game_end_reason"] == "WALK_OFF"


def test_rebuild_from_scratch_reproduces_the_same_completed_state() -> None:
    # Sec.19.1's own replay-determinism property, extended to the new event.
    state = _new_game()
    AtBatRulesService.record_plate_appearance(state, _score("home", 2))
    AtBatRulesService.confirm_game_end(state, "RUN_RULE")
    rebuilt = DiamondStateFoundation.rebuild(state, state["diamond_events"])
    assert rebuilt["status"] == "completed"
    assert rebuilt["official_game_end_reason"] == "RUN_RULE"
    assert rebuilt["home_score"] == 2


def test_game_end_evaluator_never_auto_closes_on_a_run_rule_candidate() -> None:
    # Confirms the investigation finding is still true after this round's
    # changes: evaluate() only ever proposes, never finalizes.
    state = _new_game(inning=5, inning_half="BOTTOM", home_score=12, visitor_score=0)
    before_status = state["status"]
    GameEndEvaluator.evaluate(state)
    assert state["status"] == before_status


# === 2. Courtesy runner: no more PITCHER/CATCHER-only restriction ==========


def test_courtesy_runner_is_accepted_for_a_non_pitcher_catcher_role() -> None:
    # The restriction this round removes -- previously a hard ValueError.
    state = _new_state()
    _start_baseball_lineup(state, "home")
    result = LineupService.enter_courtesy_runner(
        state, "home", "home-cr1", "home-p6", "SHORTSTOP", event_id="e1"
    )
    assert result.ok
    appearances = state["lineup"]["home"]["courtesy_runners"]
    assert len(appearances) == 1
    assert appearances[0]["for_role_at_time"] == "SHORTSTOP"


def test_courtesy_runner_still_records_the_special_role_snapshot_not_a_substitution() -> None:
    # "Keep the special-role modeling exactly as it is now -- only the
    # restriction comes out." Confirm the lineup slot is untouched (CR-01's
    # own invariant) even for a role the old code would have rejected.
    state = _new_state()
    _start_baseball_lineup(state, "home")
    before = dict(state["lineup"]["home"]["slots"])
    LineupService.enter_courtesy_runner(state, "home", "home-cr1", "home-p6", "FIRST_BASE", event_id="e1")
    assert state["lineup"]["home"]["slots"] == before
    assert state["lineup"]["home"]["roles"]["home-cr1"] == "COURTESY_RUNNER"


def test_courtesy_runner_still_supports_pitcher_and_catcher_too() -> None:
    # The old, real use case keeps working -- this is an expansion, not a
    # replacement.
    state = _new_state()
    _start_baseball_lineup(state, "home")
    result = LineupService.enter_courtesy_runner(state, "home", "home-cr1", "home-p2", "CATCHER", event_id="e1")
    assert result.ok
    assert state["lineup"]["home"]["courtesy_runners"][0]["for_role_at_time"] == "CATCHER"


def _new_state() -> dict:
    state = {"sport": "baseball"}
    state.update(default_state())
    state.update(lineup_default_state())
    return state


# === 3. Tiebreaker: operator-supplied starting inning =======================


def test_seed_tiebreaker_runner_requires_an_operator_supplied_inning() -> None:
    # No more silent ruleset fallback -- starting_inning is a required
    # positional argument now (a TypeError, not a quiet default, if a
    # caller forgets it -- confirms nothing can silently drift back to
    # ruleset-derived behavior).
    import inspect

    sig = inspect.signature(GameEndEvaluator.seed_tiebreaker_runner)
    params = list(sig.parameters)
    assert "starting_inning" in params
    assert sig.parameters["starting_inning"].default is inspect.Parameter.empty


def test_seed_tiebreaker_runner_uses_the_supplied_inning_not_the_ruleset() -> None:
    import ruleset_service

    state = _new_game(inning=9, home_score=1, visitor_score=1)

    def fake_ruleset(*_a, **_k):
        # Ruleset says 8 -- operator confirms 9. The recorded event must
        # reflect the operator's number, never the ruleset's.
        return {"tieBreaker": {"mode": "RUNNER_ON_SECOND", "startsAtInning": 8}}

    original = ruleset_service.active_ruleset
    ruleset_service.active_ruleset = fake_ruleset
    try:
        result = GameEndEvaluator.seed_tiebreaker_runner(state, "player-1", 9)
        assert result.ok
        events = [e for e in state["diamond_events"] if e["event_type"] == "TIEBREAKER_RUNNER_PLACED"]
        assert events[0]["payload"]["startingInning"] == 9
    finally:
        ruleset_service.active_ruleset = original


def test_seed_tiebreaker_runner_is_reachable_through_dispatch() -> None:
    import threading

    from diamond_game_operations_service import DiamondGameOperationsService

    class _Store:
        def __init__(self, state: dict) -> None:
            self.state = state

        def load(self) -> dict:
            return self.state

        def save(self, state: dict) -> None:
            self.state = state

    state = {"sport": "baseball", "status": "live", "country": "US", "home_score": 1, "visitor_score": 1}
    store = _Store(state)
    service = DiamondGameOperationsService(
        load_state=store.load, save_state=store.save, transaction_lock=threading.Lock()
    )
    service.dispatch("start_lineup", {
        "side": "home",
        "starters": {i: f"home-p{i}" for i in range(1, 10)},
        "defense": {"P": "home-p1", "C": "home-p2"},
        "sport": "baseball",
    })
    result = service.dispatch("seed_tiebreaker_runner", {"player_id": "home-p3", "starting_inning": 9})
    # No ruleset in this repo has RUNNER_ON_SECOND active yet (only an
    # MHSAA overlay would, and that's P6, not built) -- confirms the
    # wiring itself works: this is a real domain response from
    # game_end_evaluator, not "unknown action" or a dispatch-layer error.
    assert result.code == "TIEBREAKER_NOT_ACTIVE"


# === 4. Regulation length: per-broadcast override ============================


def test_regulation_uses_the_broadcast_override_when_set() -> None:
    # TOP half (never a walk-off candidate) past the override, visitor
    # trailing -- isolates the REGULATION branch specifically.
    state = _new_game(
        inning=7, inning_half="TOP", home_score=2, visitor_score=1,
        regulation_innings_override=6,
    )
    candidate = GameEndEvaluator.evaluate(state)
    assert candidate == {"reason": "REGULATION", "inning": 7}


def test_regulation_falls_back_to_the_ruleset_when_no_override_is_set() -> None:
    state = _new_game(inning=6, inning_half="BOTTOM", home_score=2, visitor_score=1)
    # NFHS-generic ships 7 scheduled innings -- inning 6 is not yet over
    # regulation without an override.
    candidate = GameEndEvaluator.evaluate(state)
    assert candidate is None


def test_walk_off_also_honors_the_broadcast_override() -> None:
    state = _new_game(
        inning=6, inning_half="BOTTOM", home_score=4, visitor_score=3,
        regulation_innings_override=6,
    )
    candidate = GameEndEvaluator.evaluate(state)
    assert candidate == {"reason": "WALK_OFF", "inning": 6, "half": "BOTTOM"}


def test_regulation_innings_override_field_survives_engine_router_diamond_view() -> None:
    # The override lives on the OUTER state (broadcast-level, like
    # effective_profile_id), not inside state["diamond"] -- confirm
    # engine_router.diamond_view() actually threads it through to
    # whatever a dispatched action sees, since that's the real path a
    # live operator's broadcast setup takes, not a raw state dict.
    import engine_router

    state = {"sport": "baseball", "status": "live", "regulation_innings_override": 6}
    view = engine_router.diamond_view(state)
    assert view["regulation_innings_override"] == 6


def test_broadcast_service_normalizes_a_blank_regulation_override_to_none() -> None:
    from broadcast_service import BroadcastService

    assert BroadcastService._regulation_innings_override("") is None
    assert BroadcastService._regulation_innings_override(None) is None
    assert BroadcastService._regulation_innings_override("6") == 6
    assert BroadcastService._regulation_innings_override(6) == 6
    assert BroadcastService._regulation_innings_override("not a number") is None
    assert BroadcastService._regulation_innings_override(0) is None


# === UI presence (text-assertion style, matching this repo's established
# no-JS-harness convention -- see test_baseball_engine_p5_operator_ui.py) ===


def test_tiebreaker_control_exists_in_the_operator_ui() -> None:
    index = read("templates/index.html")
    assert 'id="tbPlayerId"' in index
    assert 'id="tbStartingInning"' in index
    assert 'onclick="diamondSeedTiebreakerRunner()"' in index

    js = read("static/csrn-diamond-controls.js")
    assert "async function diamondSeedTiebreakerRunner()" in js
    assert "function diamondPopulateTiebreakerSelect()" in js


def test_tiebreaker_control_sends_player_id_and_starting_inning_by_name() -> None:
    # diamond_game_operations_service._bind_kwargs() matches payload keys
    # onto GameEndEvaluator.seed_tiebreaker_runner()'s own parameter names
    # (player_id, starting_inning) by exact name -- a mismatch here would
    # silently 404/no-op in production, not raise anywhere obvious.
    js = read("static/csrn-diamond-controls.js")
    start = js.index("async function diamondSeedTiebreakerRunner()")
    body = js[start:js.index("\n}", start)]
    assert "player_id: playerId" in body
    assert "starting_inning: startingInning" in body


def test_seed_tiebreaker_runner_action_is_registered() -> None:
    import diamond_game_operations_service as svc

    assert "seed_tiebreaker_runner" in svc.ACTIONS
    import inspect

    sig = inspect.signature(svc.ACTIONS["seed_tiebreaker_runner"])
    assert "player_id" in sig.parameters
    assert "starting_inning" in sig.parameters


def test_regulation_innings_override_field_exists_in_the_create_broadcast_form() -> None:
    index = read("templates/index.html")
    assert 'id="regulationInningsOverride"' in index
    assert "regulation_innings_override: document.getElementById('regulationInningsOverride').value" in index
    # Edit Broadcast pre-fills it from the existing record, same as every
    # other field in that form.
    assert "regulationInningsOverride:r.regulation_innings_override" in index
