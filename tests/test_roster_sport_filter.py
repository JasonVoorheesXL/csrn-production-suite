"""The Rosters page's sport dropdown (Jason, 2026-11-02): pick which group of rosters
to work on. Driven in a throwaway app; these pin the wiring."""

from __future__ import annotations

from pathlib import Path

INDEX = (Path(__file__).resolve().parents[1] / "templates" / "index.html").read_text(encoding="utf-8")


def test_dropdown_sits_on_the_list_and_filters_it() -> None:
    assert 'id="rosterSportFilter" onchange="setRosterSportFilter(this.value)"' in INDEX
    assert "String(r.sport||'').toLowerCase()===sport.toLowerCase()" in INDEX
    assert "fillRosterSportFilter();\n  renderRosterList();" in INDEX


def test_saved_choice_survives_blocked_browser_storage() -> None:
    assert "function rosterSportFilterValue(){try{" in INDEX
    assert "function setRosterSportFilter(value){try{" in INDEX


def test_app_wide_sport_locks_it_and_new_rosters_follow_the_choice() -> None:
    assert "select.disabled=Boolean(locked)" in INDEX
    assert "rosterSportSelect.value=contextRosterSport||document.getElementById('rosterSportFilter').value||'Football'" in INDEX


def test_list_tells_boys_from_girls() -> None:
    assert "${escapeHtml(r.division||'')} ${escapeHtml(r.sport)}" in INDEX
