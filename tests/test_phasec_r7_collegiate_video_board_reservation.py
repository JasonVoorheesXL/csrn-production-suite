"""Phase C R7: reserve the central video-board region on the Collegiate Tech
non-football boards.

FNS / 8-Bit / Heritage all emit their `data-module="video.board"` region for
every sport already. The SHA-256-pinned csrn-broadcast-layout-engine only
emits `.bl-college-stage` for football, so the runtime injects a
contract-shaped host (`.bl-college-stage` + a direct `[data-video-mode]`
child) into the Collegiate baseball / softball / basketball board -- the Gate
16.7 "central video-board ownership" layout space is reserved now instead of
retrofitted when video capability ships.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "static" / "csrn-production-theme-runtime.js").read_text(encoding="utf-8")
CSS = (ROOT / "static" / "csrn-production-theme-runtime.css").read_text(encoding="utf-8")
ENGINE_JS = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")


def _body() -> str:
    start = JS.index("function ensureCollegiateVideoStage(root, runtime)")
    return JS[start:JS.index("\nfunction ", start + 1)]


def test_reserved_stage_is_injected_by_the_runtime_not_the_frozen_engine() -> None:
    assert "function ensureCollegiateVideoStage(root, runtime)" in JS
    # the pinned engine gains nothing
    assert "bl-college-stage-reserved" not in ENGINE_JS
    assert "ensureCollegiateVideoStage" not in ENGINE_JS


def test_reserved_stage_carries_the_video_board_contract() -> None:
    body = _body()
    assert 'stage.className = "bl-college-stage bl-college-stage-reserved"' in body
    assert 'stage.setAttribute("data-module", "video.board")' in body
    assert 'data-video-mode="broadcast"' in body
    # reuses the engine's own collegiate stage classes -- no new assets
    assert "bl-college-stage-field" in body
    assert "bl-college-video-feed" in body


def test_reserved_stage_resolves_through_the_existing_native_host_map() -> None:
    native = JS[JS.index("function nativeVideoBoardHost"):]
    native = native[: native.index("\nfunction ", 1)]
    # the contract's collegiate selector is unchanged; the injected stage
    # matches it and exposes a `:scope > [data-video-mode]` child.
    assert 'collegiate_traditional: ".bl-college-stage"' in native
    assert 'board.querySelector(`:scope > [data-video-mode="${mode}"]`)' in native


def test_reserved_stage_is_wired_into_both_collegiate_branches() -> None:
    diamond = JS[JS.index("function applyDiamondBoardOverrides"):]
    diamond = diamond[: diamond.index("\nfunction ", 1)]
    assert "ensureCollegiateVideoStage(root, runtime);" in diamond

    basketball = JS[JS.index("function applyBasketballBoardOverrides"):]
    basketball = basketball[: basketball.index("\nfunction ", 1)]
    assert "ensureCollegiateVideoStage(root, runtime);" in basketball


def test_reserved_stage_is_injected_once_and_ahead_of_the_diamond() -> None:
    body = _body()
    assert 'board.querySelector(":scope > .bl-college-stage")' in body  # idempotent guard
    assert "board.insertBefore(stage, diamond)" in body


def test_reserved_stage_has_its_own_reserved_layout_css() -> None:
    assert ".bl-college-stage-reserved{" in CSS
    # compact, full-width reserved strip
    assert "grid-column:1 / -1" in CSS
    assert "height:84px" in CSS
    # football-field bleed from the shared .bl-college-stage-field is neutralised
    assert ".bl-college-stage-reserved > .bl-college-stage-field{" in CSS
