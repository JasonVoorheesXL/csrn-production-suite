"""Sign-in usability (2026-10-31): Enter submits the PIN forms, and a wrong
PIN says so instead of a generic "Authentication required"."""
from __future__ import annotations

from pathlib import Path

HTML = (Path(__file__).resolve().parents[1] / "templates" / "index.html").read_text(encoding="utf-8")


def test_enter_unlocks_and_saves_the_pin() -> None:
    assert 'id="loginPin" type="password" inputmode="numeric" maxlength="6" autocomplete="current-password" onkeydown="if(event.key===\'Enter\'){event.preventDefault();login()}"' in HTML
    assert 'id="newPin"' in HTML and "document.getElementById('confirmPin').focus()" in HTML
    assert 'id="confirmPin"' in HTML and "onkeydown=\"if(event.key==='Enter'){event.preventDefault();setupPin()}\"" in HTML


def test_a_wrong_pin_reaches_the_incorrect_pin_message() -> None:
    api = HTML[HTML.index("async function api(path, body = null, method = null) {"):]
    api = api[: api.index("\n}\n")]
    assert "new Error(data.error === 'INVALID_PIN' ? 'INVALID_PIN' : 'Authentication required')" in api
    assert "err.data = data;" in api
    assert "msg.textContent = `Incorrect PIN. ${err.data.attempts_remaining} attempt(s) remaining.`;" in HTML
