from __future__ import annotations

from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable

import pytest
from flask import Flask, jsonify, request

from routes.obs_routes import OBSRoutesDependencies, create_obs_blueprint


@dataclass(frozen=True)
class StubResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)


class StubOBSService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.status_result = StubResult(
            "OK",
            {"status": {"reachable": False, "error": "not tested"}},
        )
        self.test_result = StubResult(
            "OK",
            {"obs": {"reachable": True, "authenticated": True}},
        )
        self.scorebug_result = StubResult(
            "OK",
            {"obs": {"scene": "Program", "visible": True}},
        )
        self.mode_result = StubResult(
            "OK",
            {
                "state": {"visual_mode": "halftime"},
                "obs": {"scene": "Halftime"},
            },
        )

    def status(self) -> StubResult:
        self.calls.append(("status", None))
        return self.status_result

    def test_connection(self) -> StubResult:
        self.calls.append(("test_connection", None))
        return self.test_result

    def scorebug_visibility(self, visible: Any) -> StubResult:
        self.calls.append(("scorebug_visibility", visible))
        return self.scorebug_result

    def program_visual_mode(self, mode: Any) -> StubResult:
        self.calls.append(("program_visual_mode", mode))
        return self.mode_result


@pytest.fixture
def obs_client():
    service = StubOBSService()

    def require_auth(view: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(view)
        def protected(*args: Any, **kwargs: Any):
            if request.headers.get("X-Test-Auth") != "yes":
                return jsonify({"error": "AUTH_REQUIRED"}), 401
            return view(*args, **kwargs)

        return protected

    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="obs-route-test")
    app.register_blueprint(
        create_obs_blueprint(
            OBSRoutesDependencies(
                require_auth=require_auth,
                get_obs_service=lambda: service,
            )
        )
    )
    with app.test_client() as client:
        yield client, app, service


def auth_headers() -> dict[str, str]:
    return {"X-Test-Auth": "yes"}


def test_obs_blueprint_registers_preserved_urls(obs_client) -> None:
    _, app, _ = obs_client
    rules = {
        (rule.rule, tuple(sorted(rule.methods - {"HEAD", "OPTIONS"})))
        for rule in app.url_map.iter_rules()
    }
    assert ("/api/obs/status", ("GET",)) in rules
    assert ("/api/obs/test", ("POST",)) in rules
    assert ("/api/obs/scorebug-visibility", ("POST",)) in rules
    assert ("/api/obs/program-visual-mode", ("POST",)) in rules


def test_obs_routes_require_authentication(obs_client) -> None:
    client, _, service = obs_client
    response = client.get("/api/obs/status")
    assert response.status_code == 401
    assert response.get_json() == {"error": "AUTH_REQUIRED"}
    assert service.calls == []


def test_obs_status_delegates(obs_client) -> None:
    client, _, service = obs_client
    response = client.get("/api/obs/status", headers=auth_headers())
    assert response.status_code == 200
    assert response.get_json() == {"reachable": False, "error": "not tested"}
    assert service.calls == [("status", None)]


def test_obs_connection_test_delegates(obs_client) -> None:
    client, _, service = obs_client
    response = client.post("/api/obs/test", headers=auth_headers())
    assert response.status_code == 200
    assert response.get_json() == {"reachable": True, "authenticated": True}
    assert service.calls == [("test_connection", None)]


def test_scorebug_visibility_maps_boolean_validation(obs_client) -> None:
    client, _, service = obs_client
    service.scorebug_result = StubResult("VISIBLE_MUST_BE_BOOLEAN")
    response = client.post(
        "/api/obs/scorebug-visibility",
        json={"visible": "yes"},
        headers=auth_headers(),
    )
    assert response.status_code == 400
    assert response.get_json() == {"error": "VISIBLE_MUST_BE_BOOLEAN"}
    assert service.calls == [("scorebug_visibility", "yes")]


def test_scorebug_visibility_maps_blocked_command(obs_client) -> None:
    client, _, service = obs_client
    service.scorebug_result = StubResult(
        "OBS_COMMAND_BLOCKED",
        {"message": "Controlled commands are disabled."},
    )
    response = client.post(
        "/api/obs/scorebug-visibility",
        json={"visible": True},
        headers=auth_headers(),
    )
    assert response.status_code == 409
    assert response.get_json() == {
        "error": "OBS_COMMAND_BLOCKED",
        "message": "Controlled commands are disabled.",
    }


def test_scorebug_visibility_preserves_success_payload(obs_client) -> None:
    client, _, service = obs_client
    response = client.post(
        "/api/obs/scorebug-visibility",
        json={"visible": True},
        headers=auth_headers(),
    )
    assert response.status_code == 200
    assert response.get_json() == {"scene": "Program", "visible": True}
    assert service.calls == [("scorebug_visibility", True)]


def test_program_visual_mode_maps_blocked_command(obs_client) -> None:
    client, _, service = obs_client
    service.mode_result = StubResult(
        "OBS_COMMAND_BLOCKED",
        {"message": "OBS is unavailable."},
    )
    response = client.post(
        "/api/obs/program-visual-mode",
        json={"mode": "halftime"},
        headers=auth_headers(),
    )
    assert response.status_code == 409
    assert response.get_json() == {
        "error": "OBS_COMMAND_BLOCKED",
        "message": "OBS is unavailable.",
    }


def test_program_visual_mode_preserves_service_payload(obs_client) -> None:
    client, _, service = obs_client
    response = client.post(
        "/api/obs/program-visual-mode",
        json={"mode": "halftime"},
        headers=auth_headers(),
    )
    assert response.status_code == 200
    assert response.get_json() == {
        "state": {"visual_mode": "halftime"},
        "obs": {"scene": "Halftime"},
    }
    assert service.calls == [("program_visual_mode", "halftime")]


