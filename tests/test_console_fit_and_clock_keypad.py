"""Console fixes asked for during the 2026-10-30 game.

* Set Clock is a big 4-digit keypad (M M : S S, left to right) that sets the
  clock on the 4th digit, not a browser prompt.
* Touchback is the first kick option.
* The play form fits one laptop screen, and the slider's direction badge has
  its own lane so it never covers the "CAL 44 (left side)" spot label.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
CSS = (ROOT / "static" / "style.css").read_text(encoding="utf-8")


def test_set_clock_is_a_four_digit_keypad_not_a_prompt() -> None:
    assert "prompt('Set game clock" not in HTML
    assert '<dialog id="clockSetDialog"' in HTML
    for digit in range(10):
        assert f'onclick="clockSetDigit({digit})"' in HTML
    assert HTML.count('<span>&nbsp;</span>', HTML.index('id="clockSetDisplay"'), HTML.index('id="clockSetMessage"')) == 4
    # The 4th digit sends the set; seconds above 59 are refused client-side.
    body = HTML[HTML.index("async function clockSetDigit("):]
    body = body[: body.index("\n")]
    assert "if(clockSetDigits.length<4)return" in body
    assert "if(s1>5)" in body
    assert "action:'set',seconds:(m1*10+m2)*60+s1*10+s2" in body
    # Typing on the keyboard works the same as the keypad.
    assert re.search(r"keydown.*clockSetDialog.*clockSetDigit\(Number\(e\.key\)\)", HTML)


def test_touchback_is_the_first_play_option() -> None:
    grid = HTML[HTML.index('<div class="play-option-grid">'):]
    first_label = re.search(r'<label id="(\w+)"', grid).group(1)
    assert first_label == "playTouchbackWrap"
    assert HTML.count('id="playTouchbackWrap"') == 1


def test_drive_indicator_sits_in_the_axis_row() -> None:
    assert '<div class="field-axis"><span>LEFT GOAL</span><div id="playDriveIndicator" class="drive-indicator">' in HTML


def test_direction_badge_has_its_own_lane_below_the_spot_label() -> None:
    assert '"title typed btn label" "lane lane lane lane" "range range range range"' in CSS
    rule = re.search(r"#playEntryModal \.slider-direction-badge\{([^}]*)\}", CSS).group(1)
    assert "grid-area:lane" in rule and "position:relative" in rule
    # Scoped to the play form; the edit-play spotter keeps its own layout.
    assert re.search(r"(?m)^#playEntryModal \.spot-control\{display:grid", CSS)
