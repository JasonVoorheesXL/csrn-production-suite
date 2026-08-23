from __future__ import annotations

from typing import Any

import pytest

import app as app_module
from roster_service import RosterResult


class StubRosterService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.rosters = [
            {
                "id": "caledonia-football-2026-varsity-boys",
                "school_id": "caledonia",
                "school_name": "Caledonia",
                "sport": "Football",
                "season": "2026",
                "level": "Varsity",
                "division": "Boys",
                "players": [],
                "player_count": 0,
                "active_count": 0,
                "inactive_count": 0,
            }
        ]
        self.create_result = RosterResult(
            "OK",
            {"roster": self.rosters[0]},
        )
        self.update_result = RosterResult(
            "OK",
            {"roster": {**self.rosters[0], "season": "2027"}},
        )
        self.delete_result = RosterResult("OK", {"ok": True})

    def list_rosters(self) -> list[dict[str, Any]]:
        self.calls.append(("list_rosters", None))
        return self.rosters

    def create(self, incoming: dict[str, Any]) -> RosterResult:
        self.calls.append(("create", incoming))
        return self.create_result

    def update(
        self,
        roster_id: str,
        incoming: dict[str, Any],
    ) -> RosterResult:
        self.calls.append(("update", (roster_id, incoming)))
        return self.update_result

    def delete(self, roster_id: str) -> RosterResult:
        self.calls.append(("delete", roster_id))
        return self.delete_result


@pytest.fixture
def roster_client(monkeypatch: pytest.MonkeyPatch):
    service = StubRosterService()
    monkeypatch.setattr(app_module, "ROSTER_SERVICE", service, raising=False)
    monkeypatch.setattr(app_module, "pin_is_configured", lambda: True)
    monkeypatch.setitem(app_module.app.config, "TESTING", True)
    monkeypatch.setitem(
        app_module.app.config,
        "SECRET_KEY",
        "roster-route-test",
    )

    with app_module.app.test_client() as client:
        with client.session_transaction() as active_session:
            active_session["authenticated"] = True
        yield client, service


def test_list_rosters_route_delegates_to_service(roster_client) -> None:
    client, service = roster_client

    response = client.get("/api/rosters")

    assert response.status_code == 200
    assert response.get_json() == service.rosters
    assert service.calls == [("list_rosters", None)]


def test_create_roster_route_preserves_success_contract(roster_client) -> None:
    client, service = roster_client
    payload = {
        "school_id": "caledonia",
        "sport": "Football",
        "season": "2026",
        "level": "Varsity",
        "division": "Boys",
    }

    response = client.post("/api/rosters", json=payload)

    assert response.status_code == 201
    assert response.get_json() == service.create_result.data["roster"]
    assert service.calls == [("create", payload)]


def test_create_roster_route_maps_validation_and_duplicate_errors(
    roster_client,
) -> None:
    client, service = roster_client

    service.create_result = RosterResult("SCHOOL_AND_SEASON_REQUIRED")
    missing = client.post("/api/rosters", json={"school_id": "caledonia"})

    duplicate_roster = service.rosters[0]
    service.create_result = RosterResult(
        "ROSTER_ALREADY_EXISTS",
        {"roster": duplicate_roster},
    )
    duplicate = client.post(
        "/api/rosters",
        json={"school_id": "caledonia", "season": "2026"},
    )

    assert missing.status_code == 400
    assert missing.get_json() == {"error": "SCHOOL_AND_SEASON_REQUIRED"}
    assert duplicate.status_code == 409
    assert duplicate.get_json() == {
        "error": "ROSTER_ALREADY_EXISTS",
        "roster": duplicate_roster,
    }


def test_update_roster_route_preserves_contract_and_not_found(
    roster_client,
) -> None:
    client, service = roster_client
    payload = {"season": "2027"}

    updated = client.put(
        "/api/rosters/caledonia-football-2026-varsity-boys",
        json=payload,
    )

    assert updated.status_code == 200
    assert updated.get_json() == service.update_result.data["roster"]
    assert service.calls == [
        (
            "update",
            ("caledonia-football-2026-varsity-boys", payload),
        )
    ]

    service.calls.clear()
    service.update_result = RosterResult("ROSTER_NOT_FOUND")
    missing = client.put("/api/rosters/missing", json=payload)

    assert missing.status_code == 404
    assert missing.get_json() == {"error": "ROSTER_NOT_FOUND"}
    assert service.calls == [("update", ("missing", payload))]


def test_delete_roster_route_preserves_contract_and_not_found(
    roster_client,
) -> None:
    client, service = roster_client

    deleted = client.delete(
        "/api/rosters/caledonia-football-2026-varsity-boys"
    )

    assert deleted.status_code == 200
    assert deleted.get_json() == {"ok": True}
    assert service.calls == [
        ("delete", "caledonia-football-2026-varsity-boys")
    ]

    service.calls.clear()
    service.delete_result = RosterResult("ROSTER_NOT_FOUND")
    missing = client.delete("/api/rosters/missing")

    assert missing.status_code == 404
    assert missing.get_json() == {"error": "ROSTER_NOT_FOUND"}
    assert service.calls == [("delete", "missing")]


