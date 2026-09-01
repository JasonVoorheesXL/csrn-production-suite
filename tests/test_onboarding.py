"""Round 22: first-run onboarding wizard."""
from __future__ import annotations

import copy
import io
import json
from pathlib import Path

import pytest
from werkzeug.datastructures import FileStorage

import app as app_module
import identity_service
import license_service as ls
import pregame_presentation
from entitlement_service import EntitlementService
from product_paths import PRODUCT_ID, resolve_product_paths
from school_service import SchoolService

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


# --------------------------------------------------------------------------
# Backend wiring: _complete_onboarding writes through the existing paths
# --------------------------------------------------------------------------


class _MemStore:
    def __init__(self) -> None:
        self.schools: list[dict] = []
        self.logos: list[dict] = []

    def load_schools(self) -> list[dict]:
        return copy.deepcopy(self.schools)

    def save_schools(self, schools: list[dict], *, force: bool = False) -> None:
        self.schools = copy.deepcopy(schools)

    def load_logos(self) -> list[dict]:
        return copy.deepcopy(self.logos)

    def save_logos(self, logos: list[dict]) -> None:
        self.logos = copy.deepcopy(logos)


@pytest.fixture
def wiring(monkeypatch, tmp_path):
    ident = tmp_path / "identity_profile.json"
    identity_service.save_identity_profile(
        ident, {"onboarding_complete": False}, existing_install=False
    )
    monkeypatch.setattr(app_module, "IDENTITY_FILE", ident)
    monkeypatch.setattr(app_module, "_EXISTING_INSTALL", False)

    store = _MemStore()
    school_service = SchoolService(
        load_schools=store.load_schools,
        save_schools=store.save_schools,
        load_logos=store.load_logos,
        save_logos=store.save_logos,
    )
    monkeypatch.setattr(app_module, "get_school_service", lambda: school_service)

    original_profile = app_module.IDENTITY_PROFILE
    yield {"identity_file": ident, "store": store, "school_service": school_service}
    app_module.IDENTITY_PROFILE = original_profile


def _profile(wiring) -> dict:
    return identity_service.load_identity_profile(
        wiring["identity_file"], existing_install=False
    )


def test_org_name_only_submission_completes_onboarding(wiring) -> None:
    ok, code, message = app_module._complete_onboarding(
        {"org_name": "Falcon Broadcast Network"}
    )
    assert ok, (code, message)
    profile = _profile(wiring)
    assert profile["onboarding_complete"] is True
    assert profile["organization"]["name"] == "Falcon Broadcast Network"
    assert app_module._onboarding_incomplete() is False


def test_org_name_is_required_unless_skipping(wiring) -> None:
    ok, code, _ = app_module._complete_onboarding({"org_name": "   "})
    assert not ok
    assert code == "ORG_NAME_REQUIRED"
    assert app_module._onboarding_incomplete() is True


def test_skip_for_now_also_completes_onboarding(wiring) -> None:
    ok, code, message = app_module._complete_onboarding({"skip": True})
    assert ok, (code, message)
    assert _profile(wiring)["onboarding_complete"] is True
    assert app_module._onboarding_incomplete() is False


def test_inline_school_name_creates_a_real_school_record(wiring) -> None:
    ok, code, message = app_module._complete_onboarding(
        {"org_name": "Test Org", "school_name": "Riverside High School"}
    )
    assert ok, (code, message)
    schools = wiring["store"].schools
    assert len(schools) == 1
    assert schools[0]["official_name"] == "Riverside High School"
    assert schools[0].get("id")
    # and it is wired in as the home school default
    assert _profile(wiring)["broadcast_defaults"]["home_school_id"] == schools[0]["id"]


def test_optional_sport_is_recorded_when_supplied(wiring) -> None:
    ok, *_ = app_module._complete_onboarding({"org_name": "Test Org", "sport": "football"})
    assert ok
    assert _profile(wiring)["broadcast_defaults"]["sport"] == "Football"


def test_completing_twice_is_refused_by_the_route(wiring) -> None:
    with app_module.app.test_client() as client:
        first = client.post("/api/onboarding/complete", json={"org_name": "Test Org"})
        assert first.status_code == 200
        second = client.post("/api/onboarding/complete", json={"org_name": "Other"})
        assert second.status_code == 409
        assert second.get_json().get("error") == "ALREADY_ONBOARDED"


# --------------------------------------------------------------------------
# Logo handler lands the file in the one asset location
# --------------------------------------------------------------------------


