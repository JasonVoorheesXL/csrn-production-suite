from __future__ import annotations

import copy
from typing import Any

import pytest

import app as app_module
from graphics_service import GraphicsResult


if not hasattr(app_module, "get_graphics_service"):
    pytest.skip(
        "GraphicsService routes are not integrated yet.",
        allow_module_level=True,
    )


class StubGraphicsService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.lower_result = GraphicsResult(
            "OK",
            {
                "state": {"channel": "lower", "lower_third": {"visible": True}},
                "graphic": {"visible": True},
            },
        )
        self.player_result = GraphicsResult(
            "OK",
            {
                "state": {"channel": "player", "player_graphic": {"visible": True}},
                "graphic": {"visible": True},
                "sponsor_warning": "",
            },
        )
        self.personnel_result = GraphicsResult(
            "OK",
            {
                "state": {
                    "channel": "personnel",
                    "personnel_graphic": {"visible": True},
                },
                "graphic": {"visible": True},
                "sponsor_warning": "",
            },
        )
        self.spotlight_result = GraphicsResult(
            "OK",
            {
                "state": {
                    "channel": "sponsor",
                    "sponsor_spotlight": {"visible": True},
                },
                "graphic": {"visible": True},
                "sponsor_warning": "",
            },
        )
        self.highlight_result = GraphicsResult(
            "OK",
            {
                "state": {
                    "channel": "highlight",
                    "player_highlight": {"visible": True},
                },
                "graphic": {"visible": True},
            },
        )
        self.queue_result = GraphicsResult(
            "OK",
            {"state": {"graphics_queue": []}},
        )

    def update_lower_third(self, state: dict, incoming: dict) -> GraphicsResult:
        self.calls.append(("update_lower_third", (copy.deepcopy(state), incoming)))
        return self.lower_result

    def update_player(self, state: dict, incoming: dict) -> GraphicsResult:
        self.calls.append(("update_player", (copy.deepcopy(state), incoming)))
        return self.player_result

    def update_personnel(self, state: dict, incoming: dict) -> GraphicsResult:
        self.calls.append(("update_personnel", (copy.deepcopy(state), incoming)))
        return self.personnel_result

    def update_sponsor_spotlight(
        self,
        state: dict,
        incoming: dict,
    ) -> GraphicsResult:
        self.calls.append(
            ("update_sponsor_spotlight", (copy.deepcopy(state), incoming))
        )
        return self.spotlight_result

    def update_player_highlight(
        self,
        state: dict,
        incoming: dict,
    ) -> GraphicsResult:
        self.calls.append(
            ("update_player_highlight", (copy.deepcopy(state), incoming))
        )
        return self.highlight_result

    def update_queue(self, state: dict, incoming: dict) -> GraphicsResult:
        self.calls.append(("update_queue", (copy.deepcopy(state), incoming)))
        return self.queue_result


@pytest.fixture
def graphics_client(monkeypatch: pytest.MonkeyPatch):
    service = StubGraphicsService()
    source_state = {
        "lower_third": {"visible": False},
        "player_graphic": {"visible": False},
        "personnel_graphic": {"visible": False},
    }
    saved: list[dict] = []

    monkeypatch.setattr(app_module, "GRAPHICS_SERVICE", service, raising=False)
    monkeypatch.setattr(app_module, "pin_is_configured", lambda: True)
    monkeypatch.setattr(app_module, "load_state", lambda: copy.deepcopy(source_state))
    monkeypatch.setattr(
        app_module,
        "save_state",
        lambda state: saved.append(copy.deepcopy(state)),
    )
    monkeypatch.setattr(app_module, "public_state", lambda state: copy.deepcopy(state))
    monkeypatch.setitem(app_module.app.config, "TESTING", True)
    monkeypatch.setitem(app_module.app.config, "SECRET_KEY", "graphics-route-test")

    with app_module.app.test_client() as client:
        with client.session_transaction() as active_session:
            active_session["authenticated"] = True
        yield client, service, source_state, saved


def test_lower_third_route_delegates_saves_and_returns_state(graphics_client) -> None:
    client, service, source_state, saved = graphics_client
    payload = {"action": "show", "headline": "Game Night"}
    response = client.post("/api/graphics/lower-third", json=payload)
    assert response.status_code == 200
    assert response.get_json() == service.lower_result.data["state"]
    assert service.calls == [
        ("update_lower_third", (source_state, payload))
    ]
    assert saved == [service.lower_result.data["state"]]


