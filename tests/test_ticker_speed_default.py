"""Default ticker scroll speed.

Operator review: "slow" (originally 36 px/s in csrn-production-theme-
runtime.js) reads as a crawl on broadcast. New broadcasts now default to
"fast" (originally 189 px/s); the Scroll Speed control still offers every
preset, and a broadcast that already has a saved ticker_speed keeps it.

Preset values retuned 24/36/84/189 -> 22/32/76/170 in commit 9095cf6
("Checkpoint: owner's in-progress work"), alongside a fix to the
crawl-speed formula itself: the old `Math.max(18, distance/pixelsPerSecond)`
clamped the scroll DURATION, which silently sped the ticker up as content
grew instead of just taking longer per pass. The fix keeps a minimum
on-screen cycle time by extending the pause dwell at each end instead (see
the comment at tickerSpeed()'s call site in csrn-production-theme-
runtime.js). "fast" is still the fastest preset and still the default --
only the underlying px/s numbers moved.
"""

from __future__ import annotations

import re
from pathlib import Path

import app

ROOT = Path(__file__).resolve().parents[1]


def test_default_state_ticker_speed_is_fast() -> None:
    assert app.DEFAULT_STATE["ticker_speed"] == "fast"


def test_fast_preset_exists_in_the_theme_runtime_speed_map() -> None:
    js = (ROOT / "static" / "csrn-production-theme-runtime.js").read_text(encoding="utf-8")
    m = re.search(r"\{very_slow:(\d+), slow:(\d+), normal:(\d+), fast:(\d+)\}", js)
    assert m, "tickerSpeed() preset map not found"
    very_slow, slow, normal, fast = (int(x) for x in m.groups())
    assert (very_slow, slow, normal, fast) == (22, 32, 76, 170)
    # the new default still resolves to the fastest preset
    assert fast == 170


def test_scroll_speed_control_still_offers_every_preset() -> None:
    index = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    for value in ("very_slow", "slow", "normal", "fast"):
        assert f'value="{value}"' in index
