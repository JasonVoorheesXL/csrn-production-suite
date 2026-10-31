"""Audit round 4 (2026-10-31): the app names itself after the station
("<short name> Production Suite") and shows the station's logo; Caledonia
text and the CSRN badge are never used as a fallback, a neutral placeholder is.
"""
from __future__ import annotations

from pathlib import Path

import pytest

import identity_service

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"
PLACEHOLDER = "/static/logo-placeholder.svg"


def test_product_name_and_logo_follow_the_organization() -> None:
    org = {"name": "Westside Sports Network", "short_name": "WSN", "logo_path": "static/organization/wsn.png"}
    assert identity_service.station_product_name(org) == "WSN Production Suite"
    assert identity_service.station_logo_url(org) == "/static/organization/wsn.png"
    assert identity_service.station_product_name({"name": "Westside Sports Network"}) == (
        "Westside Sports Network Production Suite"
    )
    assert identity_service.station_product_name({}) == "Production Suite"
    assert identity_service.station_logo_url({}) == PLACEHOLDER
    assert identity_service.station_logo_url({"logo": "https://cdn.example/logo.png"}) == "https://cdn.example/logo.png"
    assert (ROOT / "static" / "logo-placeholder.svg").exists()


@pytest.mark.parametrize("name", ["index.html", "social_manager.html", "overlay.html", "pregame_universal_overlay.html"])
def test_no_caledonia_fallbacks_or_badge_in_pages(name: str) -> None:
    text = (TEMPLATES / name).read_text(encoding="utf-8")
    assert "/static/csrn-logo.png" not in text
    assert "CaledoniaSRN" not in text
    assert "Caledonia Sports Radio Network" not in text
    assert "CALEDONIA SPORTS RADIO NETWORK" not in text
    assert "Caledonia High School" not in text


def test_pregame_overlay_hides_unset_social_cards_and_names_the_station() -> None:
    text = (TEMPLATES / "pregame_universal_overlay.html").read_text(encoding="utf-8")
    assert "document.querySelector(`.${network}-card`).style.display=handle?'':'none';" in text
    assert "Next on CSRN" not in text
    assert "stationShortName()?`Next on ${esc(stationShortName())}`:'Up Next'" in text


@pytest.fixture
def station_client(monkeypatch):
    import app as app_module

    config = dict(app_module.load_config())
    config["organization"] = {"name": "Westside Sports Network", "short_name": "WSN", "logo_path": ""}
    monkeypatch.setattr(app_module, "load_config", lambda: config)
    with app_module.app.test_client() as client:
        yield client


def test_console_and_social_pages_render_the_station(station_client) -> None:
    body = station_client.get("/").get_data(as_text=True)
    assert "<title>WSN Production Suite — Command Center</title>" in body
    assert '<div class="product-name">WSN PRODUCTION SUITE</div>' in body
    assert body.count('<div class="auth-product">WSN Production Suite</div>') == 2
    assert f'<img class="header-logo" src="{PLACEHOLDER}"' in body
    assert 'const STATION_SHORT_NAME="WSN";' in body
    assert "CSRN Production Suite" not in body.split("<footer", 1)[0]

    social = station_client.get("/social")
    if social.status_code == 200:
        page = social.get_data(as_text=True)
        assert "<title>WSN Production Suite — Social Publishing</title>" in page
        assert f'src="{PLACEHOLDER}" alt="Station logo"' in page


def test_settings_logo_field_reads_and_writes_the_path_in_use() -> None:
    html = (TEMPLATES / "index.html").read_text(encoding="utf-8")
    assert (
        "document.getElementById('cfgOrgLogo').value = c.organization.logo_path || c.organization.logo"
        in html
    )
    assert "      logo_path: document.getElementById('cfgOrgLogo').value.trim(),\n" in html
    app_source = (ROOT / "app.py").read_text(encoding="utf-8")
    persist = app_source[app_source.index("def _persist_identity_sections"):]
    persist = persist[: persist.index("\ndef ")]
    # A configuration save refreshes the in-memory profile (no restart needed).
    assert "IDENTITY_PROFILE = load_identity_profile(" in persist
