"""Overlay preloads sponsor commercials instead of cold-loading them on trigger.

mountCentralBoardMedia() used to build a fresh `<video src>` on every sponsor
trigger, so the browser fetched + decoded the whole commercial from scratch
(the 5-15s the operator sees). csrn-production-theme-runtime.js now keeps a
hidden `<video preload="auto">` per URL, warmed every poll from
runtime.sponsor_spotlight.media_url (which persists in state after a hide),
and the board reuses that warm element.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "static" / "csrn-production-theme-runtime.js").read_text(encoding="utf-8")


def _slice(start_marker: str, span: int = 1400) -> str:
    i = JS.index(start_marker)
    return JS[i:i + span]


def test_warm_cache_helpers_exist() -> None:
    assert "const sponsorVideoWarmCache = new Map()" in JS
    assert "function warmSponsorVideo(url)" in JS
    assert "function takeWarmSponsorVideo(url)" in JS


def test_warm_cache_is_bounded() -> None:
    body = _slice("function warmSponsorVideo(url)")
    assert "SPONSOR_WARM_CACHE_MAX" in body
    assert "sponsorVideoWarmCache.size > SPONSOR_WARM_CACHE_MAX" in body


def test_warm_element_preloads() -> None:
    body = _slice("function warmSponsorVideo(url)")
    assert 'el.preload = "auto"' in body
    assert "el.src = url" in body
    assert "el.load()" in body


def test_poll_warms_the_next_commercial_from_persisted_state() -> None:
    # Called on the render path where runtime is available, gated to video.
    region = _slice("lastRuntimeForClockPatch = runtime;", 600)
    assert "warmSponsorVideo(imageCandidate(warmSpot.media_url))" in region
    assert 'media_type || "").toLowerCase() === "video"' in region


def test_board_reuses_the_warm_element_instead_of_always_creating_one() -> None:
    board = _slice("if (type === \"video\" && primaryUrl) {", 900)
    assert "takeWarmSponsorVideo(primaryUrl) || document.createElement(\"video\")" in board
    # still resets to the start and still keeps a cold-path fallback
    assert "video.currentTime = 0" in board
    assert 'document.createElement("video")' in board
