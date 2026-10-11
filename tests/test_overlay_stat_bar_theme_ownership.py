"""The legacy #statBar must stand down while a production theme owns the scorebug.

2026-10-09 Columbus @ Caledonia (collegiate_traditional): the ribbon showed above
the themed scorebug card in pregame and live, in OBS and in a plain /overlay
preview. Its only condition was `scorebug_visible && stats exist`; the theme
hides the legacy #scorebug and #eventTicker but nothing told #statBar, and only
Neon / a layout-hidden ticker had a CSS patch for it.

No JS test runner here, so like test_layout_builder_p1.py this pins the source;
the behaviour was checked in a real browser against an isolated app instance.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OVERLAY = (ROOT / "templates" / "overlay.html").read_text(encoding="utf-8")
RUNTIME = (ROOT / "static" / "csrn-production-theme-runtime.js").read_text(encoding="utf-8")
THEME_CLASS = "csrn-production-theme-scorebug-active"


def _sync_function() -> str:
    start = OVERLAY.index("function syncStatBarVisibility(){")
    return OVERLAY[start:OVERLAY.index("\n}", start)]


def test_stat_bar_visibility_requires_the_legacy_scorebug_to_own_the_screen() -> None:
    body = _sync_function()
    assert f"document.documentElement.classList.contains('{THEME_CLASS}')" in body
    assert "const visible=overlayScorebugVisible&&!themeOwnsScorebug&&statBarHasStats;" in body
    assert "statBar.classList.toggle('hidden',!visible);" in body


def test_stat_bar_is_only_toggled_through_the_shared_condition() -> None:
    # The old inline `overlayScorebugVisible&&segments.length>0` toggle is gone.
    assert "overlayScorebugVisible&&segments.length>0" not in OVERLAY
    assert OVERLAY.count("statBar.classList.toggle('hidden'") == 1
    assert "statBarHasStats=segments.length>0;" in OVERLAY


def test_stat_bar_is_resynced_on_every_runtime_state_poll() -> None:
    # The stats fetch runs every 6s; the 500ms runtime-state poll re-evaluates so a
    # theme takeover or scorebug-off hides the ribbon without waiting for it.
    refresh = OVERLAY[OVERLAY.index("async function refresh(){"):OVERLAY.index("async function refreshStatBar(){")]
    assert "syncStatBarVisibility();" in refresh


def test_stat_bar_still_starts_hidden_and_the_theme_class_name_matches_the_runtime() -> None:
    assert '<div id="statBar" class="hidden">' in OVERLAY
    assert f'const SCORE_ACTIVE_CLASS = "{THEME_CLASS}";' in RUNTIME
