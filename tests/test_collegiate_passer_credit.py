"""Regression coverage for the QB passer credit on the Collegiate Tech
player-spotlight card (e.g. "pass from Brantley Rickard"), added for the
2026-08-28 Friday game.

The receiver stays the card's main photo/headline; the passer gets a
text-only credit line. Backend plumbing (rules_service.py ->
graphics_service.py -> state["player_graphic"]["passer_name"]) is covered
behaviorally in tests/test_rules_service.py -- this file covers the
frontend consumption of that field, which this project's test suite tests
via static source assertions (no node/execjs/playwright harness), matching
the existing pattern for these JS files.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_runtime_surfaces_passer_name_onto_the_player_object() -> None:
    js = read("static/csrn-production-theme-runtime.js")
    assert "passerName: textValue(graphic.passer_name, player.passerName)," in js
    assert "passer_name: textValue(graphic.passer_name, player.passer_name)," in js


def test_player_spotlight_card_renders_passer_credit_line() -> None:
    js = read("static/csrn-broadcast-layout-engine.js")
    assert "function collegiatePasserCredit(player)" in js
    assert '`<em>pass from ${esc(passer)}</em>`' in js
    assert "${collegiatePasserCredit(player)}" in js


def test_passer_credit_has_its_own_scaled_style() -> None:
    css = read("static/csrn-broadcast-layout-engine.css")
    assert ".bl-college-video-copy em{" in css
    assert ".bl-college-player .bl-college-video-copy em{font-size:20px}" in css
