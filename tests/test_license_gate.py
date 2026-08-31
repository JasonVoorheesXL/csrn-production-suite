"""Round 15 Task B -- the license gate.

Golden requirement: the existing Caledonia install (a source checkout)
must be completely unaffected. Broadcast-control is only held when an
*installed* build has no valid license.
"""

from __future__ import annotations

import pytest

import app as app_module


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(app_module, "pin_is_configured", lambda: True)
    monkeypatch.setitem(app_module.app.config, "TESTING", True)
    with app_module.app.test_client() as test_client:
        with test_client.session_transaction() as session:
            session["authenticated"] = True
        yield test_client


def _licensing(valid: bool, reason: str = "UNLICENSED") -> dict:
    return {"valid": valid, "reason": reason, "license": None}


# --------------------------------------------------------------------------
# GOLDEN: a source checkout (today's Caledonia install) is never gated.
# --------------------------------------------------------------------------


def test_source_checkout_is_never_gated(client, monkeypatch) -> None:
    assert app_module.PRODUCT_PATHS.installed_mode is False
    monkeypatch.setattr(app_module, "_installed_build", lambda: False)
    # Even if licensing somehow reported invalid, a dev checkout must pass.
    monkeypatch.setattr(app_module, "_current_licensing", lambda: _licensing(False))

    home = client.get("/")
    assert home.status_code == 200
    assert b"License required" not in home.data

    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.get_json().get("status") == "ok"


# --------------------------------------------------------------------------
# Installed build, NO valid license -> broadcast-control held, essentials open.
# --------------------------------------------------------------------------


def test_installed_build_without_license_shows_the_screen(client, monkeypatch) -> None:
    monkeypatch.setattr(app_module, "_installed_build", lambda: True)
    monkeypatch.setattr(app_module, "_current_licensing", lambda: _licensing(False))

    home = client.get("/")
    assert home.status_code == 200
    assert b"License required" in home.data

    # broadcast-control API is held
    gated = client.get("/api/state")
    assert gated.status_code == 402
    assert gated.get_json().get("error") == "LICENSE_REQUIRED"


def test_installed_build_without_license_keeps_essentials_reachable(client, monkeypatch) -> None:
    monkeypatch.setattr(app_module, "_installed_build", lambda: True)
    monkeypatch.setattr(app_module, "_current_licensing", lambda: _licensing(False))

    for path in ("/api/health", "/api/licensing/status"):
        response = client.get(path)
        body = response.get_json() if response.is_json else {}
        assert body.get("error") != "LICENSE_REQUIRED", path
        assert response.status_code != 402, path

    overlay = client.get("/overlay")
    assert overlay.status_code != 402


# --------------------------------------------------------------------------
# GOLDEN: installed build WITH a valid license behaves exactly as today.
# (i.e. Caledonia after it eventually moves to a frozen build + is issued
#  a license -- nothing changes behaviourally.)
# --------------------------------------------------------------------------


def test_installed_build_with_valid_license_is_not_gated(client, monkeypatch) -> None:
    monkeypatch.setattr(app_module, "_installed_build", lambda: True)
    monkeypatch.setattr(
        app_module, "_current_licensing", lambda: _licensing(True, "ACTIVE")
    )

    home = client.get("/")
    assert home.status_code == 200
    assert b"License required" not in home.data

    state = client.get("/api/state")
    assert state.status_code != 402


def test_gate_never_wedges_the_app_if_licensing_raises(client, monkeypatch) -> None:
    def _boom():
        raise RuntimeError("licensing backend unavailable")

    monkeypatch.setattr(app_module, "_installed_build", lambda: True)
    monkeypatch.setattr(app_module, "_current_licensing", _boom)

    home = client.get("/")
    assert home.status_code == 200
    assert b"License required" not in home.data
