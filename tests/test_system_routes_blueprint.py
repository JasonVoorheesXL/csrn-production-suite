from __future__ import annotations

from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable

import pytest
from flask import Flask, jsonify, request

from routes.system_routes import (
    SystemRoutesDependencies,
    create_system_blueprint,
)


@dataclass(frozen=True)
class StubResult:
    code: str
    data: dict[str, Any]


class StubConfigurationService:
    def __init__(self) -> None:
        self.read_result = StubResult(
            "OK",
            {"config": {"organization": {"name": "CSRN"}}},
        )
        self.update_result = StubResult(
            "OK",
            {"config": {"organization": {"name": "Updated CSRN"}}},
        )
        self.updates: list[Any] = []

    def read(self) -> StubResult:
        return self.read_result

    def update(self, incoming: Any) -> StubResult:
        self.updates.append(incoming)
        return self.update_result


@pytest.fixture
def system_client():
    configuration = StubConfigurationService()
    calls: dict[str, int] = {
        "diagnostics": 0,
        "state": 0,
        "runtime_load_state": 0,
        "public_state": 0,
        "runtime_state": 0,
        "readiness": 0,
        "journal": 0,
    }

    def require_auth(view: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(view)
        def protected(*args: Any, **kwargs: Any):
            if request.headers.get("X-Test-Auth") != "yes":
                return jsonify({"error": "AUTH_REQUIRED"}), 401
            return view(*args, **kwargs)

        return protected

    def diagnostic_status() -> dict[str, Any]:
        calls["diagnostics"] += 1
        return {"status": "ready"}

    def load_state() -> dict[str, Any]:
        calls["state"] += 1
        return {"private": "hidden", "home_score": 7}

    def load_runtime_state() -> dict[str, Any]:
        calls["runtime_load_state"] += 1
        return {"private": "hidden", "home_score": 9}

    def public_state(state: dict[str, Any]) -> dict[str, Any]:
        calls["public_state"] += 1
        return {"home_score": state["home_score"]}

    def runtime_state(state: dict[str, Any]) -> dict[str, Any]:
        calls["runtime_state"] += 1
        return {"home_score": state["home_score"], "runtime": True}

    def readiness_payload() -> dict[str, Any]:
        calls["readiness"] += 1
        return {"ready": True}

    def load_build_journal() -> list[dict[str, Any]]:
        calls["journal"] += 1
        return [{"build": "V1.13A5A"}]

    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="route-test")
    app.register_blueprint(
        create_system_blueprint(
            SystemRoutesDependencies(
                require_auth=require_auth,
                get_configuration_service=lambda: configuration,
                diagnostic_status=diagnostic_status,
                load_state=load_state,
                load_runtime_state=load_runtime_state,
                public_state=public_state,
                runtime_state=runtime_state,
                readiness_payload=readiness_payload,
                load_build_journal=load_build_journal,
            )
        )
    )
    with app.test_client() as client:
        yield client, app, configuration, calls


def auth_headers() -> dict[str, str]:
    return {"X-Test-Auth": "yes"}


def test_blueprint_registers_preserved_system_urls(system_client) -> None:
    _, app, _, _ = system_client
    rules = {
        (rule.rule, tuple(sorted(rule.methods - {"HEAD", "OPTIONS"})))
        for rule in app.url_map.iter_rules()
    }
    assert ("/api/config", ("GET",)) in rules
    assert ("/api/config", ("POST",)) in rules
    assert ("/api/diagnostics", ("GET",)) in rules
    assert ("/api/state", ("GET",)) in rules
    assert ("/api/runtime-state", ("GET",)) in rules
    assert ("/api/readiness", ("GET",)) in rules
    assert ("/api/build-journal", ("GET",)) in rules
    assert ("/api/health", ("GET",)) in rules


