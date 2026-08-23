from __future__ import annotations

from typing import Any

import pytest

import app as app_module
from roster_service import RosterResult


ROSTER_ID = "caledonia-football-2026-varsity-boys"
PLAYER_ID = "12-pat-player"


class StubRosterPlayerService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.player = {
            "id": PLAYER_ID,
            "number": "12",
            "first_name": "Pat",
            "last_name": "Player",
            "status": "active",
        }
        self.roster = {
            "id": ROSTER_ID,
            "school_id": "caledonia",
            "school_name": "Caledonia",
            "sport": "Football",
            "season": "2026",
            "level": "Varsity",
            "division": "Boys",
            "players": [self.player],
            "player_count": 1,
            "active_count": 1,
            "inactive_count": 0,
        }
        self.create_player_result = RosterResult(
            "OK",
            {"player": self.player, "warning": ""},
        )
        self.update_player_result = RosterResult(
            "OK",
            {
                "player": {**self.player, "preferred_name": "P"},
                "warning": "DUPLICATE_JERSEY_NUMBER",
            },
        )
        self.delete_player_result = RosterResult("OK", {"ok": True})
        self.import_players_result = RosterResult(
            "OK",
            {
                "added": 1,
                "warnings": ["Duplicate jersey number 12"],
                "roster": self.roster,
            },
        )

    def create_player(
        self,
        roster_id: str,
        incoming: dict[str, Any],
    ) -> RosterResult:
        self.calls.append(("create_player", (roster_id, incoming)))
        return self.create_player_result

    def update_player(
        self,
        roster_id: str,
        player_id: str,
        incoming: dict[str, Any],
    ) -> RosterResult:
        self.calls.append(
            ("update_player", (roster_id, player_id, incoming))
        )
        return self.update_player_result

    def delete_player(
        self,
        roster_id: str,
        player_id: str,
    ) -> RosterResult:
        self.calls.append(("delete_player", (roster_id, player_id)))
        return self.delete_player_result

    def import_players(
        self,
        roster_id: str,
        rows: Any,
    ) -> RosterResult:
        self.calls.append(("import_players", (roster_id, rows)))
        return self.import_players_result


@pytest.fixture
def roster_player_client(monkeypatch: pytest.MonkeyPatch):
    service = StubRosterPlayerService()
    monkeypatch.setattr(app_module, "ROSTER_SERVICE", service, raising=False)
    monkeypatch.setattr(app_module, "pin_is_configured", lambda: True)
    monkeypatch.setitem(app_module.app.config, "TESTING", True)
    monkeypatch.setitem(
        app_module.app.config,
        "SECRET_KEY",
        "roster-player-route-test",
    )

    with app_module.app.test_client() as client:
        with client.session_transaction() as active_session:
            active_session["authenticated"] = True
        yield client, service


def test_create_player_route_preserves_success_contract(
    roster_player_client,
) -> None:
    client, service = roster_player_client
    payload = {"number": "12", "first_name": "Pat", "last_name": "Player"}

    response = client.post(f"/api/rosters/{ROSTER_ID}/players", json=payload)

    assert response.status_code == 201
    assert response.get_json() == service.create_player_result.data
    assert service.calls == [("create_player", (ROSTER_ID, payload))]


def test_create_player_route_maps_validation_errors(
    roster_player_client,
) -> None:
    client, service = roster_player_client

    service.create_player_result = RosterResult("ROSTER_NOT_FOUND")
    missing_roster = client.post("/api/rosters/missing/players", json={})

    service.create_player_result = RosterResult("PLAYER_NAME_REQUIRED")
    missing_name = client.post(f"/api/rosters/{ROSTER_ID}/players", json={})

    assert missing_roster.status_code == 404
    assert missing_roster.get_json() == {"error": "ROSTER_NOT_FOUND"}
    assert missing_name.status_code == 400
    assert missing_name.get_json() == {"error": "PLAYER_NAME_REQUIRED"}


def test_update_player_route_preserves_contract_and_maps_missing_records(
    roster_player_client,
) -> None:
    client, service = roster_player_client
    payload = {"preferred_name": "P", "number": "12"}

    response = client.put(
        f"/api/rosters/{ROSTER_ID}/players/{PLAYER_ID}",
        json=payload,
    )

    assert response.status_code == 200
    assert response.get_json() == service.update_player_result.data
    assert service.calls == [
        ("update_player", (ROSTER_ID, PLAYER_ID, payload))
    ]

    service.update_player_result = RosterResult("ROSTER_NOT_FOUND")
    missing_roster = client.put(
        f"/api/rosters/missing/players/{PLAYER_ID}",
        json=payload,
    )
    service.update_player_result = RosterResult("PLAYER_NOT_FOUND")
    missing_player = client.put(
        f"/api/rosters/{ROSTER_ID}/players/missing",
        json=payload,
    )

    assert missing_roster.status_code == 404
    assert missing_roster.get_json() == {"error": "ROSTER_NOT_FOUND"}
    assert missing_player.status_code == 404
    assert missing_player.get_json() == {"error": "PLAYER_NOT_FOUND"}


def test_delete_player_route_preserves_contract_and_maps_missing_records(
    roster_player_client,
) -> None:
    client, service = roster_player_client

    response = client.delete(
        f"/api/rosters/{ROSTER_ID}/players/{PLAYER_ID}"
    )

    assert response.status_code == 200
    assert response.get_json() == {"ok": True}
    assert service.calls == [("delete_player", (ROSTER_ID, PLAYER_ID))]

    service.delete_player_result = RosterResult("ROSTER_NOT_FOUND")
    missing_roster = client.delete(
        f"/api/rosters/missing/players/{PLAYER_ID}"
    )
    service.delete_player_result = RosterResult("PLAYER_NOT_FOUND")
    missing_player = client.delete(
        f"/api/rosters/{ROSTER_ID}/players/missing"
    )

    assert missing_roster.status_code == 404
    assert missing_roster.get_json() == {"error": "ROSTER_NOT_FOUND"}
    assert missing_player.status_code == 404
    assert missing_player.get_json() == {"error": "PLAYER_NOT_FOUND"}


def test_import_players_route_preserves_success_contract(
    roster_player_client,
) -> None:
    client, service = roster_player_client
    rows = [{"number": "12", "first_name": "Pat", "last_name": "Player"}]

    response = client.post(
        f"/api/rosters/{ROSTER_ID}/players/import",
        json={"players": rows},
    )

    assert response.status_code == 200
    assert response.get_json() == service.import_players_result.data
    assert service.calls == [("import_players", (ROSTER_ID, rows))]


def test_import_players_route_maps_validation_errors(
    roster_player_client,
) -> None:
    client, service = roster_player_client

    service.import_players_result = RosterResult("INVALID_PLAYER_LIST")
    invalid = client.post(
        f"/api/rosters/{ROSTER_ID}/players/import",
        json={"players": {}},
    )

    service.import_players_result = RosterResult("ROSTER_NOT_FOUND")
    missing = client.post(
        "/api/rosters/missing/players/import",
        json={"players": []},
    )

    assert invalid.status_code == 400
    assert invalid.get_json() == {"error": "INVALID_PLAYER_LIST"}
    assert missing.status_code == 404
    assert missing.get_json() == {"error": "ROSTER_NOT_FOUND"}


