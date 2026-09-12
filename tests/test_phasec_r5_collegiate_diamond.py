"""Phase C R5 (commissioned): Collegiate Tech baseball/softball diamond graphic.

A real CSS/SVG field-position graphic in the .bl-college-field idiom,
injected by the runtime so csrn-broadcast-layout-engine (SHA-256 pinned)
stays byte-stable.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
JS = (ROOT / "static" / "csrn-production-theme-runtime.js").read_text(encoding="utf-8")
CSS = (ROOT / "static" / "csrn-production-theme-runtime.css").read_text(encoding="utf-8")
ENGINE_JS = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")


def test_diamond_is_injected_by_the_runtime_not_the_frozen_engine() -> None:
    assert "function ensureCollegiateDiamond(root, d)" in JS
    assert "ensureCollegiateDiamond(root, {half, inning, balls, strikes, outs, bases});" in JS
    # the pinned engine file gains nothing
    assert "bl-college-diamond" not in ENGINE_JS


def test_diamond_svg_has_the_real_geometry() -> None:
    block = JS[JS.index("function ensureCollegiateDiamond"):]
    block = block[: block.index("\n}\n", block.index("host.innerHTML")) + 2]
    for cls in ("bl-cd-grass", "bl-cd-dirt", "bl-cd-infield", "bl-cd-foul",
                "bl-cd-mound", "bl-cd-base", "bl-cd-home"):
        assert cls in block
    # three runner markers, one per base
    assert block.count('class="bl-cd-runner') == 3
    for base in ("first", "second", "third"):
        assert f'bl-cd-runner {base}"' in block


def test_diamond_meta_matches_the_football_field_idiom() -> None:
    # same structure/tokens as .bl-college-field-meta
    assert ".bl-college-diamond-meta span{" in CSS
    assert "grid-template-columns:auto minmax(0,1fr)" in CSS
    assert ".bl-college-diamond-meta small{" in CSS and "text-transform:uppercase" in CSS
    assert ".bl-college-diamond-grid{" in CSS
    assert ".bl-college-diamond-art .bl-cd-runner.on{" in CSS


def test_diamond_runtime_updates_bases_count_outs_and_half() -> None:
    block = JS[JS.index("function ensureCollegiateDiamond"):]
    block = block[: block.index("\n}\n", block.index("host.dataset")) + 2]
    assert 'host.dataset.inningHalf = (d.half === "BOT" ? "bottom" : "top");' in block
    assert 'setText(".bl-cd-inning"' in block
    assert 'setText(".bl-cd-count"' in block
    assert 'setText(".bl-cd-outs"' in block
    assert '.bl-cd-runner.first").classList.toggle("on"' in block
