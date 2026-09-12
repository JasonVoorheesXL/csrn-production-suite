"""Regression coverage for the Caledonia @ Lamar (9/11/2026) bug report,
item 2 (MEDIUM): manual events (penalty, XP/2PT and the shared TD/FG/
TURNOVER commit path) left the play register blank/stale until the next
poll, because they never force-refreshed it after a successful commit --
unlike the run/pass play-entry flow's finishCommittedPlayEntry(), which
already calls refreshPlayRegister(reason, true).
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_submit_penalty_force_refreshes_play_register() -> None:
    html = _read("templates/index.html")
    fn = html[html.index("async function submitPenalty()"):]
    fn = fn[: fn.index("\nfunction ", 1)]
    assert "refreshPlayRegister('penalty-commit',true)" in fn


def test_confirm_automation_event_force_refreshes_play_register() -> None:
    # confirmAutomationEvent() is the shared TD/FG/XP/2PT/TURNOVER commit
    # path -- the same fix covers all of them, not just XP/2PT.
    html = _read("templates/index.html")
    fn = html[html.index("async function confirmAutomationEvent()"):]
    fn = fn[: fn.index("\nasync function triggerEvent", 1)]
    assert "refreshPlayRegister('automation-event-commit',true)" in fn
    # the refresh happens on the success path, after the modal closes
    assert fn.index("closeAutomationEvent()") < fn.index("refreshPlayRegister('automation-event-commit',true)")
