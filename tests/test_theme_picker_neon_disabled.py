"""Round 6 Task B1: Neon is temporarily hidden from the operator's theme
picker. Code stays; it's a reversible hide.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_index_theme_select_has_no_neon_option() -> None:
    html = _read("templates/index.html")
    select = html[html.index('id="csrnPregameThemeSelect"'):]
    select = select[:select.index("</select>")]
    assert 'value="digital_neon"' not in select
    assert "Neon" not in select
    # the other packages are still there
    for value in ("legacy", "friday_night_stadium", "eight_bit_gameday", "heritage_press", "collegiate_traditional"):
        assert f'value="{value}"' in select


def test_pregame_selector_js_disables_neon_reversibly() -> None:
    js = _read("static/csrn-pregame-theme-selector.js")
    assert 'const DISABLED = new Set(["digital_neon"]);' in js
    assert "pruneDisabledOptions()" in js
    # APPROVED (the client-side validity gate) excludes disabled ids
    assert "Object.keys(LABELS).filter(id => !DISABLED.has(id))" in js
    # the now-unreachable "deferred / unvalidated" confirm is gone
    assert "deferred / unvalidated" not in js
    # the LABELS entry is kept so any stale saved state still renders a name
    assert "digital_neon:" in js


def test_production_template_menu_js_disables_neon_reversibly() -> None:
    js = _read("static/csrn-production-template-menu.js")
    assert 'const DISABLED = Object.freeze(new Set(["digital_neon"]));' in js
    assert "SELECTABLE_OPTIONS" in js
    assert "for (const option of SELECTABLE_OPTIONS)" in js
    # OPTIONS still lists it (kept for reference / re-enable)
    assert 'id:"digital_neon"' in js
