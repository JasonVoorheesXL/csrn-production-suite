"""Layout Builder P1, Part B: the builder page (templates/layout_builder.html).

Static-source assertions, per this repo's convention for browser code with no JS
runner; the page's BEHAVIOUR was verified live in a real browser (build a
preset from a starter, use it on air, save, and watch an already-open overlay
change within a poll without a reload) -- see docs/LAYOUT_BUILDER_P1.md.
"""

from __future__ import annotations

from pathlib import Path

import layout_builder_service

SVC = layout_builder_service
ROOT = Path(__file__).resolve().parents[1]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_builder_page_is_driven_by_the_catalog_and_the_engine_zones() -> None:
    html = _read("templates/layout_builder.html")
    assert '<script src="/static/csrn-broadcast-layout-engine.js' in html
    assert "window.CSRNBroadcastLayoutEngine" in html and "engine.zones" in html
    assert 'fetch("/api/layouts"' in html and 'method: "POST"' in html
    assert "catalog.controls[scene]" in html  # nothing is hard-coded in the page
    assert "beforeunload" in html  # unsaved edits are not lost silently
    assert 'aria-live="polite"' in html
    assert "innerHTML" not in html  # preset names and messages are user data: textContent only


def test_builder_page_and_index_link_to_each_other() -> None:
    assert 'href="/layouts"' in _read("templates/index.html")
    assert 'href="/"' in _read("templates/layout_builder.html")


def test_builder_page_name_rules_match_the_server() -> None:
    html = _read("templates/layout_builder.html")
    assert "/^[A-Za-z0-9][A-Za-z0-9 _.-]{0,39}$/" in html
    assert SVC._valid_preset_name("Game 1.5-b_c") and not SVC._valid_preset_name("a/b") and not SVC._valid_preset_name(" x")
