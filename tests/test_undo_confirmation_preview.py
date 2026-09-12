"""Regression coverage for the Caledonia @ Lamar (9/11/2026) bug report's
secondary item-1 addition: "Undo Last" had no confirmation or preview of
what it was about to undo. Because EventService.undo()'s target search
walks backward for the first not-undone event -- not necessarily "the last
thing the operator did" if something in between was already undone -- an
operator could undo something much older than expected with zero on-screen
warning.

Fix: a client-side describeUndoTarget() mirrors the server's target search
over currentState.events and previews the label/quarter/description of
what's about to be undone via a confirm() dialog, matching the existing
confirm()-before-destructive-action convention already used elsewhere in
this template (deleteRoster, deleteAsset, endGame, etc.).
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_describe_undo_target_mirrors_the_server_search() -> None:
    html = _read("templates/index.html")
    assert "function describeUndoTarget()" in html
    fn = html[html.index("function describeUndoTarget()"):]
    fn = fn[: fn.index("\nasync function undo", 1)]
    # same shape as EventService.undo()'s target search: walk backward for
    # the first not-undone event that carries a "before" snapshot
    assert "events.length-1" in fn
    assert "!ev.undone&&ev.before" in fn


def test_undo_shows_a_preview_before_committing() -> None:
    html = _read("templates/index.html")
    fn = html[html.index("async function undo() {"):]
    fn = fn[: fn.index("\nasync function restoreLastUndone", 1)]
    assert "describeUndoTarget()" in fn
    assert "confirm(" in fn
    # the coin-toss-undo path is untouched (it has its own dedicated flow)
    assert fn.index("coinTossUndoIsNext()") < fn.index("describeUndoTarget()")
