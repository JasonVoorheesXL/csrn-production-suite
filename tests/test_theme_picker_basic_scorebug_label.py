"""Round 6 Task B2: the built-in scorebug is shown to the operator as
"Basic Scorebug", not "Legacy". Internal id stays "legacy".
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_index_theme_option_label_is_basic_scorebug() -> None:
    html = _read("templates/index.html")
    select = html[html.index('id="csrnPregameThemeSelect"'):]
    select = select[:select.index("</select>")]
    assert '<option value="legacy">Basic Scorebug</option>' in select
    assert "Legacy" not in select  # no customer-facing "Legacy" left in the picker


def test_pregame_selector_js_label_is_basic_scorebug_but_id_unchanged() -> None:
    js = _read("static/csrn-pregame-theme-selector.js")
    assert 'legacy: "Basic Scorebug"' in js
    assert 'legacy: "Legacy"' not in js
    # the internal id is untouched
    assert 'let activePackageId = "legacy"' in js
    assert '"legacy"' in js


def test_template_menu_js_label_and_copy_are_basic_scorebug() -> None:
    js = _read("static/csrn-production-template-menu.js")
    assert '{id:"legacy", label:"Basic Scorebug"}' in js
    assert '"Basic Scorebug selected."' in js
    assert "automatic Basic Scorebug fallback" in js
    assert "Basic Scorebug remains the automatic fallback" in js
    assert "Legacy" not in js  # all customer-facing copy switched


def test_internal_legacy_identifiers_are_not_renamed() -> None:
    # id / default / fallback plumbing keeps the "legacy" name -- only labels moved.
    svc = _read("production_template_service.py")
    assert 'DEFAULT_PACKAGE_ID = "legacy"' in svc
    assert '"legacy"' in _read("static/csrn-production-theme-runtime.js")  # currentAlias etc.
