from __future__ import annotations

from typing import Any

import pytest

import app as app_module
from broadcast_package_service import PackageResult


class StubPackageService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

    def list_packages(self) -> list[dict[str, Any]]:
        self.calls.append(("list", None))
        return [{"id": "pkg-list", "updated_at": 10}]

    def create(self, data: dict[str, Any]) -> PackageResult:
        self.calls.append(("create", data))
        return PackageResult("OK", {"package": {"id": "pkg-created", **data}})

    def update(self, package_id: str, data: dict[str, Any]) -> PackageResult:
        self.calls.append(("update", (package_id, data)))
        if package_id == "missing":
            return PackageResult("NOT_FOUND")
        if package_id == "locked":
            return PackageResult("PACKAGE_LOCKED")
        return PackageResult("OK", {"package": {"id": package_id, **data}})

    def delete(self, package_id: str) -> PackageResult:
        self.calls.append(("delete", package_id))
        if package_id == "missing":
            return PackageResult("NOT_FOUND")
        if package_id == "locked":
            return PackageResult("PACKAGE_LOCKED")
        return PackageResult("OK", {"deleted": package_id})

    def duplicate(self, package_id: str) -> PackageResult:
        self.calls.append(("duplicate", package_id))
        if package_id == "missing":
            return PackageResult("NOT_FOUND")
        return PackageResult("OK", {"package": {"id": "pkg-copy"}})

    def load(self, package_id: str) -> PackageResult:
        self.calls.append(("load", package_id))
        if package_id == "missing":
            return PackageResult("NOT_FOUND")
        if package_id == "no-broadcast":
            return PackageResult("BROADCAST_NOT_FOUND")
        return PackageResult(
            "OK",
            {
                "package": {"id": package_id, "status": "Loaded"},
                "state": {"marker": "loaded-state"},
                "health": {"score": 100, "ready": True, "checks": []},
            },
        )


@pytest.fixture
def package_client(monkeypatch: pytest.MonkeyPatch):
    service = StubPackageService()
    monkeypatch.setattr(app_module, "BROADCAST_PACKAGE_SERVICE", service)
    monkeypatch.setattr(app_module, "pin_is_configured", lambda: True)
    monkeypatch.setattr(
        app_module,
        "public_state",
        lambda state: {"public_marker": state["marker"]},
    )
    monkeypatch.setitem(app_module.app.config, "TESTING", True)
    monkeypatch.setitem(app_module.app.config, "SECRET_KEY", "package-route-test")

    with app_module.app.test_client() as client:
        with client.session_transaction() as active_session:
            active_session["authenticated"] = True
        yield client, service


def test_list_and_create_routes_delegate_to_service(package_client) -> None:
    client, service = package_client

    listed = client.get("/api/packages")
    created = client.post("/api/packages", json={"name": "Friday Night"})

    assert listed.status_code == 200
    assert listed.get_json() == [{"id": "pkg-list", "updated_at": 10}]
    assert created.status_code == 201
    assert created.get_json()["id"] == "pkg-created"
    assert ("create", {"name": "Friday Night"}) in service.calls


def test_update_route_maps_domain_errors(package_client) -> None:
    client, _service = package_client

    missing = client.put("/api/packages/missing", json={"name": "Changed"})
    locked = client.put("/api/packages/locked", json={"name": "Changed"})
    updated = client.put("/api/packages/pkg-1", json={"name": "Changed"})

    assert missing.status_code == 404
    assert missing.get_json() == {"error": "NOT_FOUND"}
    assert locked.status_code == 409
    assert locked.get_json() == {"error": "PACKAGE_LOCKED"}
    assert updated.status_code == 200
    assert updated.get_json() == {"id": "pkg-1", "name": "Changed"}


def test_delete_and_duplicate_routes_preserve_response_contract(package_client) -> None:
    client, _service = package_client

    deleted = client.delete("/api/packages/pkg-1")
    locked = client.delete("/api/packages/locked")
    duplicated = client.post("/api/packages/pkg-1/duplicate")
    missing = client.post("/api/packages/missing/duplicate")

    assert deleted.status_code == 200
    assert deleted.get_json() == {"deleted": "pkg-1"}
    assert locked.status_code == 409
    assert locked.get_json() == {"error": "PACKAGE_LOCKED"}
    assert duplicated.status_code == 201
    assert duplicated.get_json() == {"id": "pkg-copy"}
    assert missing.status_code == 404
    assert missing.get_json() == {"error": "NOT_FOUND"}


def test_load_route_maps_errors_and_filters_public_state(package_client) -> None:
    client, _service = package_client

    missing = client.post("/api/packages/missing/load")
    no_broadcast = client.post("/api/packages/no-broadcast/load")
    loaded = client.post("/api/packages/pkg-1/load")

    assert missing.status_code == 404
    assert missing.get_json() == {"error": "NOT_FOUND"}
    assert no_broadcast.status_code == 409
    assert no_broadcast.get_json() == {"error": "BROADCAST_NOT_FOUND"}
    assert loaded.status_code == 200
    assert loaded.get_json() == {
        "package": {"id": "pkg-1", "status": "Loaded"},
        "state": {"public_marker": "loaded-state"},
        "health": {"score": 100, "ready": True, "checks": []},
    }
