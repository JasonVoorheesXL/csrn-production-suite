from __future__ import annotations

import copy
from typing import Any

import pytest

import app as app_module
from statistics_service import StatisticsResult


if not hasattr(app_module, "get_statistics_service"):
    pytest.skip(
        "StatisticsService route is not integrated yet.",
        allow_module_level=True,
    )


class StubStatisticsService:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.result = StatisticsResult(
            "OK",
            {
                "statistics": {
                    "broadcast_id": "FB-2026-01",
                    "teams": {"home": {"score": 14}},
                    "players": [],
                }
            },
        )

    def report(self, state: dict[str, Any]) -> StatisticsResult:
        self.calls.append(copy.deepcopy(state))
        return self.result


@pytest.fixture
def statistics_client(monkeypatch: pytest.MonkeyPatch):
    service = StubStatisticsService()
    state = {"broadcast_id": "FB-2026-01", "home_score": 14}
    monkeypatch.setattr(app_module, "STATISTICS_SERVICE", service, raising=False)
    monkeypatch.setattr(app_module, "pin_is_configured", lambda: True)
    monkeypatch.setattr(app_module, "load_state", lambda: copy.deepcopy(state))
    monkeypatch.setitem(app_module.app.config, "TESTING", True)
    monkeypatch.setitem(app_module.app.config, "SECRET_KEY", "statistics-route-test")
    with app_module.app.test_client() as client:
        with client.session_transaction() as active_session:
            active_session["authenticated"] = True
        yield client, service, state


def test_statistics_route_delegates_and_returns_report(statistics_client) -> None:
    client, service, state = statistics_client
    response = client.get("/api/statistics")
    assert response.status_code == 200
    assert response.get_json()["broadcast_id"] == "FB-2026-01"
    assert response.get_json()["teams"]["home"]["score"] == 14
    assert service.calls == [state]


def test_statistics_route_preserves_service_payload(statistics_client) -> None:
    client, service, _state = statistics_client
    service.result = StatisticsResult(
        "OK",
        {
            "statistics": {
                "broadcast_id": "",
                "teams": {},
                "players": [],
                "scoring_summary": [],
                "play_register": [],
            }
        },
    )
    response = client.get("/api/statistics")
    assert response.status_code == 200
    assert response.get_json() == service.result.data["statistics"]


def test_build_statistics_compatibility_helper_delegates(monkeypatch: pytest.MonkeyPatch) -> None:
    service = StubStatisticsService()
    monkeypatch.setattr(app_module, "STATISTICS_SERVICE", service, raising=False)
    state = {"broadcast_id": "COMPAT"}
    assert app_module.build_statistics(state) == service.result.data["statistics"]
    assert service.calls == [state]


