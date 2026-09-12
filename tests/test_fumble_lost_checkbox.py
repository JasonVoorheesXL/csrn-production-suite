"""Regression coverage for the Caledonia @ Lamar (9/11/2026) bug report,
item 3 (LOW): the "Fumble lost" checkbox was disabled until "Fumble" was
checked first, so an operator checking "Fumble lost" directly (a natural
click order) silently had no effect and the turnover never got flagged.

Fix: remove the disabled-until-Fumble gating entirely; "Fumble lost" now
implies "Fumble" (checking it auto-checks Fumble), and unchecking "Fumble"
clears "Fumble lost" too.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_fumble_lost_checkbox_is_not_disabled_in_markup() -> None:
    html = _read("templates/index.html")
    idx = html.index('id="playFumbleLost"')
    tag = html[idx - 40: idx + 80]
    assert "disabled" not in tag


def test_open_play_entry_no_longer_force_disables_fumble_lost() -> None:
    html = _read("templates/index.html")
    fn = html[html.index("async function openPlayEntry("):]
    fn = fn[: fn.index("\nfunction closePlayEntry", 1)]
    assert "playFumbleLost').disabled" not in fn


def test_turnover_entry_changed_makes_fumble_lost_imply_fumble() -> None:
    html = _read("templates/index.html")
    fn = html[html.index("function turnoverEntryChanged()"):]
    fn = fn[: fn.index("}", fn.index("playOutcomeChanged()")) + 1]
    assert "if(lost.checked)fumble.checked=true" in fn
    assert "if(!fumble.checked)lost.checked=false" in fn
    # the old disabling behaviour is gone
    assert ".disabled=" not in fn
