from __future__ import annotations

from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable

import pytest
from flask import Flask, jsonify, request

from routes.school_routes import SchoolRoutesDependencies, create_school_blueprint


@dataclass(frozen=True)
class StubResult:
    code: str
    data: dict[str, Any]

    @property
    def ok(self) -> bool:
        return self.code == "OK"


class StubSchoolService:
    def __init__(self) -> None:
        self.schools = [{"id": "caledonia", "official_name": "Caledonia"}]
        self.read_result = StubResult("OK", {"school": self.schools[0]})
        self.create_result = StubResult(
            "OK",
            {"school": {"id": "new-school", "official_name": "New School"}},
        )
        self.update_result = StubResult(
            "OK",
            {"school": {"id": "caledonia", "official_name": "Updated"}},
        )
        self.delete_result = StubResult("OK", {})
        self.create_payloads: list[dict[str, Any]] = []
        self.update_payloads: list[tuple[str, dict[str, Any]]] = []
        self.deleted_ids: list[str] = []
        self.duplicate_calls: list[tuple[dict[str, Any], str]] = []

    def list_schools(self) -> list[dict[str, Any]]:
        return self.schools

    def read(self, school_id: str) -> StubResult:
        return self.read_result

    def create(self, payload: dict[str, Any]) -> StubResult:
        self.create_payloads.append(payload)
        return self.create_result

    def update(self, school_id: str, payload: dict[str, Any]) -> StubResult:
        self.update_payloads.append((school_id, payload))
        return self.update_result

    def delete(self, school_id: str) -> StubResult:
        self.deleted_ids.append(school_id)
        return self.delete_result

    def duplicate_candidates(
        self,
        payload: dict[str, Any],
        exclude_id: str,
    ) -> list[dict[str, Any]]:
        self.duplicate_calls.append((payload, exclude_id))
        return [{"id": "similar-school"}]


@pytest.fixture
def school_client():
    service = StubSchoolService()

    def require_auth(view: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(view)
        def protected(*args: Any, **kwargs: Any):
            if request.headers.get("X-Test-Auth") != "yes":
                return jsonify({"error": "AUTH_REQUIRED"}), 401
            return view(*args, **kwargs)

        return protected

    app = Flask(__name__)
    app.config.update(TESTING=True)
    app.register_blueprint(
        create_school_blueprint(
            SchoolRoutesDependencies(
                require_auth=require_auth,
                get_school_service=lambda: service,
            )
        )
    )
    with app.test_client() as client:
        yield client, app, service


def auth_headers() -> dict[str, str]:
    return {"X-Test-Auth": "yes"}


def test_school_blueprint_registers_preserved_urls(school_client) -> None:
    _, app, _ = school_client
    routes = {
        (rule.rule, tuple(sorted(rule.methods - {"HEAD", "OPTIONS"})))
        for rule in app.url_map.iter_rules()
        if rule.rule.startswith("/api/schools")
    }
    assert ("/api/schools", ("GET",)) in routes
    assert ("/api/schools", ("POST",)) in routes
    assert ("/api/schools/<school_id>", ("GET",)) in routes
    assert ("/api/schools/<school_id>", ("PUT",)) in routes
    assert ("/api/schools/<school_id>", ("DELETE",)) in routes
    assert ("/api/schools/duplicate-check", ("POST",)) in routes


def test_school_routes_require_authentication(school_client) -> None:
    client, _, service = school_client
    response = client.get("/api/schools")
    assert response.status_code == 401
    assert response.get_json() == {"error": "AUTH_REQUIRED"}
    assert service.create_payloads == []


def test_list_and_read_school_delegate_to_service(school_client) -> None:
    client, _, _ = school_client
    listed = client.get("/api/schools", headers=auth_headers())
    read = client.get("/api/schools/caledonia", headers=auth_headers())
    assert listed.status_code == 200
    assert listed.get_json()[0]["id"] == "caledonia"
    assert read.status_code == 200
    assert read.get_json()["official_name"] == "Caledonia"


def test_read_school_maps_not_found(school_client) -> None:
    client, _, service = school_client
    service.read_result = StubResult("SCHOOL_NOT_FOUND", {})
    response = client.get("/api/schools/missing", headers=auth_headers())
    assert response.status_code == 404
    assert response.get_json() == {"error": "SCHOOL_NOT_FOUND"}


def test_create_school_delegates_payload_and_returns_created(school_client) -> None:
    client, _, service = school_client
    payload = {"official_name": "New School"}
    response = client.post(
        "/api/schools",
        json=payload,
        headers=auth_headers(),
    )
    assert response.status_code == 201
    assert response.get_json()["id"] == "new-school"
    assert service.create_payloads == [payload]


def test_create_school_preserves_validation_mappings(school_client) -> None:
    client, _, service = school_client
    cases = [
        (StubResult("SCHOOL_NAME_REQUIRED", {}), 400, {"error": "SCHOOL_NAME_REQUIRED"}),
        (
            StubResult("LIKELY_DUPLICATE", {"matches": [{"id": "dup"}]}),
            409,
            {"error": "LIKELY_DUPLICATE", "matches": [{"id": "dup"}]},
        ),
        (
            StubResult("INVALID_SOCIAL_URL", {"fields": {"x": "INVALID_URL"}}),
            400,
            {"error": "INVALID_SOCIAL_URL", "fields": {"x": "INVALID_URL"}},
        ),
    ]
    for result, status, expected in cases:
        service.create_result = result
        response = client.post(
            "/api/schools",
            json={"official_name": "Test"},
            headers=auth_headers(),
        )
        assert response.status_code == status
        assert response.get_json() == expected


def test_update_school_preserves_success_and_error_mappings(school_client) -> None:
    client, _, service = school_client
    response = client.put(
        "/api/schools/caledonia",
        json={"official_name": "Updated"},
        headers=auth_headers(),
    )
    assert response.status_code == 200
    assert response.get_json()["official_name"] == "Updated"
    assert service.update_payloads[-1] == (
        "caledonia",
        {"official_name": "Updated"},
    )

    service.update_result = StubResult("SCHOOL_NOT_FOUND", {})
    assert client.put(
        "/api/schools/missing",
        json={},
        headers=auth_headers(),
    ).status_code == 404

    service.update_result = StubResult(
        "INVALID_SOCIAL_URL",
        {"fields": {"website": "INVALID_URL"}},
    )
    invalid = client.put(
        "/api/schools/caledonia",
        json={},
        headers=auth_headers(),
    )
    assert invalid.status_code == 400
    assert invalid.get_json()["fields"] == {"website": "INVALID_URL"}


def test_delete_school_preserves_success_and_not_found(school_client) -> None:
    client, _, service = school_client
    deleted = client.delete(
        "/api/schools/caledonia",
        headers=auth_headers(),
    )
    assert deleted.status_code == 200
    assert deleted.get_json() == {"ok": True}
    assert service.deleted_ids == ["caledonia"]

    service.delete_result = StubResult("SCHOOL_NOT_FOUND", {})
    missing = client.delete("/api/schools/missing", headers=auth_headers())
    assert missing.status_code == 404
    assert missing.get_json() == {"error": "SCHOOL_NOT_FOUND"}


def test_duplicate_check_delegates_exclusion(school_client) -> None:
    client, _, service = school_client
    payload = {"official_name": "Caledonia", "exclude_id": "caledonia"}
    response = client.post(
        "/api/schools/duplicate-check",
        json=payload,
        headers=auth_headers(),
    )
    assert response.status_code == 200
    assert response.get_json() == {"matches": [{"id": "similar-school"}]}
    assert service.duplicate_calls == [(payload, "caledonia")]
