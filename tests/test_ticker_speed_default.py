"""Default ticker scroll speed.

Operator review: "slow" (36 px/s in csrn-production-theme-runtime.js) reads
as a crawl on broadcast. New broadcasts now default to "fast" (189 px/s);
the Scroll Speed control still offers every preset, and a broadcast that
already has a saved ticker_speed keeps it.
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
    assert (very_slow, slow, normal, fast) == (24, 36, 84, 189)
    # the new default resolves to the fastest preset
    assert fast == 189


def test_scroll_speed_control_still_offers_every_preset() -> None:
    index = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    for value in ("very_slow", "slow", "normal", "fast"):
        assert f'value="{value}"' in index
