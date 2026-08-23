from __future__ import annotations

from typing import Any

import pytest

import app as app_module
from broadcast_service import BroadcastResult


if not hasattr(app_module, "get_broadcast_service"):
    pytest.skip(
        "BroadcastService routes are not integrated yet.",
        allow_module_level=True,
    )


BROADCAST_ID = "FB-2026-5A-W01-001"


class StubBroadcastService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.broadcast = {
            "broadcast_id": BROADCAST_ID,
            "status": "planned",
            "home_team": "Caledonia",
            "visitor_team": "New Hope",
        }
        self.list_result = BroadcastResult(
            "OK",
            {"broadcasts": [self.broadcast]},
        )
        self.read_result = BroadcastResult(
            "OK",
            {"broadcast": self.broadcast},
        )
        self.create_result = BroadcastResult(
            "OK",
            {"broadcast": self.broadcast, "warnings": ["warning"]},
        )
        self.update_result = BroadcastResult(
            "OK",
            {"broadcast": self.broadcast, "warnings": []},
        )
        self.status_result = BroadcastResult(
            "OK",
            {"broadcast": self.broadcast},
        )
        self.delete_result = BroadcastResult(
            "OK",
            {"deleted": BROADCAST_ID},
        )

    def list_records(self, *, include_archived: bool = False) -> BroadcastResult:
        self.calls.append(("list_records", include_archived))
        return self.list_result

    def read(self, broadcast_id: str) -> BroadcastResult:
        self.calls.append(("read", broadcast_id))
        return self.read_result

    def create(self, incoming: dict[str, Any]) -> BroadcastResult:
        self.calls.append(("create", incoming))
        return self.create_result

    def update(
        self,
        broadcast_id: str,
        incoming: dict[str, Any],
    ) -> BroadcastResult:
        self.calls.append(("update", (broadcast_id, incoming)))
        return self.update_result

    def set_status(self, broadcast_id: str, status: Any) -> BroadcastResult:
        self.calls.append(("set_status", (broadcast_id, status)))
        return self.status_result

    def delete(self, broadcast_id: str) -> BroadcastResult:
        self.calls.append(("delete", broadcast_id))
        return self.delete_result


@pytest.fixture
def broadcast_client(monkeypatch: pytest.MonkeyPatch):
    service = StubBroadcastService()
    monkeypatch.setattr(app_module, "BROADCAST_SERVICE", service, raising=False)
    monkeypatch.setattr(app_module, "pin_is_configured", lambda: True)
    monkeypatch.setitem(app_module.app.config, "TESTING", True)
    monkeypatch.setitem(
        app_module.app.config,
        "SECRET_KEY",
        "broadcast-route-test",
    )

    with app_module.app.test_client() as client:
        with client.session_transaction() as active_session:
            active_session["authenticated"] = True
        yield client, service


def test_list_broadcasts_preserves_array_contract_and_archive_option(
    broadcast_client,
) -> None:
    client, service = broadcast_client

    response = client.get("/api/broadcasts?include_archived=true")

    assert response.status_code == 200
    assert response.get_json() == [service.broadcast]
    assert service.calls == [("list_records", True)]


def test_read_broadcast_preserves_success_and_not_found_contracts(
    broadcast_client,
) -> None:
    client, service = broadcast_client

    found = client.get(f"/api/broadcasts/{BROADCAST_ID}")
    assert found.status_code == 200
    assert found.get_json() == service.broadcast

    service.read_result = BroadcastResult("NOT_FOUND")
    missing = client.get("/api/broadcasts/missing")
    assert missing.status_code == 404
    assert missing.get_json() == {"error": "NOT_FOUND"}


def test_create_broadcast_preserves_payload_contract(broadcast_client) -> None:
    client, service = broadcast_client
    payload = {
        "home_school_id": "caledonia",
        "visitor_school_id": "new-hope",
    }

    response = client.post("/api/create-broadcast", json=payload)

    assert response.status_code == 200
    assert response.get_json() == {
        "broadcast": service.broadcast,
        "warnings": ["warning"],
    }
    assert service.calls == [("create", payload)]


def test_update_broadcast_preserves_success_and_not_found_contracts(
    broadcast_client,
) -> None:
    client, service = broadcast_client
    payload = {"date": "2026-08-21"}

    updated = client.put(f"/api/broadcasts/{BROADCAST_ID}", json=payload)
    assert updated.status_code == 200
    assert updated.get_json() == {
        "broadcast": service.broadcast,
        "warnings": [],
    }
    assert service.calls == [("update", (BROADCAST_ID, payload))]

    service.update_result = BroadcastResult("NOT_FOUND")
    missing = client.put("/api/broadcasts/missing", json=payload)
    assert missing.status_code == 404
    assert missing.get_json() == {"error": "NOT_FOUND"}


def test_status_route_preserves_invalid_missing_and_success_contracts(
    broadcast_client,
) -> None:
    client, service = broadcast_client

    updated = client.put(
        f"/api/broadcasts/{BROADCAST_ID}/status",
        json={"status": "live"},
    )
    assert updated.status_code == 200
    assert updated.get_json() == service.broadcast
    assert service.calls == [("set_status", (BROADCAST_ID, "live"))]

    service.status_result = BroadcastResult("INVALID_STATUS")
    invalid = client.put(
        f"/api/broadcasts/{BROADCAST_ID}/status",
        json={"status": "cancelled"},
    )
    assert invalid.status_code == 400
    assert invalid.get_json() == {"error": "INVALID_STATUS"}

    service.status_result = BroadcastResult("NOT_FOUND")
    missing = client.put(
        "/api/broadcasts/missing/status",
        json={"status": "live"},
    )
    assert missing.status_code == 404
    assert missing.get_json() == {"error": "NOT_FOUND"}


def test_delete_broadcast_preserves_success_and_not_found_contracts(
    broadcast_client,
) -> None:
    client, service = broadcast_client

    deleted = client.delete(f"/api/broadcasts/{BROADCAST_ID}")
    assert deleted.status_code == 200
    assert deleted.get_json() == {"deleted": BROADCAST_ID}
    assert service.calls == [("delete", BROADCAST_ID)]

    service.delete_result = BroadcastResult("NOT_FOUND")
    missing = client.delete("/api/broadcasts/missing")
    assert missing.status_code == 404
    assert missing.get_json() == {"error": "NOT_FOUND"}


