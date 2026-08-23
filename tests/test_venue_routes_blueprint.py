from __future__ import annotations

from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable

import pytest
from flask import Flask, jsonify, request

from routes.venue_routes import VenueRoutesDependencies, create_venue_blueprint


@dataclass(frozen=True)
class StubResult:
    code: str
    data: dict[str, Any]


class StubVenueService:
    def __init__(self) -> None:
        self.list_result = StubResult("OK", {"venues": [{"id": "v1"}]})
        self.read_result = StubResult("OK", {"venue": {"id": "v1"}})
        self.create_result = StubResult("OK", {"venue": {"id": "v1"}})
        self.update_result = StubResult("OK", {"venue": {"id": "v1"}})
        self.delete_result = StubResult("OK", {"deleted": True})
        self.calls: list[tuple[str, Any]] = []

    def list_venues(self, **kwargs: Any) -> StubResult:
        self.calls.append(("list", kwargs))
        return self.list_result

    def read(self, venue_id: str) -> StubResult:
        self.calls.append(("read", venue_id))
        return self.read_result

    def create(self, payload: dict[str, Any]) -> StubResult:
        self.calls.append(("create", payload))
        return self.create_result

    def update(self, venue_id: str, payload: dict[str, Any]) -> StubResult:
        self.calls.append(("update", (venue_id, payload)))
        return self.update_result

    def delete(self, venue_id: str) -> StubResult:
        self.calls.append(("delete", venue_id))
        return self.delete_result


@pytest.fixture
def venue_client():
    service = StubVenueService()

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
        create_venue_blueprint(
            VenueRoutesDependencies(
                require_auth=require_auth,
                get_venue_service=lambda: service,
            )
        )
    )
    with app.test_client() as client:
        yield client, app, service


def auth_headers() -> dict[str, str]:
    return {"X-Test-Auth": "yes"}


def test_venue_blueprint_registers_preserved_urls(venue_client) -> None:
    _, app, _ = venue_client
    paths = {rule.rule for rule in app.url_map.iter_rules()}
    assert "/api/venues" in paths
    assert "/api/venues/<venue_id>" in paths


def test_venue_routes_require_authentication(venue_client) -> None:
    client, _, service = venue_client
    response = client.get("/api/venues")
    assert response.status_code == 401
    assert service.calls == []


def test_list_venues_maps_filters(venue_client) -> None:
    client, _, service = venue_client
    response = client.get(
        "/api/venues?school_id=chs&sport=Football&include_inactive=false",
        headers=auth_headers(),
    )
    assert response.status_code == 200
    assert response.get_json() == [{"id": "v1"}]
    assert service.calls[-1] == (
        "list",
        {"school_id": "chs", "sport": "Football", "include_inactive": False},
    )


def test_read_venue_preserves_not_found_mapping(venue_client) -> None:
    client, _, service = venue_client
    assert client.get("/api/venues/v1", headers=auth_headers()).status_code == 200
    service.read_result = StubResult("VENUE_NOT_FOUND", {})
    assert client.get("/api/venues/missing", headers=auth_headers()).status_code == 404


def test_create_venue_preserves_validation_and_duplicate_mappings(venue_client) -> None:
    client, _, service = venue_client
    assert client.post("/api/venues", json={"name": "Field"}, headers=auth_headers()).status_code == 201
    service.create_result = StubResult("VENUE_NAME_REQUIRED", {})
    assert client.post("/api/venues", json={}, headers=auth_headers()).status_code == 400
    service.create_result = StubResult("DUPLICATE_VENUE", {"duplicate_venue": {"id": "v1"}})
    duplicate = client.post("/api/venues", json={}, headers=auth_headers())
    assert duplicate.status_code == 409
    assert duplicate.get_json()["duplicate_venue"]["id"] == "v1"


def test_update_venue_preserves_error_mappings(venue_client) -> None:
    client, _, service = venue_client
    assert client.put("/api/venues/v1", json={"name": "Field"}, headers=auth_headers()).status_code == 200
    service.update_result = StubResult("VENUE_NOT_FOUND", {})
    assert client.put("/api/venues/missing", json={}, headers=auth_headers()).status_code == 404
    service.update_result = StubResult("VENUE_NAME_REQUIRED", {})
    assert client.put("/api/venues/v1", json={}, headers=auth_headers()).status_code == 400
    service.update_result = StubResult("DUPLICATE_VENUE", {"duplicate_venue": {"id": "v2"}})
    assert client.put("/api/venues/v1", json={}, headers=auth_headers()).status_code == 409


def test_delete_venue_preserves_not_found_and_in_use_mappings(venue_client) -> None:
    client, _, service = venue_client
    assert client.delete("/api/venues/v1", headers=auth_headers()).get_json() == {"deleted": True}
    service.delete_result = StubResult("VENUE_NOT_FOUND", {})
    assert client.delete("/api/venues/missing", headers=auth_headers()).status_code == 404
    service.delete_result = StubResult("VENUE_IN_USE", {"references": ["broadcast"]})
    blocked = client.delete("/api/venues/v1", headers=auth_headers())
    assert blocked.status_code == 409
    assert blocked.get_json()["references"] == ["broadcast"]


