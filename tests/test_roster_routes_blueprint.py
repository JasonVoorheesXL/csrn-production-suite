from __future__ import annotations

from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable

import pytest
from flask import Flask, jsonify, request

from routes.roster_routes import RosterRoutesDependencies, create_roster_blueprint


@dataclass(frozen=True)
class StubResult:
    code: str
    data: dict[str, Any]


class StubRosterService:
    def __init__(self) -> None:
        self.create_result = StubResult("OK", {"roster": {"id": "r1"}})
        self.update_result = StubResult("OK", {"roster": {"id": "r1"}})
        self.delete_result = StubResult("OK", {})
        self.create_player_result = StubResult("OK", {"player": {"id": "p1"}})
        self.update_player_result = StubResult("OK", {"player": {"id": "p1"}})
        self.delete_player_result = StubResult("OK", {})
        self.import_result = StubResult("OK", {"imported": 2})
        self.calls: list[tuple[str, Any]] = []

    def list_rosters(self) -> list[dict[str, Any]]:
        self.calls.append(("list", None))
        return [{"id": "r1"}]

    def create(self, payload: dict[str, Any]) -> StubResult:
        self.calls.append(("create", payload))
        return self.create_result

    def update(self, roster_id: str, payload: dict[str, Any]) -> StubResult:
        self.calls.append(("update", (roster_id, payload)))
        return self.update_result

    def delete(self, roster_id: str) -> StubResult:
        self.calls.append(("delete", roster_id))
        return self.delete_result

    def create_player(self, roster_id: str, payload: dict[str, Any]) -> StubResult:
        self.calls.append(("create_player", (roster_id, payload)))
        return self.create_player_result

    def update_player(self, roster_id: str, player_id: str, payload: dict[str, Any]) -> StubResult:
        self.calls.append(("update_player", (roster_id, player_id, payload)))
        return self.update_player_result

    def delete_player(self, roster_id: str, player_id: str) -> StubResult:
        self.calls.append(("delete_player", (roster_id, player_id)))
        return self.delete_player_result

    def import_players(self, roster_id: str, players: Any) -> StubResult:
        self.calls.append(("import", (roster_id, players)))
        return self.import_result


@pytest.fixture
def roster_client():
    service = StubRosterService()

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
        create_roster_blueprint(
            RosterRoutesDependencies(
                require_auth=require_auth,
                get_roster_service=lambda: service,
            )
        )
    )
    with app.test_client() as client:
        yield client, app, service


def auth_headers() -> dict[str, str]:
    return {"X-Test-Auth": "yes"}


def test_roster_blueprint_registers_preserved_urls(roster_client) -> None:
    _, app, _ = roster_client
    paths = {rule.rule for rule in app.url_map.iter_rules()}
    assert {
        "/api/rosters",
        "/api/rosters/<roster_id>",
        "/api/rosters/<roster_id>/players",
        "/api/rosters/<roster_id>/players/<player_id>",
        "/api/rosters/<roster_id>/players/import",
    }.issubset(paths)


def test_roster_routes_require_authentication(roster_client) -> None:
    client, _, service = roster_client
    response = client.get("/api/rosters")
    assert response.status_code == 401
    assert service.calls == []


def test_list_rosters_delegates(roster_client) -> None:
    client, _, service = roster_client
    response = client.get("/api/rosters", headers=auth_headers())
    assert response.status_code == 200
    assert response.get_json() == [{"id": "r1"}]
    assert service.calls[-1] == ("list", None)


def test_create_roster_preserves_success_and_conflict_mappings(roster_client) -> None:
    client, _, service = roster_client
    assert client.post("/api/rosters", json={"school_id": "chs"}, headers=auth_headers()).status_code == 201
    service.create_result = StubResult("SCHOOL_AND_SEASON_REQUIRED", {})
    assert client.post("/api/rosters", json={}, headers=auth_headers()).status_code == 400
    service.create_result = StubResult("ROSTER_ALREADY_EXISTS", {"roster": {"id": "r1"}})
    conflict = client.post("/api/rosters", json={}, headers=auth_headers())
    assert conflict.status_code == 409
    assert conflict.get_json()["roster"]["id"] == "r1"


def test_update_and_delete_roster_preserve_not_found_mapping(roster_client) -> None:
    client, _, service = roster_client
    assert client.put("/api/rosters/r1", json={"season": "2026"}, headers=auth_headers()).status_code == 200
    service.update_result = StubResult("ROSTER_NOT_FOUND", {})
    assert client.put("/api/rosters/missing", json={}, headers=auth_headers()).status_code == 404
    service.delete_result = StubResult("ROSTER_NOT_FOUND", {})
    assert client.delete("/api/rosters/missing", headers=auth_headers()).status_code == 404


def test_create_player_preserves_validation_mappings(roster_client) -> None:
    client, _, service = roster_client
    assert client.post("/api/rosters/r1/players", json={"name": "Player"}, headers=auth_headers()).status_code == 201
    service.create_player_result = StubResult("PLAYER_NAME_REQUIRED", {})
    assert client.post("/api/rosters/r1/players", json={}, headers=auth_headers()).status_code == 400
    service.create_player_result = StubResult("ROSTER_NOT_FOUND", {})
    assert client.post("/api/rosters/missing/players", json={}, headers=auth_headers()).status_code == 404


def test_update_and_delete_player_preserve_not_found_mapping(roster_client) -> None:
    client, _, service = roster_client
    assert client.put("/api/rosters/r1/players/p1", json={"number": "7"}, headers=auth_headers()).status_code == 200
    service.update_player_result = StubResult("PLAYER_NOT_FOUND", {})
    assert client.put("/api/rosters/r1/players/missing", json={}, headers=auth_headers()).status_code == 404
    service.delete_player_result = StubResult("ROSTER_NOT_FOUND", {})
    assert client.delete("/api/rosters/missing/players/p1", headers=auth_headers()).status_code == 404


def test_import_players_delegates_and_preserves_errors(roster_client) -> None:
    client, _, service = roster_client
    response = client.post(
        "/api/rosters/r1/players/import",
        json={"players": [{"name": "One"}, {"name": "Two"}]},
        headers=auth_headers(),
    )
    assert response.status_code == 200
    assert service.calls[-1] == ("import", ("r1", [{"name": "One"}, {"name": "Two"}]))
    service.import_result = StubResult("INVALID_PLAYER_LIST", {})
    assert client.post("/api/rosters/r1/players/import", json={}, headers=auth_headers()).status_code == 400
    service.import_result = StubResult("ROSTER_NOT_FOUND", {})
    assert client.post("/api/rosters/missing/players/import", json={}, headers=auth_headers()).status_code == 404


