from __future__ import annotations

from typing import Any

import pytest

import app as app_module
from state_service import StateResult


if not hasattr(app_module, "get_state_service"):
    pytest.skip(
        "StateService routes are not integrated yet.",
        allow_module_level=True,
    )


class StubStateService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.state = {"broadcast_id": "B1", "home_score": 6}

    def load(self) -> StateResult:
        self.calls.append(("load", None))
        return StateResult("OK", {"state": dict(self.state)})

    def save(self, state: dict[str, Any]) -> StateResult:
        self.calls.append(("save", state))
        self.state = dict(state)
        return StateResult("OK", {"state": dict(self.state)})

    def public(self, state: dict[str, Any]) -> StateResult:
        self.calls.append(("public", state))
        return StateResult("OK", {"state": {**state, "public": True}})

    def apply_change(self, changes, *, save_undo=True) -> StateResult:
        self.calls.append(("apply_change", (changes, save_undo)))
        return StateResult("OK", {"state": {**self.state, **changes}})

    def normalize(self, state):
        self.calls.append(("normalize", state))
        return dict(state)


@pytest.fixture
def state_client(monkeypatch: pytest.MonkeyPatch):
    service = StubStateService()
    monkeypatch.setattr(app_module, "STATE_SERVICE", service, raising=False)
    monkeypatch.setitem(app_module.app.config, "TESTING", True)
    with app_module.app.test_client() as client:
        yield client, service


def test_load_state_wrapper_delegates(state_client) -> None:
    _, service = state_client
    assert app_module.load_state() == service.state
    assert service.calls == [("load", None)]


def test_save_state_wrapper_delegates(state_client) -> None:
    _, service = state_client
    app_module.save_state({"broadcast_id": "B2", "home_score": 3})
    assert service.calls == [
        ("save", {"broadcast_id": "B2", "home_score": 3})
    ]


def test_state_endpoint_returns_public_service_state(state_client) -> None:
    client, service = state_client
    response = client.get("/api/state")
    assert response.status_code == 200
    assert response.get_json() == {
        "broadcast_id": "B1",
        "graphics_queue": [],
        "home_score": 6,
        "overlay_revision": "gate5-program-visual-v10",
        "public": True,
    }
    assert service.calls == [
        ("load", None),
        (
            "public",
            {
                "broadcast_id": "B1",
                "graphics_queue": [],
                "home_score": 6,
            },
        ),
    ]
