"""Round 7 Task B step 5 (consumer 3): CanonicalStateFoundation's kickoff /
free-kick / try spots come from the ruleset, not the 40 / 20 / 3 literals.
"""

from __future__ import annotations

import ruleset_service
from canonical_state_service import CanonicalStateFoundation as C


def _reset():
    C._field_yards_cache = None


def _state():
    return {"possession": "home", "home_direction": "right", "visitor_direction": "left"}


def test_field_yards_come_from_the_ruleset_and_match_the_literals() -> None:
    _reset()
    assert C._field_yards() == {"kickoff": 40, "free_kick": 20, "try": 3}
    assert C._field_yards() == C._FIELD_YARDS_FALLBACK


def test_enter_kickoff_free_kick_try_produce_the_same_ball_spots() -> None:
    _reset()
    s = _state()
    C.enter_kickoff(s, "home")
    assert s["ball_spot"] == "LEFT 40"          # home drives right -> own 40 = coord 40
    s = _state()
    C.enter_free_kick(s, "home")
    assert s["ball_spot"] == "LEFT 20"          # own 20
    s = _state()
    C.enter_pending_try(s, "home")
    assert s["ball_spot"] == "RIGHT 3"          # opponent 3 (home attacks coord 100)


def test_falls_back_to_literals_if_the_ruleset_engine_is_unavailable(monkeypatch) -> None:
    _reset()

    def boom(**_kw):
        raise RuntimeError("no rulesets")

    monkeypatch.setattr(ruleset_service, "resolve", boom)
    assert C._field_yards() == {"kickoff": 40, "free_kick": 20, "try": 3}
    _reset()
