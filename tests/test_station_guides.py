"""Operator guides (2026-10-31): the Station Setup Guide for every station plus a
statistician guide per switched-on sport, shipped in static/guides/, listed by
a public /api/guides, and offered in Settings > Guides and at the end of the
first-run wizard.
"""
from __future__ import annotations

from pathlib import Path

import pytest

import guides_catalog

ROOT = Path(__file__).resolve().parents[1]
GUIDES_DIR = ROOT / "static" / "guides"
HTML = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")


def test_shipped_guides_exist_where_the_installer_packs_them() -> None:
    for guide in guides_catalog.GUIDES:
        assert (GUIDES_DIR / guide["file"]).is_file(), guide["file"]


def test_station_guide_plus_one_entry_per_switched_on_sport() -> None:
    rows = guides_catalog.guides_for(["football", "basketball"], GUIDES_DIR)
    assert [row["id"] for row in rows] == ["station-setup", "statistician-football", "statistician-basketball"]
    assert rows[0]["url"] == "/static/guides/station-setup-guide.pdf" and rows[0]["available"]
    assert rows[1]["url"] == "/static/guides/statistician-guide-football.pdf"
    # Never another sport's guide: basketball has none yet.
    assert rows[2]["available"] is False and rows[2]["url"] == ""
    assert "coming" in rows[2]["summary"]


def test_a_sport_switched_off_gets_no_guide() -> None:
    ids = [row["id"] for row in guides_catalog.guides_for(["basketball"], GUIDES_DIR)]
    assert "statistician-football" not in ids


def test_a_missing_pdf_is_never_linked(tmp_path) -> None:
    rows = guides_catalog.guides_for(["football"], tmp_path)
    # No station guide at all; the sport's guide shows as coming soon.
    assert [(row["id"], row["available"], row["url"]) for row in rows] == [("statistician-football", False, "")]


@pytest.fixture
def client(monkeypatch):
    import app as app_module

    monkeypatch.setattr(app_module, "IDENTITY_PROFILE", {**app_module.IDENTITY_PROFILE, "station_sports": {"on": ["football", "softball"]}})
    with app_module.app.test_client() as test_client:
        yield test_client


def test_api_guides_is_public_and_follows_the_sports(client) -> None:
    response = client.get("/api/guides")
    assert response.status_code == 200
    ids = [row["id"] for row in response.get_json()["guides"]]
    assert ids == ["station-setup", "statistician-football", "statistician-softball"]


def test_settings_lists_the_guides_and_opens_them_in_the_app() -> None:
    assert HTML.index("<h2>Guides</h2>") < HTML.index("<h2>Organization</h2>")
    assert '<div id="settingsGuideList" class="settings-guide-list"></div>' in HTML
    assert "if (module === 'settings') { loadConfig(); loadStationSports(); loadGuides(); }" in HTML
    assert "openPdfInApp(${escapeHtml(JSON.stringify(g.url))}" in HTML
    # Ticking a sport refreshes the list.
    assert "await loadSessionContext();loadGuides()" in HTML
