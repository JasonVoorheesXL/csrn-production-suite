"""Flip Field (2026-10-30 game): the coin toss had Caledonia receiving with
their backs to the clock, but the teams lined up at the other ends. The
operator flipped the arrow and then moved the ball by hand. Flip Field does
both in one confirm: both directions flip and the ball keeps its yard line.
The server side (ball="yard_line" mirrors the spot) is covered in
tests/test_drive_direction_safeguards.py.
"""
from __future__ import annotations

from pathlib import Path

HTML = (Path(__file__).resolve().parents[1] / "templates" / "index.html").read_text(encoding="utf-8")


def test_drive_direction_card_has_a_flip_field_button() -> None:
    card = HTML[HTML.index("<h2>Drive Direction</h2>"):]
    card = card[: card.index("</article>")]
    assert '<button id="flipFieldButton" class="primary" onclick="flipField()"' in card
    assert "⇄ Flip Field" in card


def test_stat_console_field_toolbar_has_a_flip_field_button() -> None:
    assert '<button id="statisticianFlipField" onclick="flipField()"' in HTML


def test_flip_field_flips_the_possession_teams_direction_and_keeps_the_yard_line() -> None:
    body = HTML[HTML.index("async function flipField(){"):]
    body = body[: body.index("\n")]
    assert "const direction=flippedDirection(String(currentState?.[`${team}_direction`]||'right').toLowerCase())" in body
    assert "await askChoice('Flip the field?'" in body
    assert "if(choice!=='flip')return" in body
    assert "GameStateManager.mutate('/api/field-direction',{team,direction,ball:'yard_line'})" in body
