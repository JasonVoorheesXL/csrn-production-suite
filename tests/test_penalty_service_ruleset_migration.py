"""Round 7 Task B step 5 (consumer 1): PenaltyService.enforce() reads its
catalog from the resolved ruleset, not the RULES literal -- transparently.
"""

from __future__ import annotations

import penalty_service
from penalty_service import PenaltyService


def _reset_cache():
    PenaltyService._penalty_rules_cache = None


def test_penalty_rules_come_from_the_ruleset_and_match_the_literal_exactly() -> None:
    _reset_cache()
    resolved = PenaltyService._penalty_rules()
    # byte-identical to the frozen literal (the golden anchor)
    assert resolved == PenaltyService.RULES
    # ...and it is a distinct object sourced at runtime, not RULES itself
    assert resolved is not PenaltyService.RULES


def test_falls_back_to_the_literal_if_the_ruleset_engine_is_unavailable(monkeypatch) -> None:
    _reset_cache()

    import ruleset_service

    def boom(**_kw):
        raise RuntimeError("no rulesets on this box")

    monkeypatch.setattr(ruleset_service, "resolve", boom)
    resolved = PenaltyService._penalty_rules()
    assert resolved == PenaltyService.RULES
    _reset_cache()


def test_enforce_still_applies_the_same_yardage_via_the_ruleset() -> None:
    _reset_cache()
    identity = lambda *a, **k: 0  # noqa: E731 - unused geometry hooks for this assertion

    def spot_to_coord(_spot):
        return 50

    def coord_to_spot(_coord):
        return "50"

    def team_direction(_state, _team):
        return 1

    state = {"possession": "home", "down": "1st", "distance": "10", "ball_spot": "50"}
    result = PenaltyService.enforce(
        state,
        selected_team="visitor",
        requested_unit="Defensive",
        name="Pass Interference",
        yards="",  # <- take the catalog default
        outcome="accepted",
        spot_to_coord=spot_to_coord,
        coord_to_spot=coord_to_spot,
        team_direction=team_direction,
    )
    # Defensive Pass Interference is 15 / automatic first down in RULES
    assert result["yards"] == 15
    assert result["automatic_first_down"] is True
