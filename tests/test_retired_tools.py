"""Audit round 1 (2026-10-31): the five tools unused all season are hidden from
the menus and pages, their code and data stay, and one Settings switch brings
them back.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
NAV = (ROOT / "static" / "csrn-navigation.js").read_text(encoding="utf-8")
CSS = (ROOT / "static" / "csrn-console-glass.css").read_text(encoding="utf-8")
HIDE_RULE = "html:not(.show-retired) .retired-tool"


def test_menu_marks_theme_manager_packages_and_recaps_retired() -> None:
    entries = dict(
        (key, rest) for key, rest in re.findall(r"\['(\w+)', ('[^']*'[^\]]*)\]", NAV)
    )
    for key in ("themes", "packages", "recaps"):
        assert entries[key].rstrip().endswith("true"), key
    for key in ("pregame", "command", "statistician", "obs", "games", "schools",
                "rosters", "broadcasters", "graphics", "sponsors", "social", "settings",
                "diagnostics"):
        assert not entries[key].rstrip().endswith("true"), key
    assert "if (retired) link.classList.add('retired-tool');" in NAV


def test_caption_and_builder_entry_points_are_tagged() -> None:
    for needle in (
        'command-caption-panel retired-tool"',
        'caption-control-panel retired-tool"',
        '<label class="check-row retired-tool"><input type="checkbox"> Captions source tested',
        '<button class="retired-tool" onclick="window.open(\'/captions\',\'_blank\')">',
        '<div class="editor-actions retired-tool"><a class="button primary" href="/themes">',
        '<div class="editor-actions retired-tool"><a class="button" href="/layouts">',
        # The Theme Manager's own value; the theme on air is picked in Pre-Game Setup.
        '<label class="retired-tool">Active Graphics Theme<input id="cfgTheme"',
    ):
        assert needle in HTML, needle
    # Every remaining Open Captions Preview button lives inside a retired panel.
    command = HTML[HTML.index('command-caption-panel retired-tool'):]
    assert "window.open('/captions'" in command[: command.index("</section>")]


def test_hidden_by_default_and_one_switch_shows_them() -> None:
    assert HIDE_RULE in CSS and HIDE_RULE in NAV
    assert "localStorage.getItem('csrn.showRetiredTools.v1')==='1'" in HTML[: HTML.index("</head>")]
    assert "const RETIRED_STORAGE_KEY = 'csrn.showRetiredTools.v1';" in NAV
    assert 'id="showRetiredTools" type="checkbox" onchange="setShowRetiredTools(this.checked)"' in HTML
    assert "setShowRetired," in NAV and "showRetired," in NAV


def test_retired_code_is_kept() -> None:
    for needle in ('<section id="packagesModule"', "async function loadPackages()",
                   "async function startLiveCaptions()", "'packages'"):
        assert needle in HTML, needle
    for template in ("theme_manager.html", "layout_builder.html", "recap_manager.html"):
        assert (ROOT / "templates" / template).exists(), template
