"""Default ticker scroll speed.

New broadcasts start on "normal" (76 px/s in csrn-production-theme-
runtime.js). The Scroll Speed control still offers every preset, and a
broadcast that already has a saved ticker_speed keeps it -- the default only
fills in a key that is missing.

History of the default, so the reasoning is not mistaken for current fact:
"slow" (originally 36 px/s) read as a crawl on broadcast, so it was changed to
"fast" (originally 189 px/s, commit 2e825df). "fast" has since been judged too
quick and the default is now "normal" (2026-09, football incident round). Only
the default moved: the preset values (very_slow 22 / slow 32 / normal 76 /
fast 170) and the control's preset list are unchanged.

The preset px/s numbers were retuned 24/36/84/189 -> 22/32/76/170 in commit
9095cf6, alongside a fix to the crawl-speed formula: the old
`Math.max(18, distance/pixelsPerSecond)` clamped the scroll DURATION, which
silently sped the ticker up as content grew instead of just taking longer per
pass. The fix keeps a minimum on-screen cycle time by extending the pause
dwell at each end instead (see the comment at tickerSpeed()'s call site in
csrn-production-theme-runtime.js).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import app
from core_repositories import StateRepository
from persistence_engine import JsonPersistenceEngine
from state_service import StateService

ROOT = Path(__file__).resolve().parents[1]

PRESETS = {"very_slow": 22, "slow": 32, "normal": 76, "fast": 170}


def _runtime_speed_map() -> dict[str, int]:
    js = (ROOT / "static" / "csrn-production-theme-runtime.js").read_text(encoding="utf-8")
    m = re.search(r"\{very_slow:(\d+), slow:(\d+), normal:(\d+), fast:(\d+)\}", js)
    assert m, "tickerSpeed() preset map not found"
    return dict(zip(("very_slow", "slow", "normal", "fast"), (int(x) for x in m.groups())))


def _load_saved(tmp_path: Path, saved: dict) -> dict:
    """Load a saved state file the way the app does (defaults merged under it)."""
    path = tmp_path / "state.json"
    path.write_text(json.dumps(saved), encoding="utf-8")
    engine = JsonPersistenceEngine(tmp_path / "bk", tmp_path / "q")
    return StateRepository(engine, path, app.DEFAULT_STATE).load()


def test_default_state_ticker_speed_is_normal() -> None:
    assert app.DEFAULT_STATE["ticker_speed"] == "normal"


def test_default_resolves_to_the_normal_preset_in_the_theme_runtime() -> None:
    speeds = _runtime_speed_map()
    assert speeds[app.DEFAULT_STATE["ticker_speed"]] == 76


def test_preset_values_are_unchanged() -> None:
    """Only the default moved; the px/s presets themselves must not."""
    assert _runtime_speed_map() == PRESETS


def test_scroll_speed_control_still_offers_every_preset() -> None:
    index = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    for value in ("very_slow", "slow", "normal", "fast"):
        assert f'value="{value}"' in index


def test_a_saved_ticker_speed_is_kept_when_the_state_is_loaded(tmp_path: Path) -> None:
    """The default only fills a missing key. A broadcast that already has a
    saved ticker_speed -- any preset, including the old default -- keeps it."""
    for saved_speed in PRESETS:
        loaded = _load_saved(tmp_path, {"broadcast_id": "G", "ticker_speed": saved_speed})
        assert loaded["ticker_speed"] == saved_speed, saved_speed


def test_a_saved_ticker_speed_is_kept_by_state_normalization() -> None:
    service = StateService(
        load_raw=lambda: {}, replace_raw=lambda s: dict(s), default_state=lambda: dict(app.DEFAULT_STATE)
    )
    for saved_speed in PRESETS:
        assert service.normalize({"broadcast_id": "G", "ticker_speed": saved_speed})["ticker_speed"] == saved_speed
    # a state with no saved value picks up the new default
    assert service.normalize({"broadcast_id": "G"})["ticker_speed"] == "normal"


def test_a_saved_fast_broadcast_stays_fast_after_the_default_change(tmp_path: Path) -> None:
    """The concrete regression to guard: every broadcast created under the old
    default has "fast" saved. It must not silently become "normal"."""
    loaded = _load_saved(tmp_path, {"broadcast_id": "OLD-GAME", "ticker_speed": "fast"})
    assert loaded["ticker_speed"] == "fast"
    assert app.DEFAULT_STATE["ticker_speed"] == "normal"


def test_resetting_game_data_starts_over_on_the_default_speed() -> None:
    """reset_data() rebuilds from default_state() and preserves only its listed
    fields; ticker_speed is not one of them, so a reset/new game starts on the
    default -- the same rule that makes the default apply to "new broadcasts"."""
    from contextlib import nullcontext

    from game_operations_service import GameOperationsService

    assert "ticker_speed" not in GameOperationsService.RESET_PRESERVED_FIELDS
    store = {"state": {**app.DEFAULT_STATE, "broadcast_id": "G", "ticker_speed": "fast"}}
    service = GameOperationsService(
        load_state=lambda: store["state"], save_state=lambda v: store.update(state=dict(v)),
        default_state=lambda: dict(app.DEFAULT_STATE), push_history=lambda s: None,
        source_allowed=lambda s, source: True, locked_payload=lambda s: {},
        update_linked_status=lambda *a: None, load_config=lambda: {},
        command_scorebug_visibility=lambda visible: None, transaction_lock=nullcontext(),
    )
    assert service.reset_data({}).ok
    assert store["state"]["ticker_speed"] == "normal"