def test_player_route_preserves_required_player_contract(graphics_client) -> None:
    client, service, _source_state, saved = graphics_client
    service.player_result = GraphicsResult("PLAYER_REQUIRED")
    response = client.post("/api/graphics/player", json={"action": "show"})
    assert response.status_code == 400
    assert response.get_json() == {"error": "PLAYER_REQUIRED"}
    assert saved == []


def test_player_route_saves_state_and_surfaces_sponsor_warning(graphics_client) -> None:
    client, service, _source_state, saved = graphics_client
    service.player_result = GraphicsResult(
        "OK",
        {
            "state": {"channel": "player"},
            "graphic": {"visible": True},
            "sponsor_warning": "CONTRACT_EXPIRED",
        },
    )
    payload = {
        "action": "show",
        "roster_id": "caledonia-football",
        "player_id": "12-jason",
    }
    response = client.post("/api/graphics/player", json=payload)
    assert response.status_code == 200
    assert response.get_json() == {
        "channel": "player",
        "sponsor_warning": "CONTRACT_EXPIRED",
    }
    assert saved == [{"channel": "player"}]


def test_player_route_omits_empty_sponsor_warning(graphics_client) -> None:
    client, service, _source_state, _saved = graphics_client
    response = client.post(
        "/api/graphics/player",
        json={"action": "show", "player_id": "12-jason"},
    )
    assert response.status_code == 200
    assert "sponsor_warning" not in response.get_json()
    assert service.calls[-1][0] == "update_player"


def test_personnel_route_preserves_required_personnel_contract(graphics_client) -> None:
    client, service, _source_state, saved = graphics_client
    service.personnel_result = GraphicsResult("PERSONNEL_REQUIRED")
    response = client.post(
        "/api/graphics/personnel",
        json={"action": "show"},
    )
    assert response.status_code == 400
    assert response.get_json() == {"error": "PERSONNEL_REQUIRED"}
    assert saved == []


def test_personnel_route_saves_and_returns_warning(graphics_client) -> None:
    client, service, _source_state, saved = graphics_client
    service.personnel_result = GraphicsResult(
        "OK",
        {
            "state": {"channel": "personnel"},
            "graphic": {"visible": True},
            "sponsor_warning": "SPONSOR_INACTIVE",
        },
    )
    response = client.post(
        "/api/graphics/personnel",
        json={"action": "show", "personnel_id": "jordan"},
    )
    assert response.status_code == 200
    assert response.get_json() == {
        "channel": "personnel",
        "sponsor_warning": "SPONSOR_INACTIVE",
    }
    assert saved == [{"channel": "personnel"}]


def test_sponsor_spotlight_and_queue_routes_delegate_and_save(graphics_client) -> None:
    client, service, source_state, saved = graphics_client
    spotlight_payload = {
        "action": "show",
        "sponsor_id": "bank",
        "media_asset_id": "bank-video",
    }
    spotlight_response = client.post(
        "/api/graphics/sponsor-spotlight",
        json=spotlight_payload,
    )
    queue_response = client.post(
        "/api/graphics/queue",
        json={"action": "cancel", "id": "GQ-1"},
    )

    assert spotlight_response.status_code == 200
    assert queue_response.status_code == 200
    assert service.calls[-2:] == [
        (
            "update_sponsor_spotlight",
            (source_state, spotlight_payload),
        ),
        (
            "update_queue",
            (source_state, {"action": "cancel", "id": "GQ-1"}),
        ),
    ]
    assert saved[-2:] == [
        service.spotlight_result.data["state"],
        service.queue_result.data["state"],
    ]


def test_player_highlight_route_delegates_and_enforces_media_contract(
    graphics_client,
) -> None:
    client, service, source_state, saved = graphics_client
    payload = {
        "action": "show",
        "roster_id": "caledonia-football",
        "player_id": "12-jason",
        "media_asset_id": "jason-week-4",
        "duration": 30,
    }
    response = client.post("/api/graphics/player-highlight", json=payload)
    assert response.status_code == 200
    assert service.calls[-1] == (
        "update_player_highlight",
        (source_state, payload),
    )
    assert saved[-1] == service.highlight_result.data["state"]

    service.highlight_result = GraphicsResult(
        "PLAYER_HIGHLIGHT_MEDIA_NOT_APPROVED"
    )
    rejected = client.post("/api/graphics/player-highlight", json=payload)
    assert rejected.status_code == 400
    assert rejected.get_json() == {
        "error": "PLAYER_HIGHLIGHT_MEDIA_NOT_APPROVED"
    }


