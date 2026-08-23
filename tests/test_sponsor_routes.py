from __future__ import annotations

from typing import Any

import pytest

import app as app_module
from sponsor_service import SponsorResult


if not hasattr(app_module, "get_sponsor_service"):
    pytest.skip(
        "SponsorService routes are not integrated yet.",
        allow_module_level=True,
    )


SPONSOR_ID = "sponsor-1"


class StubSponsorService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.sponsor = {
            "id": SPONSOR_ID,
            "name": "Caledonia Bank",
            "status": "Active",
            "effective_status": "Active",
            "contract_expired": False,
            "asset_id": "asset-logo",
            "logo_url": "/asset-files/bank.png",
        }
        self.asset = {
            "id": "asset-logo",
            "name": "Caledonia Bank Logo",
            "category": "Sponsor",
            "asset_type": "Logo",
            "file_url": "/asset-files/bank.png",
        }
        self.list_result = {
            "sponsors": [self.sponsor],
            "logo_assets": [self.asset],
        }
        self.create_result = SponsorResult("OK", {"sponsor": self.sponsor})
        self.update_result = SponsorResult("OK", {"sponsor": self.sponsor})
        self.delete_result = SponsorResult("OK", {"ok": True})
        self.link_result = SponsorResult(
            "OK",
            {"sponsor": self.sponsor, "asset": self.asset},
        )

    def list_payload(self) -> dict[str, Any]:
        self.calls.append(("list_payload", None))
        return self.list_result

    def create(self, incoming: dict[str, Any]) -> SponsorResult:
        self.calls.append(("create", incoming))
        return self.create_result

    def update(
        self,
        sponsor_id: str,
        incoming: dict[str, Any],
    ) -> SponsorResult:
        self.calls.append(("update", (sponsor_id, incoming)))
        return self.update_result

    def delete(self, sponsor_id: str) -> SponsorResult:
        self.calls.append(("delete", sponsor_id))
        return self.delete_result

    def link_asset(self, sponsor_id: str, asset_id: str) -> SponsorResult:
        self.calls.append(("link_asset", (sponsor_id, asset_id)))
        return self.link_result


@pytest.fixture
def sponsor_client(monkeypatch: pytest.MonkeyPatch):
    service = StubSponsorService()
    monkeypatch.setattr(app_module, "SPONSOR_SERVICE", service, raising=False)
    monkeypatch.setattr(app_module, "pin_is_configured", lambda: True)
    monkeypatch.setitem(app_module.app.config, "TESTING", True)
    monkeypatch.setitem(
        app_module.app.config,
        "SECRET_KEY",
        "sponsor-route-test",
    )

    with app_module.app.test_client() as client:
        with client.session_transaction() as active_session:
            active_session["authenticated"] = True
        yield client, service


def test_list_sponsors_route_delegates_to_service(sponsor_client) -> None:
    client, service = sponsor_client

    response = client.get("/api/sponsors")

    assert response.status_code == 200
    assert response.get_json() == service.list_result
    assert service.calls == [("list_payload", None)]


def test_create_sponsor_route_preserves_success_and_validation_contracts(
    sponsor_client,
) -> None:
    client, service = sponsor_client
    payload = {"name": "Caledonia Bank"}

    created = client.post("/api/sponsors", json=payload)

    assert created.status_code == 200
    assert created.get_json() == {"sponsor": service.sponsor}
    assert service.calls == [("create", payload)]

    service.create_result = SponsorResult("SPONSOR_NAME_REQUIRED")
    missing = client.post("/api/sponsors", json={})

    assert missing.status_code == 400
    assert missing.get_json() == {"error": "Sponsor name is required."}


def test_create_sponsor_route_preserves_duplicate_contract(
    sponsor_client,
) -> None:
    client, service = sponsor_client
    service.create_result = SponsorResult(
        "DUPLICATE_SPONSOR",
        {"duplicate_sponsor": service.sponsor},
    )

    response = client.post("/api/sponsors", json={"name": "Caledonia Bank"})

    assert response.status_code == 409
    assert response.get_json() == {
        "error": "DUPLICATE_SPONSOR",
        "duplicate_sponsor": service.sponsor,
    }


def test_update_sponsor_route_preserves_contracts(sponsor_client) -> None:
    client, service = sponsor_client
    payload = {"status": "Prospect"}

    updated = client.put(f"/api/sponsors/{SPONSOR_ID}", json=payload)

    assert updated.status_code == 200
    assert updated.get_json() == {"sponsor": service.sponsor}
    assert service.calls == [("update", (SPONSOR_ID, payload))]

    service.update_result = SponsorResult("SPONSOR_NOT_FOUND")
    missing = client.put("/api/sponsors/missing", json=payload)
    assert missing.status_code == 404
    assert missing.get_json() == {"error": "Sponsor not found."}

    service.update_result = SponsorResult(
        "DUPLICATE_SPONSOR",
        {"duplicate_sponsor": service.sponsor},
    )
    duplicate = client.put(f"/api/sponsors/{SPONSOR_ID}", json=payload)
    assert duplicate.status_code == 409
    assert duplicate.get_json() == {
        "error": "DUPLICATE_SPONSOR",
        "duplicate_sponsor": service.sponsor,
    }


def test_delete_sponsor_route_preserves_contracts(sponsor_client) -> None:
    client, service = sponsor_client

    deleted = client.delete(f"/api/sponsors/{SPONSOR_ID}")

    assert deleted.status_code == 200
    assert deleted.get_json() == {"ok": True}
    assert service.calls == [("delete", SPONSOR_ID)]

    service.delete_result = SponsorResult("SPONSOR_NOT_FOUND")
    missing = client.delete("/api/sponsors/missing")
    assert missing.status_code == 404
    assert missing.get_json() == {"error": "Sponsor not found."}


def test_link_asset_route_preserves_success_and_error_contracts(
    sponsor_client,
) -> None:
    client, service = sponsor_client

    linked = client.put(
        f"/api/sponsors/{SPONSOR_ID}/asset",
        json={"asset_id": "asset-logo"},
    )

    assert linked.status_code == 200
    assert linked.get_json() == {
        "sponsor": service.sponsor,
        "asset": service.asset,
    }
    assert service.calls == [("link_asset", (SPONSOR_ID, "asset-logo"))]

    service.link_result = SponsorResult("INVALID_SPONSOR_LOGO_ASSET")
    invalid = client.put(
        f"/api/sponsors/{SPONSOR_ID}/asset",
        json={"asset_id": "bad"},
    )
    assert invalid.status_code == 400
    assert invalid.get_json() == {
        "error": "Choose a valid Sponsor Logo asset."
    }

    service.link_result = SponsorResult("SPONSOR_NOT_FOUND")
    missing = client.put(
        "/api/sponsors/missing/asset",
        json={"asset_id": "asset-logo"},
    )
    assert missing.status_code == 404
    assert missing.get_json() == {"error": "Sponsor not found."}


