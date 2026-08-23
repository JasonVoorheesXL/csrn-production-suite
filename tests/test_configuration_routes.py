from __future__ import annotations

from typing import Any

import pytest

import app as app_module
from configuration_service import ConfigurationResult


if not hasattr(app_module, "get_configuration_service"):
    pytest.skip(
        "ConfigurationService routes are not integrated yet.",
        allow_module_level=True,
    )


class StubConfigurationService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.config = {
            "organization": {"name": "CSRN"},
            "application": {
                "version": "Version 1.13.0-alpha.4n — Configuration Service",
                "build": "V1.13A4N-CONFIGURATION-SERVICE",
            },
        }
        self.update_result = ConfigurationResult(
            "OK",
            {"config": self.config},
        )

    def read(self) -> ConfigurationResult:
        self.calls.append(("read", None))
        return ConfigurationResult("OK", {"config": self.config})

    def update(self, payload: Any) -> ConfigurationResult:
        self.calls.append(("update", payload))
        return self.update_result


@pytest.fixture
def configuration_client(monkeypatch: pytest.MonkeyPatch):
    service = StubConfigurationService()
    monkeypatch.setattr(
        app_module,
        "CONFIGURATION_SERVICE",
        service,
        raising=False,
    )
    monkeypatch.setattr(app_module, "pin_is_configured", lambda: True)
    monkeypatch.setitem(app_module.app.config, "TESTING", True)
    monkeypatch.setitem(
        app_module.app.config,
        "SECRET_KEY",
        "configuration-route-test",
    )

    with app_module.app.test_client() as client:
        with client.session_transaction() as active_session:
            active_session["authenticated"] = True
        yield client, service


def test_get_config_preserves_object_contract(configuration_client) -> None:
    client, service = configuration_client
    response = client.get("/api/config")
    assert response.status_code == 200
    assert response.get_json() == service.config
    assert service.calls == [("read", None)]


def test_update_config_delegates_payload_and_returns_config(
    configuration_client,
) -> None:
    client, service = configuration_client
    payload = {"organization": {"name": "PossumFrog"}}
    response = client.post("/api/config", json=payload)
    assert response.status_code == 200
    assert response.get_json() == service.config
    assert service.calls == [("update", payload)]


def test_update_config_maps_invalid_social_fields(configuration_client) -> None:
    client, service = configuration_client
    service.update_result = ConfigurationResult(
        "INVALID_SOCIAL_URL",
        {"fields": {"facebook": "Expected a valid facebook URL"}},
    )
    response = client.post(
        "/api/config",
        json={"social": {"facebook": "https://example.com"}},
    )
    assert response.status_code == 400
    assert response.get_json() == {
        "error": "INVALID_SOCIAL_URL",
        "fields": {"facebook": "Expected a valid facebook URL"},
    }


def test_update_config_rejects_non_object_payload(configuration_client) -> None:
    client, service = configuration_client
    service.update_result = ConfigurationResult("CONFIG_PAYLOAD_REQUIRED")
    response = client.post("/api/config", json=["not", "an", "object"])
    assert response.status_code == 400
    assert response.get_json() == {"error": "CONFIG_PAYLOAD_REQUIRED"}
    assert service.calls == [("update", ["not", "an", "object"])]


