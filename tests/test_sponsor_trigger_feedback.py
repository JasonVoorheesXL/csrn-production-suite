"""Sponsor video trigger: instant operator acknowledgment + duration probe
moved off the trigger path.

The operator has no audio/intercom feedback, so clicking Run must give an
immediate visual ack (reusing the command client's "SUBMITTING · <action>"
status surface) rather than waiting for the overlay to confirm playback.
Separately, sponsorAdvertisementDuration() -- a hidden <video> metadata load
with a 6 s timeout -- used to run on the Run click; it now runs when the
video is selected so the trigger path is a cache hit.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")


def _fn_body(name: str) -> str:
    start = INDEX.index(f"async function {name}(")
    # walk to the matching close brace of the function
    depth = 0
    for i in range(INDEX.index("{", start), len(INDEX)):
        c = INDEX[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return INDEX[start:i + 1]
    raise AssertionError(f"could not bound {name}")


def test_run_advertisement_acknowledges_before_any_await() -> None:
    body = _fn_body("runSponsorAdvertisement")
    ack = body.index("commandClientStatus('SUBMITTING · sponsor advertisement'")
    first_await = body.index("await ")
    assert ack < first_await, "ack must fire synchronously, before the first await"
    assert "Sponsor video triggered — starting…" in body


def test_run_advertisement_reports_commit_and_failure_on_the_shared_surface() -> None:
    body = _fn_body("runSponsorAdvertisement")
    assert "commandClientStatus('COMMITTED · sponsor advertisement'" in body
    assert "commandClientStatus('Sponsor advertisement failed to start.'" in body


def test_show_sponsor_spotlight_also_acknowledges_immediately() -> None:
    body = _fn_body("showSponsorSpotlight")
    ack = body.index("commandClientStatus('SUBMITTING · sponsor spotlight'")
    first_await = body.index("await ")
    assert ack < first_await
    assert "Sponsor spotlight triggered — starting…" in body
    # still surfaces a failure instead of a silent throw
    assert "catch(error)" in body


def test_rapid_re_trigger_is_blocked_while_one_is_in_flight() -> None:
    # A shared guard: both sponsor triggers write the same sponsor_spotlight
    # state, and the cold-video delay tempts a re-click.
    assert "let sponsorTriggerBusy=false;" in INDEX
    for name in ("runSponsorAdvertisement", "showSponsorSpotlight"):
        body = _fn_body(name)
        guard = body.index("if(sponsorTriggerBusy)")
        set_busy = body.index("sponsorTriggerBusy=true")
        first_await = body.index("await ")
        clear = body.index("finally{sponsorTriggerBusy=false")
        assert guard < set_busy < first_await, f"{name}: guard/set must precede any await"
        assert clear > first_await, f"{name}: guard must clear in finally, after the awaits"


def test_run_buttons_are_disabled_while_a_trigger_is_pending() -> None:
    assert 'id="sadRunButton"' in INDEX
    assert 'id="spsShowButton"' in INDEX
    helper = INDEX[INDEX.index("function setSponsorTriggerButtons("):]
    helper = helper[:helper.index("\n}\n") + 3]
    assert "'sadRunButton'" in helper and "'spsShowButton'" in helper
    for name in ("runSponsorAdvertisement", "showSponsorSpotlight"):
        body = _fn_body(name)
        assert "setSponsorTriggerButtons(true)" in body
        assert "setSponsorTriggerButtons(false)" in body[body.index("finally"):]


def test_duration_probe_runs_at_selection_not_only_at_trigger() -> None:
    preview = INDEX[INDEX.index("function renderSponsorAdvertisementPreview()"):]
    preview = preview[:preview.index("\n}\n") + 3]
    assert "sponsorAdvertisementDuration(asset)" in preview


def test_run_advertisement_still_falls_back_to_probing_on_a_cold_cache() -> None:
    # The pre-read is best-effort; the trigger path must still work if it
    # never ran (e.g. asset picked before assets finished loading).
    body = _fn_body("runSponsorAdvertisement")
    assert "await sponsorAdvertisementDuration(asset)" in body


def test_probe_is_cache_first_so_a_warm_selection_makes_the_trigger_instant() -> None:
    probe = INDEX[INDEX.index("function sponsorAdvertisementDuration(asset)"):]
    probe = probe[:probe.index("\n}\n") + 3]
    assert "sponsorAdvertisementDurationCache.has(asset.id)" in probe
    assert "Promise.resolve(sponsorAdvertisementDurationCache.get(asset.id))" in probe