def test_health_route_is_public_fast_and_never_reads_state(system_client) -> None:
    client, _, _, calls = system_client
    response = client.get("/api/health")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["service"] == "csrn"
    assert isinstance(payload["pid"], int)
    assert isinstance(payload["time"], int)
    assert isinstance(payload["uptime_s"], int) and payload["uptime_s"] >= 0
    # The whole point of the endpoint: it must answer without touching the
    # state load path (which can be stuck behind the write lock mid-game).
    assert calls["state"] == 0
    assert calls["runtime_load_state"] == 0
    assert calls["public_state"] == 0
    assert calls["runtime_state"] == 0


def test_state_route_remains_public_and_filters_state(system_client) -> None:
    client, _, _, calls = system_client
    response = client.get("/api/state")
    assert response.status_code == 200
    assert response.get_json() == {"home_score": 7}
    assert calls["state"] == 1
    assert calls["public_state"] == 1


def test_runtime_state_route_remains_public_and_filters_state(system_client) -> None:
    client, _, _, calls = system_client
    response = client.get("/api/runtime-state")
    assert response.status_code == 200
    assert response.get_json() == {"home_score": 9, "runtime": True}
    assert calls["state"] == 0
    assert calls["runtime_load_state"] == 1
    assert calls["runtime_state"] == 1


def test_protected_system_route_requires_authentication(system_client) -> None:
    client, _, _, calls = system_client
    response = client.get("/api/diagnostics")
    assert response.status_code == 401
    assert response.get_json() == {"error": "AUTH_REQUIRED"}
    assert calls["diagnostics"] == 0


def test_get_config_delegates_to_configuration_service(system_client) -> None:
    client, _, _, _ = system_client
    response = client.get("/api/config", headers=auth_headers())
    assert response.status_code == 200
    assert response.get_json()["organization"]["name"] == "CSRN"


def test_update_config_delegates_payload(system_client) -> None:
    client, _, configuration, _ = system_client
    payload = {"organization": {"name": "Updated CSRN"}}
    response = client.post(
        "/api/config",
        json=payload,
        headers=auth_headers(),
    )
    assert response.status_code == 200
    assert response.get_json()["organization"]["name"] == "Updated CSRN"
    assert configuration.updates == [payload]


def test_update_config_maps_missing_payload_error(system_client) -> None:
    client, _, configuration, _ = system_client
    configuration.update_result = StubResult("CONFIG_PAYLOAD_REQUIRED", {})
    response = client.post(
        "/api/config",
        data="null",
        content_type="application/json",
        headers=auth_headers(),
    )
    assert response.status_code == 400
    assert response.get_json() == {"error": "CONFIG_PAYLOAD_REQUIRED"}
    assert configuration.updates == [None]


def test_update_config_maps_invalid_social_url_fields(system_client) -> None:
    client, _, configuration, _ = system_client
    configuration.update_result = StubResult(
        "INVALID_SOCIAL_URL",
        {"fields": {"youtube": "INVALID_URL"}},
    )
    response = client.post(
        "/api/config",
        json={"social": {"youtube": "bad"}},
        headers=auth_headers(),
    )
    assert response.status_code == 400
    assert response.get_json() == {
        "error": "INVALID_SOCIAL_URL",
        "fields": {"youtube": "INVALID_URL"},
    }


def test_diagnostics_route_delegates(system_client) -> None:
    client, _, _, calls = system_client
    response = client.get("/api/diagnostics", headers=auth_headers())
    assert response.status_code == 200
    assert response.get_json() == {"status": "ready"}
    assert calls["diagnostics"] == 1


def test_readiness_route_delegates(system_client) -> None:
    client, _, _, calls = system_client
    response = client.get("/api/readiness", headers=auth_headers())
    assert response.status_code == 200
    assert response.get_json() == {"ready": True}
    assert calls["readiness"] == 1


def test_build_journal_route_delegates(system_client) -> None:
    client, _, _, calls = system_client
    response = client.get("/api/build-journal", headers=auth_headers())
    assert response.status_code == 200
    assert response.get_json() == [{"build": "V1.13A5A"}]
    assert calls["journal"] == 1


