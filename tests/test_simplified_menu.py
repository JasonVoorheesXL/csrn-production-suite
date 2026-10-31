"""Audit round 2 (2026-10-31): 13 menu items in the same five groups; 12 since
Personnel was removed later the same day.
Statistics becomes the Box Score tab of Statistician, Assets the Media Library
tab of Sponsors, Graphics keeps the automatic player graphic, and Release
Readiness becomes System Check.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
NAV = (ROOT / "static" / "csrn-navigation.js").read_text(encoding="utf-8")
CSS = (ROOT / "static" / "csrn-console-glass.css").read_text(encoding="utf-8")


def _module(module_id: str) -> str:
    start = HTML.index(f'<section id="{module_id}"')
    ends = [HTML.find(marker, start + 10) for marker in ("\n    <section id=", "\n    <div id=")]
    return HTML[start: min(end for end in ends if end != -1)]


def test_menu_has_twelve_items_besides_retired_ones() -> None:
    entries = re.findall(r"\['(\w+)', ('[^']*'[^\]]*)\]", NAV)
    shown = [key for key, rest in entries if not rest.rstrip().endswith("true")]
    assert shown == [
        "pregame", "command", "statistician", "obs",
        "games", "schools", "rosters",
        "graphics", "sponsors",
        "social",
        "settings", "diagnostics",
    ]
    assert "['diagnostics', 'System Check']" in NAV


def test_statistics_and_assets_are_tabs_of_their_neighbours() -> None:
    for module_id, tabs in (
        ("statisticianModule", ("statistician", "statistics")),
        ("statisticsModule", ("statistician", "statistics")),
        ("sponsorsModule", ("sponsors", "assets")),
        ("assetsModule", ("sponsors", "assets")),
    ):
        block = _module(module_id)
        strip = block[block.index('<div class="module-tabs"'):]
        strip = strip[: strip.index("</div>")]
        for key in tabs:
            assert f"onclick=\"showModule('{key}')\"" in strip, (module_id, key)
        assert strip.count('class="active"') == 1, module_id
    assert "const MODULE_MENU_PARENT = {statistics: 'statistician', assets: 'sponsors'};" in HTML
    assert HTML.count("setActive(MODULE_MENU_PARENT[module] || module)") == 2
    assert ".module-tabs button.active" in CSS


def test_graphics_keeps_only_the_player_graphic_in_view() -> None:
    graphics = _module("graphicsModule")
    items = re.findall(r'<article class="graphics-library-item ([^"]*)"', graphics)
    kept = [classes for classes in items if "retired-tool" not in classes]
    assert kept == ["is-available"]
    assert '<h2>Player Identification Master</h2>' in graphics


def test_system_check_drops_rehearsal_and_recap_pieces() -> None:
    diagnostics = _module("diagnosticsModule")
    assert "<h1>System Check</h1>" in diagnostics
    assert 'onclick="loadReleaseReadiness()">Check System</button>' in diagnostics
    assert '<button class="retired-tool" onclick="exportReleaseReport()">' in diagnostics
    assert 'onclick="exportIncidentBundle()">Export Incident Bundle</button>' in diagnostics
    assert "/api/recaps/status" not in HTML
