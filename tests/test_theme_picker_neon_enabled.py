"""Neon redesign checkpoint 4: Neon is back in every theme picker (it was hidden by Round 6 Task B1 while the
standalone build was retired). The hide mechanism stays as an empty set, so any package can be hidden again."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_index_theme_select_offers_neon_and_every_other_package() -> None:
    html = _read("templates/index.html")
    select = html[html.index('id="csrnPregameThemeSelect"'):]
    select = select[:select.index("</select>")]
    for value in ("legacy", "friday_night_stadium", "eight_bit_gameday", "heritage_press", "collegiate_traditional"):
        assert f'value="{value}"' in select
    assert '<option value="digital_neon">Neon</option>' in select


def test_pregame_selector_js_no_longer_disables_anything() -> None:
    js = _read("static/csrn-pregame-theme-selector.js")
    assert "const DISABLED = new Set([]);" in js
    assert 'digital_neon: "Neon"' in js
    assert "Object.keys(LABELS).filter(id => !DISABLED.has(id))" in js  # the validity gate is still the DISABLED filter
    assert "pruneDisabledOptions()" in js


def test_production_template_menu_js_no_longer_disables_anything() -> None:
    js = _read("static/csrn-production-template-menu.js")
    assert "const DISABLED = Object.freeze(new Set([]));" in js
    assert 'id:"digital_neon", label:"Neon"' in js
    assert "for (const option of SELECTABLE_OPTIONS)" in js


def test_the_three_hide_lists_agree() -> None:
    py = _read("production_template_service.py")
    assert "DISABLED_PACKAGE_IDS: frozenset[str] = frozenset()" in py
    assert "digital_neon" in py.split("APPROVED_PACKAGE_IDS = frozenset(")[1].split(")")[0]


def test_the_theme_manager_previews_neon_with_the_collegiate_renderer() -> None:
    """Theme Manager's scorebug preview used the retired 'neon' angular-wings layout. Neon is Collegiate's
    structure now, so the preset maps to the Collegiate preview layout (the old renderer stays for the
    layout-coverage tests, but no preset points at it)."""
    theme = _read("theme_service.py")
    block = theme.split('"digital_neon": {')[1].split('"collegiate_traditional": {')[0]
    assert '"layouts": {"scorebug": "collegiate"}' in block and '"name": "Neon"' in block
    assert 'digital_neon: "collegiate"' in _read("static/csrn-scorebug-engine.js")
