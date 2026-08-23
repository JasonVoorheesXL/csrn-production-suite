from __future__ import annotations

from typing import Any

import pytest

import app as app_module
from school_service import SchoolResult


class StubSchoolService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []

    def list_schools(self) -> list[dict[str, Any]]:
        self.calls.append(("list", None))
        return [
            {
                "id": "caledonia",
                "official_name": "Caledonia High School",
                "broadcast_name": "Caledonia",
            }
        ]

    def read(self, school_id: str) -> SchoolResult:
        self.calls.append(("read", school_id))
        if school_id == "missing":
            return SchoolResult("SCHOOL_NOT_FOUND")
        return SchoolResult(
            "OK",
            {"school": {"id": school_id, "broadcast_name": "Caledonia"}},
        )

    def create(self, incoming: dict[str, Any]) -> SchoolResult:
        self.calls.append(("create", incoming))
        mode = incoming.get("mode")
        if mode == "missing-name":
            return SchoolResult("SCHOOL_NAME_REQUIRED")
        if mode == "duplicate":
            return SchoolResult(
                "LIKELY_DUPLICATE",
                {"matches": [{"id": "caledonia", "score": 5}]},
            )
        if mode == "invalid-social":
            return SchoolResult(
                "INVALID_SOCIAL_URL",
                {"fields": {"facebook": "Expected a valid facebook URL"}},
            )
        return SchoolResult(
            "OK",
            {"school": {"id": "new-school", **incoming}},
        )

    def update(self, school_id: str, incoming: dict[str, Any]) -> SchoolResult:
        self.calls.append(("update", (school_id, incoming)))
        if school_id == "missing":
            return SchoolResult("SCHOOL_NOT_FOUND")
        if incoming.get("mode") == "invalid-social":
            return SchoolResult(
                "INVALID_SOCIAL_URL",
                {"fields": {"website": "Expected a valid website URL"}},
            )
        return SchoolResult(
            "OK",
            {"school": {"id": school_id, **incoming}},
        )

    def delete(self, school_id: str) -> SchoolResult:
        self.calls.append(("delete", school_id))
        if school_id == "missing":
            return SchoolResult("SCHOOL_NOT_FOUND")
        return SchoolResult("OK", {"ok": True})

    def duplicate_candidates(
        self,
        incoming: dict[str, Any],
        exclude_id: str = "",
    ) -> list[dict[str, Any]]:
        self.calls.append(("duplicate", (incoming, exclude_id)))
        return [{"id": "possible-match", "score": 3}]


@pytest.fixture
def school_client(monkeypatch: pytest.MonkeyPatch):
    service = StubSchoolService()
    monkeypatch.setattr(app_module, "SCHOOL_SERVICE", service, raising=False)
    monkeypatch.setattr(app_module, "pin_is_configured", lambda: True)
    monkeypatch.setitem(app_module.app.config, "TESTING", True)
    monkeypatch.setitem(app_module.app.config, "SECRET_KEY", "school-route-test")

    with app_module.app.test_client() as client:
        with client.session_transaction() as active_session:
            active_session["authenticated"] = True
        yield client, service


def test_list_and_read_routes_delegate_to_service(school_client) -> None:
    client, service = school_client

    listed = client.get("/api/schools")
    found = client.get("/api/schools/caledonia")
    missing = client.get("/api/schools/missing")

    assert listed.status_code == 200
    assert listed.get_json()[0]["id"] == "caledonia"
    assert found.status_code == 200
    assert found.get_json() == {
        "id": "caledonia",
        "broadcast_name": "Caledonia",
    }
    assert missing.status_code == 404
    assert missing.get_json() == {"error": "SCHOOL_NOT_FOUND"}
    assert ("read", "caledonia") in service.calls


def test_create_route_maps_validation_errors_and_success(school_client) -> None:
    client, service = school_client

    missing_name = client.post("/api/schools", json={"mode": "missing-name"})
    duplicate = client.post("/api/schools", json={"mode": "duplicate"})
    invalid_social = client.post(
        "/api/schools",
        json={"mode": "invalid-social"},
    )
    created = client.post(
        "/api/schools",
        json={"official_name": "New School", "broadcast_name": "New"},
    )

    assert missing_name.status_code == 400
    assert missing_name.get_json() == {"error": "SCHOOL_NAME_REQUIRED"}
    assert duplicate.status_code == 409
    assert duplicate.get_json() == {
        "error": "LIKELY_DUPLICATE",
        "matches": [{"id": "caledonia", "score": 5}],
    }
    assert invalid_social.status_code == 400
    assert invalid_social.get_json()["error"] == "INVALID_SOCIAL_URL"
    assert created.status_code == 201
    assert created.get_json()["id"] == "new-school"
    assert any(call[0] == "create" for call in service.calls)


def test_update_route_maps_errors_and_success(school_client) -> None:
    client, _service = school_client

    missing = client.put("/api/schools/missing", json={"city": "Caledonia"})
    invalid = client.put(
        "/api/schools/caledonia",
        json={"mode": "invalid-social"},
    )
    updated = client.put(
        "/api/schools/caledonia",
        json={"city": "Caledonia"},
    )

    assert missing.status_code == 404
    assert missing.get_json() == {"error": "SCHOOL_NOT_FOUND"}
    assert invalid.status_code == 400
    assert invalid.get_json()["error"] == "INVALID_SOCIAL_URL"
    assert updated.status_code == 200
    assert updated.get_json() == {"id": "caledonia", "city": "Caledonia"}


def test_delete_and_duplicate_check_preserve_contract(school_client) -> None:
    client, service = school_client

    missing = client.delete("/api/schools/missing")
    deleted = client.delete("/api/schools/caledonia")
    duplicate = client.post(
        "/api/schools/duplicate-check",
        json={"official_name": "Caledonia", "exclude_id": "caledonia"},
    )

    assert missing.status_code == 404
    assert missing.get_json() == {"error": "SCHOOL_NOT_FOUND"}
    assert deleted.status_code == 200
    assert deleted.get_json() == {"ok": True}
    assert duplicate.status_code == 200
    assert duplicate.get_json() == {
        "matches": [{"id": "possible-match", "score": 3}]
    }
    assert (
        "duplicate",
        (
            {"official_name": "Caledonia", "exclude_id": "caledonia"},
            "caledonia",
        ),
    ) in service.calls


