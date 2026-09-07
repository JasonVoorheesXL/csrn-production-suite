"""Phase C R8 (item 2): transparent-for-video baseball clash backdrop.

ensureCollegiateVideoStage() (commit 7) gains a sport-appropriate resting
backdrop for `.bl-college-stage-field` -- a textured ballpark field for
baseball / softball -- that clears to transparent the moment a real feed or
interstitial mounts into the `[data-video-mode]` host via the
nativeVideoBoardHost contract. Runtime-only: no csrn-broadcast-layout-engine
edit, no SHA-256 re-pin.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "static" / "csrn-production-theme-runtime.js").read_text(encoding="utf-8")
CSS = (ROOT / "static" / "csrn-production-theme-runtime.css").read_text(encoding="utf-8")
ENGINE_JS = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
ENGINE_CSS = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")


def _body() -> str:
    start = JS.index("function ensureCollegiateVideoStage(root, runtime)")
    return JS[start:JS.index("\nfunction ", start + 1)]


def test_no_frozen_engine_edit() -> None:
    for name in ("bl-college-stage-diamond", "bl-college-stage-live-feed"):
        assert name not in ENGINE_JS
        assert name not in ENGINE_CSS


def test_backdrop_class_is_toggled_for_baseball_and_softball_only() -> None:
    body = _body()
    assert 'const family = productionSportFamily(runtime && runtime.sport);' in body
    assert (
        'stage.classList.toggle("bl-college-stage-diamond", '
        'family === "baseball" || family === "softball");'
    ) in body


def test_stage_is_now_updated_in_place_not_created_once_only() -> None:
    body = _body()
    # the once-only early-return guard is gone; the stage is found-or-created
    assert 'let stage = board.querySelector(":scope > .bl-college-stage");' in body
    assert "if (!stage) {" in body


def test_transparent_for_video_reads_the_data_video_mode_host() -> None:
    body = _body()
    assert 'const host = stage.querySelector(":scope > [data-video-mode]");' in body
    assert 'host.querySelector("video, img")' in body
    assert 'host.classList.contains("csrn-production-highlight-board")' in body
    assert 'host.classList.contains("csrn-production-sponsor-board")' in body
    assert 'stage.classList.toggle("bl-college-stage-live-feed", liveFeed);' in body


def test_baseball_backdrop_css_has_the_ballpark_layers() -> None:
    assert ".bl-college-stage-diamond > .bl-college-stage-field{" in CSS
    block = CSS[CSS.index(".bl-college-stage-diamond > .bl-college-stage-field{"):]
    block = block[: block.index("}")]
    assert "repeating-conic-gradient(from 300deg at 50% 100%" in block  # mowing fans
    assert "conic-gradient(from 0deg at 50% 100%" in block              # foul lines
    assert "#b07b3f" in block                                           # infield dirt
    assert "opacity:1" in block and "filter:" in block


def test_live_feed_clears_the_backdrop() -> None:
    assert ".bl-college-stage-live-feed > .bl-college-stage-field{" in CSS
    block = CSS[CSS.index(".bl-college-stage-live-feed > .bl-college-stage-field{"):]
    block = block[: block.index("}")]
    assert "opacity:0!important" in block
    assert "background:none!important" in block


def test_contract_selector_still_resolves_after_the_backdrop_change() -> None:
    # nativeVideoBoardHost still keys on the same class; the backdrop is a
    # sibling of the [data-video-mode] host, not a wrapper.
    native = JS[JS.index("function nativeVideoBoardHost"):]
    native = native[: native.index("\nfunction ", 1)]
    assert 'collegiate_traditional: ".bl-college-stage"' in native