def test_logo_upload_lands_in_the_identity_profile_asset_location(monkeypatch, tmp_path) -> None:
    dest = tmp_path / "organization"
    monkeypatch.setattr(pregame_presentation, "_ORG_LOGO_DIR", dest)
    upload = FileStorage(
        stream=io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"0" * 64),
        filename="our-logo.png",
        content_type="image/png",
    )
    status, body = pregame_presentation.save_organization_logo(upload)
    assert status == 200
    assert body["logo_path"] == "/static/organization/organization-logo.png"
    assert (dest / "organization-logo.png").is_file()


def test_logo_upload_rejects_a_non_image(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(pregame_presentation, "_ORG_LOGO_DIR", tmp_path / "organization")
    upload = FileStorage(stream=io.BytesIO(b"nope"), filename="notes.txt")
    status, body = pregame_presentation.save_organization_logo(upload)
    assert status == 400
    assert body["error"] == "INVALID_LOGO_TYPE"


# --------------------------------------------------------------------------
# License gate screen: a real signed license, uploaded through the gate,
# unlocks the app.
# --------------------------------------------------------------------------


_LICENSE_SEED = bytes(range(7, 39))  # not the placeholder, not the wrong-key fixture


def _signed_license() -> dict:
    return ls.sign_license(
        {
            "product_id": PRODUCT_ID,
            "license_id": "onboarding-e2e",
            "status": "active",
            "customer": "Riverside Broadcast",
            "issued_at": 1,
            "expires_at": 0,
            "features": sorted(EntitlementService.CORE_FEATURES),
            "sports": ["football"],
        },
        _LICENSE_SEED,
    )


@pytest.fixture
def gate_client(monkeypatch, tmp_path):
    # An installed build with no license yet, its EntitlementService pointed
    # at a scratch license file, verifying against a test key.
    paths = resolve_product_paths(
        tmp_path / "app",
        env={"CSRN_RUNTIME_ROOT": str(tmp_path / "runtime")},
        frozen=False,
    )
    assert paths.installed_mode is True
    service = EntitlementService(
        paths=paths, verifier=ls.verify_license, clock=lambda: 1_000
    )
    monkeypatch.setattr(ls, "LICENSE_PUBLIC_KEY_HEX", ls.ed25519_publickey(_LICENSE_SEED).hex())
    monkeypatch.setattr(app_module, "ENTITLEMENT_SERVICE", service)
    monkeypatch.setattr(app_module, "_installed_build", lambda: True)
    monkeypatch.setattr(app_module, "_onboarding_incomplete", lambda: False)
    monkeypatch.setitem(app_module.app.config, "TESTING", True)
    with app_module.app.test_client() as client:
        yield client


def test_signed_license_uploaded_through_the_gate_unlocks_the_app(gate_client) -> None:
    # held before the license is installed
    assert gate_client.get("/api/state").status_code == 402
    assert b"License required" in gate_client.get("/").data

    signed = _signed_license()
    response = gate_client.post(
        "/api/licensing/install-file",
        data={"license": (io.BytesIO(json.dumps(signed).encode("utf-8")), "license.json")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.get_json()["status"] == "LICENSE_INSTALLED"

    # gate lifted, no restart
    assert gate_client.get("/api/state").status_code != 402
    assert b"License required" not in gate_client.get("/").data


def test_gate_upload_rejects_a_file_that_is_not_json(gate_client) -> None:
    response = gate_client.post(
        "/api/licensing/install-file",
        data={"license": (io.BytesIO(b"this is not a license"), "junk.json")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    assert response.get_json()["status"] == "LICENSE_FILE_UNREADABLE"
    assert gate_client.get("/api/state").status_code == 402  # still held


def test_gate_upload_with_no_file_is_a_clean_400(gate_client) -> None:
    response = gate_client.post(
        "/api/licensing/install-file",
        data={},
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    assert response.get_json()["status"] == "LICENSE_FILE_REQUIRED"


def test_gate_upload_rejects_a_license_signed_by_the_wrong_key(gate_client, monkeypatch) -> None:
    # verifier now expects a different key than the one the license is signed with
    monkeypatch.setattr(ls, "LICENSE_PUBLIC_KEY_HEX", ls.ed25519_publickey(bytes(range(9, 41))).hex())
    response = gate_client.post(
        "/api/licensing/install-file",
        data={"license": (io.BytesIO(json.dumps(_signed_license()).encode("utf-8")), "license.json")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 409
    assert response.get_json()["status"] == "SIGNATURE_INVALID"
    assert gate_client.get("/api/state").status_code == 402
