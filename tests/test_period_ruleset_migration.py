"""Round 7 Task B step 5 (consumer 4): PeriodService's quarter length and
quarter set come from the ruleset, not the 720 / {"1".."4","OT"} literals.
"""

from __future__ import annotations

import ruleset_service
from period_service import PeriodService


def _reset():
    PeriodService._period_cache = None


def test_period_values_come_from_the_ruleset_and_match_the_literals() -> None:
    _reset()
    period = PeriodService._period()
    assert period["quarter_seconds"] == 720
    assert period["quarters"] == ["1", "2", "3", "4", "OT"]
    assert tuple(period["quarters"]) == PeriodService._QUARTERS_FALLBACK
    assert period["quarter_seconds"] == PeriodService._QUARTER_SECONDS_FALLBACK


def test_quarter_validator_still_behaves_identically() -> None:
    _reset()
    assert PeriodService._quarter("3") == "3"
    assert PeriodService._quarter("ot") == "OT"
    assert PeriodService._quarter("5") == "1"
    assert PeriodService._quarter("") == "1"
    assert PeriodService._quarter(None) == "1"


def test_stop_clock_reset_uses_the_ruleset_quarter_length() -> None:
    _reset()
    state: dict = {}
    PeriodService._stop_clock(state, reset=True)
    assert state["clock_seconds"] == 720
    assert state["clock_running"] is False
    assert state["clock_started_at"] == 0


def test_falls_back_to_literals_if_the_ruleset_engine_is_unavailable(monkeypatch) -> None:
    _reset()

    def boom(**_kw):
        raise RuntimeError("no rulesets")

    monkeypatch.setattr(ruleset_service, "resolve", boom)
    period = PeriodService._period()
    assert period["quarter_seconds"] == 720
    assert period["quarters"] == ["1", "2", "3", "4", "OT"]
    _reset()
