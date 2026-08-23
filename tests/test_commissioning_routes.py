from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest
from flask import Flask

from routes.commissioning_routes import (
    CommissioningRoutesDependencies,
    create_commissioning_blueprint,
)


@dataclass
class StubResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)


class StubCommissioningService:
    def __init__(self) -> None:
        self.updated: Any = None
        self.check_args: dict[str, Any] = {}
        self.profile_result = StubResult("OK", {"profile": {"device": {"model": "P4next"}}})
        self.update_result = StubResult("PROFILE_UPDATED", {"profile": {"updated": True}})
        self.check_result = StubResult("CHECK_UPDATED", {"profile": {"checked": True}})
        self.obs_result = StubResult("OBS_CHECK_COMPLETE", {"obs_check": {"ready": True}})
        self.report_result = StubResult("COMMISSIONING_READY", {"report": {"ready": True}})

    def load(self) -> StubResult:
        return self.profile_result

    def update_profile(self, incoming: Any) -> StubResult:
        self.updated = incoming
        return self.update_result

    def set_check(self, **kwargs: Any) -> StubResult:
        self.check_args = kwargs
        return self.check_result

    def run_obs_check(self) -> StubResult:
        return self.obs_result

    def report(self) -> StubResult:
        return self.report_result


def require_auth(func):
    setattr(func, "_csrn_requires_auth", True)
    return func


@pytest.fixture
def commissioning_client():
    service = StubCommissioningService()
    app = Flask(__name__)
    app.register_blueprint(
        create_commissioning_blueprint(
            CommissioningRoutesDependencies(
                require_auth=require_auth,
                get_commissioning_service=lambda: service,
            )
        )
    )
    return app.test_client(), service


def test_get_profile(commissioning_client) -> None:
    client, _ = commissioning_client
    response = client.get("/api/game-day/commissioning")
    assert response.status_code == 200
    assert response.get_json()["profile"]["device"]["model"] == "P4next"


def test_update_profile(commissioning_client) -> None:
    client, service = commissioning_client
    response = client.put(
        "/api/game-day/commissioning",
        json={"notes": "ready"},
    )
    assert response.status_code == 200
    assert response.get_json()["code"] == "PROFILE_UPDATED"
    assert service.updated == {"notes": "ready"}


def test_update_profile_rejects_invalid_body(commissioning_client) -> None:
    client, service = commissioning_client
    service.update_result = StubResult("PROFILE_MUST_BE_OBJECT")
    response = client.put(
        "/api/game-day/commissioning",
        data="[]",
        content_type="application/json",
    )
    assert response.status_code == 400
    assert response.get_json()["error"] == "PROFILE_MUST_BE_OBJECT"


def test_update_check(commissioning_client) -> None:
    client, service = commissioning_client
    response = client.post(
        "/api/game-day/commissioning/check",
        json={
            "section": "audio_checks",
            "key": "no_clipping",
            "passed": True,
            "note": "clean",
        },
    )
    assert response.status_code == 200
    assert service.check_args == {
        "section": "audio_checks",
        "key": "no_clipping",
        "passed": True,
        "note": "clean",
    }


@pytest.mark.parametrize(
    "code",
    ["INVALID_CHECK_SECTION", "INVALID_CHECK_KEY", "PASSED_MUST_BE_BOOLEAN"],
)
def test_update_check_maps_validation_errors(commissioning_client, code: str) -> None:
    client, service = commissioning_client
    service.check_result = StubResult(code)
    response = client.post(
        "/api/game-day/commissioning/check",
        json={"section": "bad", "key": "bad", "passed": "yes"},
    )
    assert response.status_code == 400
    assert response.get_json()["code"] == code


def test_run_obs_test(commissioning_client) -> None:
    client, _ = commissioning_client
    response = client.post("/api/game-day/commissioning/obs-test")
    assert response.status_code == 200
    assert response.get_json()["obs_check"]["ready"] is True


def test_ready_report_returns_200(commissioning_client) -> None:
    client, _ = commissioning_client
    response = client.get("/api/game-day/commissioning/report")
    assert response.status_code == 200
    assert response.get_json()["code"] == "COMMISSIONING_READY"


def test_incomplete_report_returns_409(commissioning_client) -> None:
    client, service = commissioning_client
    service.report_result = StubResult(
        "COMMISSIONING_INCOMPLETE", {"report": {"ready": False}}
    )
    response = client.get("/api/game-day/commissioning/report")
    assert response.status_code == 409
    assert response.get_json()["code"] == "COMMISSIONING_INCOMPLETE"


