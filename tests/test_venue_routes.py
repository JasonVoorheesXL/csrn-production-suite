from __future__ import annotations

from typing import Any

import pytest

import app as app_module
from venue_service import VenueResult


if not hasattr(app_module, "get_venue_service"):
    pytest.skip(
        "VenueService routes are not integrated yet.",
        allow_module_level=True,
    )


VENUE_ID = "caledonia-football"


class StubVenueService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.venue = {
            "id": VENUE_ID,
            "school_id": "caledonia",
            "sport": "Football",
            "name": "Caledonia HS Football Field",
        }
        self.list_result = VenueResult("OK", {"venues": [self.venue]})
        self.read_result = VenueResult("OK", {"venue": self.venue})
        self.create_result = VenueResult("OK", {"venue": self.venue})
        self.update_result = VenueResult("OK", {"venue": self.venue})
        self.delete_result = VenueResult(
            "OK",
            {"ok": True, "deleted": VENUE_ID},
        )

    def list_venues(
        self,
        *,
        school_id: str = "",
        sport: str = "",
        include_inactive: bool = True,
    ) -> VenueResult:
        self.calls.append(
            (
                "list_venues",
                {
                    "school_id": school_id,
                    "sport": sport,
                    "include_inactive": include_inactive,
                },
            )
        )
        return self.list_result

    def read(self, venue_id: str) -> VenueResult:
        self.calls.append(("read", venue_id))
        return self.read_result

    def create(self, incoming: dict[str, Any]) -> VenueResult:
        self.calls.append(("create", incoming))
        return self.create_result

    def update(
        self,
        venue_id: str,
        incoming: dict[str, Any],
    ) -> VenueResult:
        self.calls.append(("update", (venue_id, incoming)))
        return self.update_result

    def delete(self, venue_id: str) -> VenueResult:
        self.calls.append(("delete", venue_id))
        return self.delete_result


@pytest.fixture
def venue_client(monkeypatch: pytest.MonkeyPatch):
    service = StubVenueService()
    monkeypatch.setattr(app_module, "VENUE_SERVICE", service, raising=False)
    monkeypatch.setattr(app_module, "pin_is_configured", lambda: True)
    monkeypatch.setitem(app_module.app.config, "TESTING", True)
    monkeypatch.setitem(
        app_module.app.config,
        "SECRET_KEY",
        "venue-route-test",
    )

    with app_module.app.test_client() as client:
        with client.session_transaction() as active_session:
            active_session["authenticated"] = True
        yield client, service


def test_list_venues_preserves_array_contract_and_filters(venue_client) -> None:
    client, service = venue_client

    response = client.get(
        "/api/venues?school_id=caledonia&sport=Football&include_inactive=false"
    )

    assert response.status_code == 200
    assert response.get_json() == [service.venue]
    assert service.calls == [
        (
            "list_venues",
            {
                "school_id": "caledonia",
                "sport": "Football",
                "include_inactive": False,
            },
        )
    ]


def test_read_venue_preserves_success_and_missing_contracts(venue_client) -> None:
    client, service = venue_client

    found = client.get(f"/api/venues/{VENUE_ID}")
    assert found.status_code == 200
    assert found.get_json() == service.venue

    service.read_result = VenueResult("VENUE_NOT_FOUND")
    missing = client.get("/api/venues/missing")
    assert missing.status_code == 404
    assert missing.get_json() == {"error": "VENUE_NOT_FOUND"}


def test_create_venue_preserves_validation_and_duplicate_contracts(
    venue_client,
) -> None:
    client, service = venue_client
    payload = {"name": "Caledonia HS Football Field"}

    created = client.post("/api/venues", json=payload)
    assert created.status_code == 201
    assert created.get_json() == service.venue
    assert service.calls == [("create", payload)]

    service.create_result = VenueResult("VENUE_NAME_REQUIRED")
    missing_name = client.post("/api/venues", json={})
    assert missing_name.status_code == 400
    assert missing_name.get_json() == {"error": "VENUE_NAME_REQUIRED"}

    service.create_result = VenueResult(
        "DUPLICATE_VENUE",
        {"duplicate_venue": service.venue},
    )
    duplicate = client.post("/api/venues", json=payload)
    assert duplicate.status_code == 409
    assert duplicate.get_json() == {
        "error": "DUPLICATE_VENUE",
        "duplicate_venue": service.venue,
    }


def test_update_venue_preserves_contracts(venue_client) -> None:
    client, service = venue_client
    payload = {"name": "Cavalier Stadium"}

    updated = client.put(f"/api/venues/{VENUE_ID}", json=payload)
    assert updated.status_code == 200
    assert updated.get_json() == service.venue
    assert service.calls == [("update", (VENUE_ID, payload))]

    service.update_result = VenueResult("VENUE_NOT_FOUND")
    missing = client.put("/api/venues/missing", json=payload)
    assert missing.status_code == 404
    assert missing.get_json() == {"error": "VENUE_NOT_FOUND"}

    service.update_result = VenueResult(
        "DUPLICATE_VENUE",
        {"duplicate_venue": service.venue},
    )
    duplicate = client.put(f"/api/venues/{VENUE_ID}", json=payload)
    assert duplicate.status_code == 409
    assert duplicate.get_json() == {
        "error": "DUPLICATE_VENUE",
        "duplicate_venue": service.venue,
    }


def test_delete_venue_preserves_missing_and_in_use_contracts(venue_client) -> None:
    client, service = venue_client

    deleted = client.delete(f"/api/venues/{VENUE_ID}")
    assert deleted.status_code == 200
    assert deleted.get_json() == {"ok": True, "deleted": VENUE_ID}
    assert service.calls == [("delete", VENUE_ID)]

    service.delete_result = VenueResult("VENUE_NOT_FOUND")
    missing = client.delete("/api/venues/missing")
    assert missing.status_code == 404
    assert missing.get_json() == {"error": "VENUE_NOT_FOUND"}

    references = {
        "schools": [{"id": "caledonia", "name": "Caledonia"}],
        "broadcasts": [],
    }
    service.delete_result = VenueResult("VENUE_IN_USE", references)
    blocked = client.delete(f"/api/venues/{VENUE_ID}")
    assert blocked.status_code == 409
    assert blocked.get_json() == {"error": "VENUE_IN_USE", **references}


