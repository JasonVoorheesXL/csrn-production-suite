"""Box Score > Top Performers (2026-10-31): up to three per team per category,
only players who recorded that stat, placed with the team stats."""
from __future__ import annotations

import re
from pathlib import Path

HTML = (Path(__file__).resolve().parents[1] / "templates" / "index.html").read_text(encoding="utf-8")


def test_section_sits_with_the_team_stats() -> None:
    totals = HTML.index('<div id="statisticsTeamTotals" class="statistics-team-totals"></div>')
    top = HTML.index('<div id="statisticsTopPerformers" class="statistics-top-performers"></div>')
    production = HTML.index("<h2>Individual Production</h2>")
    assert totals < top < production
    assert "    renderTopPerformers();\n" in HTML


def test_three_at_most_and_only_players_with_the_stat() -> None:
    block = HTML[HTML.index("function topPerformersFor(players,team,category){"):]
    block = block[: block.index("\n}\n")]
    assert "p.team===team&&category.has(p)" in block
    assert ".slice(0,3)" in block
    labels = re.findall(r"\{label:'([A-Za-z]+)'", HTML[HTML.index("const TOP_PERFORMER_CATEGORIES=["):])
    assert labels[:8] == ["Passing", "Rushing", "Receiving", "Scoring", "Sacks",
                          "Interceptions", "Returns", "Kicking"]
    assert "label:'Tackles'" not in HTML
    # A category nobody has recorded is left out.
    assert "if(!columns.some(rows=>rows.length))return '';" in HTML
