"""Round 12 Task C: the CSRN_INTERNAL_TOOLS flag gates the internal-only
routes catalogued in docs/internal_only_surfaces.json.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import app as app_module


ROOT = Path(__file__).resolve().parents[1]

GATED_SAMPLES = (
    "/api/diagnostics",
    "/api/runtime-diagnostics",
    "/api/game-day/rehearsals",
    "/api/game-day/release-manifest",
    "/api/deployment/status",
    "/api/deployment/support-bundle",
)
NOT_GATED = (
    "/api/health",
    "/api/config",
    "/api/state",
    "/api/licensing/status",
    "/api/identity/streaming-links",
)


def test_resolver_honours_explicit_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for value in ("1", "true", "YES", "on"):
        monkeypatch.setenv("CSRN_INTERNAL_TOOLS", value)
        assert app_module.internal_tools_enabled() is True
    for value in ("0", "false", "NO", "off"):
        monkeypatch.setenv("CSRN_INTERNAL_TOOLS", value)
        assert app_module.internal_tools_enabled() is False


def test_resolver_default_follows_installed_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CSRN_INTERNAL_TOOLS", raising=False)
    # dev/source checkout -> installed_mode is False -> internal tools on
    assert app_module.PRODUCT_PATHS.installed_mode is False
    assert app_module.internal_tools_enabled() is True


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(app_module, "pin_is_configured", lambda: True)
    monkeypatch.setitem(app_module.app.config, "TESTING", True)
    with app_module.app.test_client() as test_client:
        with test_client.session_transaction() as session:
            session["authenticated"] = True
        yield test_client


def test_disabled_flag_404s_the_internal_routes_only(
    client, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(app_module, "INTERNAL_TOOLS_ENABLED", False)

    for path in GATED_SAMPLES:
        response = client.get(path)
        assert response.status_code == 404, path
        assert response.get_json().get("error") == "INTERNAL_TOOLS_DISABLED", path

    for path in NOT_GATED:
        response = client.get(path)
        # whatever these normally do, it is NOT the internal-tools 404
        body = response.get_json() if response.is_json else {}
        assert body.get("error") != "INTERNAL_TOOLS_DISABLED", path


def test_enabled_flag_lets_the_internal_routes_route_normally(
    client, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(app_module, "INTERNAL_TOOLS_ENABLED", True)
    response = client.get("/api/diagnostics")
    assert response.status_code != 404
    if response.is_json:
        assert response.get_json().get("error") != "INTERNAL_TOOLS_DISABLED"


def test_manifest_documents_the_runtime_flag() -> None:
    manifest = json.loads(
        (ROOT / "docs" / "internal_only_surfaces.json").read_text(encoding="utf-8")
    )
    enforcement = manifest["runtime_enforcement"]
    assert enforcement["flag"] == "CSRN_INTERNAL_TOOLS"
    assert "internal_tools_enabled" in enforcement["resolver"]
    assert "/api/diagnostics" in enforcement["gated_paths"]
    src = (ROOT / "run_core_foundation.py").read_text(encoding="utf-8")
    assert "do NOT include in a commercial build" in src
