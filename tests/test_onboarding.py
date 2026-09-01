"""Round 22: first-run onboarding wizard."""
from __future__ import annotations

from pathlib import Path

import pytest

import app as app_module
import identity_service

ROOT = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------
# identity_service.onboarding_complete flag
# --------------------------------------------------------------------------


def test_fresh_install_template_is_not_onboarded(tmp_path) -> None:
    fresh = identity_service.load_identity_profile(
        tmp_path / "identity_profile.json", existing_install=False
    )
    assert fresh["onboarding_complete"] is False
    assert identity_service.onboarding_complete(fresh) is False


def test_existing_install_template_is_already_onboarded(tmp_path) -> None:
    existing = identity_service.load_identity_profile(
        tmp_path / "identity_profile.json", existing_install=True
    )
    assert existing["onboarding_complete"] is True
    assert identity_service.onboarding_complete(existing) is True


def test_flag_round_trips_through_save(tmp_path) -> None:
    p = tmp_path / "identity_profile.json"
    prof = identity_service.load_identity_profile(p, existing_install=False)
    prof["onboarding_complete"] = True
    identity_service.save_identity_profile(p, prof, existing_install=False)
    reloaded = identity_service.load_identity_profile(p, existing_install=False)
    assert reloaded["onboarding_complete"] is True
    # sections still intact
    assert "organization" in reloaded and "streaming" in reloaded


def test_editing_config_sections_does_not_clobber_the_flag(tmp_path) -> None:
    p = tmp_path / "identity_profile.json"
    identity_service.save_identity_profile(
        p, {"onboarding_complete": True, "organization": {"name": "X"}},
        existing_install=False,
    )
    # a later section-only save (what _persist_identity_sections does)
    current = identity_service.load_identity_profile(p, existing_install=False)
    current["organization"] = {"name": "X", "short_name": "XY"}
    identity_service.save_identity_profile(p, current, existing_install=False)
    assert identity_service.load_identity_profile(p, existing_install=False)["onboarding_complete"] is True


# --------------------------------------------------------------------------
# Routing gate
# --------------------------------------------------------------------------


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setitem(app_module.app.config, "TESTING", True)
    with app_module.app.test_client() as c:
        yield c


def test_seeded_profile_serves_the_normal_control_panel(client, monkeypatch) -> None:
    monkeypatch.setattr(app_module, "_onboarding_incomplete", lambda: False)
    r = client.get("/")
    assert r.status_code == 200
    assert b"Welcome to CSRN Production Suite" not in r.data  # not the wizard


def test_blank_profile_routes_to_the_wizard(client, monkeypatch) -> None:
    monkeypatch.setattr(app_module, "_onboarding_incomplete", lambda: True)
    r = client.get("/")
    assert r.status_code == 200
    assert b"Welcome to CSRN Production Suite" in r.data
    assert b'href="/static/style.css"' in r.data  # reuses the app CSS


def test_wizard_holds_the_rest_of_the_app_but_leaves_essentials_reachable(client, monkeypatch) -> None:
    monkeypatch.setattr(app_module, "_onboarding_incomplete", lambda: True)
    held = client.get("/api/state")
    assert held.status_code == 409
    assert held.get_json().get("error") == "ONBOARDING_REQUIRED"
    for ok_path in ("/api/health", "/static/style.css", "/api/onboarding/context"):
        assert client.get(ok_path).status_code != 409, ok_path


def test_onboarding_incomplete_reads_the_profile_fresh(monkeypatch, tmp_path) -> None:
    p = tmp_path / "identity_profile.json"
    identity_service.save_identity_profile(
        p, {"onboarding_complete": False}, existing_install=False
    )
    monkeypatch.setattr(app_module, "IDENTITY_FILE", p)
    monkeypatch.setattr(app_module, "_EXISTING_INSTALL", False)
    assert app_module._onboarding_incomplete() is True
    identity_service.save_identity_profile(p, {"onboarding_complete": True}, existing_install=False)
    assert app_module._onboarding_incomplete() is False  # no restart needed


# --------------------------------------------------------------------------
# Wizard page structure
# --------------------------------------------------------------------------


def test_wizard_page_has_the_locked_fields_and_both_completion_buttons() -> None:
    html = (ROOT / "templates" / "onboarding.html").read_text(encoding="utf-8")
    assert 'id="orgName"' in html
    assert 'id="sport"' in html            # optional, from the ruleset registry
    assert 'id="schoolName"' in html       # inline text, not a dropdown
    assert 'type="file"' in html and 'id="logoFile"' in html  # file picker, not a path field
    assert 'id="finishBtn"' in html and 'id="skipBtn"' in html
    assert "/api/onboarding/complete" in html
    assert "/api/onboarding/context" in html
    assert "/api/onboarding/logo" in html
    assert 'href="/static/style.css"' in html
