from __future__ import annotations

from typing import Any

import pytest

import app as app_module
from diagnostics_service import DiagnosticsResult


if not hasattr(app_module, "get_diagnostics_service"):
    pytest.skip(
        "DiagnosticsService routes are not integrated yet.",
        allow_module_level=True,
    )


class StubDiagnosticsService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.diagnostics_payload = {
            "version": "Version X",
            "checks": [{"name": "Configuration", "ok": True}],
        }
        self.readiness_payload = {
            "ready": True,
            "checks": [{"key": "obs", "ok": True}],
        }

    def diagnostics(self) -> DiagnosticsResult:
        self.calls.append(("diagnostics", None))
        return DiagnosticsResult(
            "OK",
            {"diagnostics": self.diagnostics_payload},
        )

    def readiness(self) -> DiagnosticsResult:
        self.calls.append(("readiness", None))
        return DiagnosticsResult(
            "OK",
            {"readiness": self.readiness_payload},
        )


@pytest.fixture
def diagnostics_client(monkeypatch: pytest.MonkeyPatch):
    service = StubDiagnosticsService()
    monkeypatch.setattr(
        app_module,
        "DIAGNOSTICS_SERVICE",
        service,
        raising=False,
    )
    monkeypatch.setattr(app_module, "pin_is_configured", lambda: True)
    monkeypatch.setitem(app_module.app.config, "TESTING", True)
    monkeypatch.setitem(
        app_module.app.config,
        "SECRET_KEY",
        "diagnostics-route-test",
    )
    with app_module.app.test_client() as client:
        with client.session_transaction() as active_session:
            active_session["authenticated"] = True
        yield client, service


def test_diagnostic_status_wrapper_delegates(diagnostics_client) -> None:
    _, service = diagnostics_client
    assert app_module.diagnostic_status() == service.diagnostics_payload
    assert service.calls == [("diagnostics", None)]


def test_readiness_payload_wrapper_delegates(diagnostics_client) -> None:
    _, service = diagnostics_client
    assert app_module.readiness_payload() == service.readiness_payload
    assert service.calls == [("readiness", None)]


def test_diagnostics_endpoint_preserves_payload(diagnostics_client) -> None:
    client, service = diagnostics_client
    response = client.get("/api/diagnostics")
    assert response.status_code == 200
    assert response.get_json() == service.diagnostics_payload
    assert service.calls == [("diagnostics", None)]


def test_readiness_endpoint_preserves_payload(diagnostics_client) -> None:
    client, service = diagnostics_client
    response = client.get("/api/readiness")
    assert response.status_code == 200
    assert response.get_json() == service.readiness_payload
    assert service.calls == [("readiness", None)]
