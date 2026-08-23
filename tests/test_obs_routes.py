from __future__ import annotations

from typing import Any

import pytest

import app as app_module
from obs_service import OBSServiceResult


if not hasattr(app_module, "get_obs_service"):
    pytest.skip(
        "OBSService routes are not integrated yet.",
        allow_module_level=True,
    )


class StubOBSService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.status_result = OBSServiceResult(
            "OK",
            {"status": {"reachable": False, "checked_at": 0}},
        )
        self.test_result = OBSServiceResult(
            "OK",
            {"obs": {"reachable": True, "authenticated": True}},
        )
        self.scorebug_result = OBSServiceResult(
            "OK",
            {"obs": {"command_sent": True, "command": "SHOW"}},
        )
        self.visual_result = OBSServiceResult(
            "OK",
            {
                "state": {"visual_mode": "camera"},
                "obs": {"command_sent": True, "visual_mode": "camera"},
            },
        )

    def status(self) -> OBSServiceResult:
        self.calls.append(("status", None))
        return self.status_result

    def test_connection(self) -> OBSServiceResult:
        self.calls.append(("test_connection", None))
        return self.test_result

    def scorebug_visibility(self, visible: Any) -> OBSServiceResult:
        self.calls.append(("scorebug_visibility", visible))
        return self.scorebug_result

    def program_visual_mode(self, mode: Any) -> OBSServiceResult:
        self.calls.append(("program_visual_mode", mode))
        return self.visual_result


@pytest.fixture
def obs_client(monkeypatch: pytest.MonkeyPatch):
    service = StubOBSService()
    monkeypatch.setattr(app_module, "OBS_SERVICE", service, raising=False)
    monkeypatch.setattr(app_module, "pin_is_configured", lambda: True)
    monkeypatch.setitem(app_module.app.config, "TESTING", True)
    monkeypatch.setitem(app_module.app.config, "SECRET_KEY", "obs-route-test")

    with app_module.app.test_client() as client:
        with client.session_transaction() as active_session:
            active_session["authenticated"] = True
        yield client, service


def test_status_route_preserves_payload(obs_client) -> None:
    client, service = obs_client
    response = client.get("/api/obs/status")
    assert response.status_code == 200
    assert response.get_json() == {"reachable": False, "checked_at": 0}
    assert service.calls == [("status", None)]


def test_connection_test_route_preserves_payload(obs_client) -> None:
    client, service = obs_client
    response = client.post("/api/obs/test")
    assert response.status_code == 200
    assert response.get_json() == {"reachable": True, "authenticated": True}
    assert service.calls == [("test_connection", None)]


def test_scorebug_route_requires_boolean(obs_client) -> None:
    client, service = obs_client
    service.scorebug_result = OBSServiceResult("VISIBLE_MUST_BE_BOOLEAN")
    response = client.post(
        "/api/obs/scorebug-visibility",
        json={"visible": "true"},
    )
    assert response.status_code == 400
    assert response.get_json() == {"error": "VISIBLE_MUST_BE_BOOLEAN"}
    assert service.calls == [("scorebug_visibility", "true")]


def test_scorebug_route_maps_blocked_command(obs_client) -> None:
    client, service = obs_client
    service.scorebug_result = OBSServiceResult(
        "OBS_COMMAND_BLOCKED",
        {"message": "Controlled OBS commands are disabled in Settings."},
    )
    response = client.post(
        "/api/obs/scorebug-visibility",
        json={"visible": True},
    )
    assert response.status_code == 409
    assert response.get_json() == {
        "error": "OBS_COMMAND_BLOCKED",
        "message": "Controlled OBS commands are disabled in Settings.",
    }


def test_scorebug_route_returns_command_payload(obs_client) -> None:
    client, service = obs_client
    response = client.post(
        "/api/obs/scorebug-visibility",
        json={"visible": True},
    )
    assert response.status_code == 200
    assert response.get_json() == {"command_sent": True, "command": "SHOW"}
    assert service.calls == [("scorebug_visibility", True)]


def test_program_visual_route_maps_blocked_command(obs_client) -> None:
    client, service = obs_client
    service.visual_result = OBSServiceResult(
        "OBS_COMMAND_BLOCKED",
        {"message": "Program visual mode must be graphic or camera."},
    )
    response = client.post(
        "/api/obs/program-visual-mode",
        json={"mode": "slides"},
    )
    assert response.status_code == 409
    assert response.get_json() == {
        "error": "OBS_COMMAND_BLOCKED",
        "message": "Program visual mode must be graphic or camera.",
    }


def test_program_visual_route_returns_state_and_obs(obs_client) -> None:
    client, service = obs_client
    response = client.post(
        "/api/obs/program-visual-mode",
        json={"mode": "camera"},
    )
    assert response.status_code == 200
    assert response.get_json() == {
        "state": {"visual_mode": "camera"},
        "obs": {"command_sent": True, "visual_mode": "camera"},
    }
    assert service.calls == [("program_visual_mode", "camera")]


def test_command_scorebug_visibility_preserves_legacy_exception(obs_client) -> None:
    _, service = obs_client
    service.scorebug_result = OBSServiceResult(
        "OBS_COMMAND_BLOCKED",
        {"message": "OBS unavailable"},
    )
    with pytest.raises(app_module.OBSConnectionError, match="OBS unavailable"):
        app_module.command_scorebug_visibility(True)


