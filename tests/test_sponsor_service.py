from __future__ import annotations

import copy
from datetime import date
from typing import Any

from sponsor_service import SponsorService


class MemoryStore:
    def __init__(
        self,
        *,
        sponsors: list[dict[str, Any]] | None = None,
        assets: list[dict[str, Any]] | None = None,
    ) -> None:
        self.sponsors = copy.deepcopy(sponsors or [])
        self.assets = copy.deepcopy(assets or [])
        self.save_count = 0

    def load_sponsors(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self.sponsors)

    def save_sponsors(self, items: list[dict[str, Any]], *, force: bool = False) -> None:
        self.sponsors = copy.deepcopy(items)
        self.save_count += 1

    def load_assets(self) -> list[dict[str, Any]]:
        return copy.deepcopy(self.assets)


def make_service(store: MemoryStore) -> SponsorService:
    return SponsorService(
        load_sponsors=store.load_sponsors,
        save_sponsors=store.save_sponsors,
        load_assets=store.load_assets,
        clock=lambda: 1_700_000_000,
        today=lambda: date(2026, 7, 25),
        token_factory=lambda: "abc123",
    )


def sponsor(**overrides: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "id": "sponsor-1",
        "name": "Caledonia Bank",
        "category": "Local Business",
        "status": "Active",
        "contact_name": "Pat Contact",
        "email": "pat@example.com",
        "phone": "555-0100",
        "website": "https://example.com",
        "contract_start": "2026-01-01",
        "contract_end": "2026-12-31",
        "package": "General Sponsor",
        "lead_ins": ["Presented by:"],
        "asset_id": "asset-logo",
        "logo_url": "/old-logo.png",
        "notes": "",
        "active": True,
        "created_at": 1_600_000_000,
        "updated_at": 1_600_000_000,
    }
    record.update(overrides)
    return record


def logo_asset(**overrides: Any) -> dict[str, Any]:
    record: dict[str, Any] = {
        "id": "asset-logo",
        "name": "Caledonia Bank Logo",
        "category": "Sponsor",
        "asset_type": "Logo",
        "file_url": "/asset-files/bank.png",
        "active": True,
    }
    record.update(overrides)
    return record


def test_contract_state_expires_only_valid_past_dates() -> None:
    service = make_service(MemoryStore())

    assert service.contract_state(sponsor(contract_end="2026-07-24")) == "Expired"
    assert service.contract_state(sponsor(contract_end="2026-07-25")) == "Active"
    assert service.contract_state(sponsor(contract_end="not-a-date")) == "Active"


def test_list_payload_decorates_status_and_resolves_linked_asset() -> None:
    store = MemoryStore(
        sponsors=[sponsor()],
        assets=[
            logo_asset(),
            logo_asset(id="inactive", active=False),
            logo_asset(id="wrong", category="School"),
        ],
    )

    payload = make_service(store).list_payload()

    assert payload["sponsors"][0]["effective_status"] == "Active"
    assert payload["sponsors"][0]["contract_expired"] is False
    assert payload["sponsors"][0]["logo_url"] == "/asset-files/bank.png"
    assert payload["sponsors"][0]["asset_name"] == "Caledonia Bank Logo"
    assert [asset["id"] for asset in payload["logo_assets"]] == ["asset-logo"]


def test_create_validates_name_and_duplicate_confirmation() -> None:
    store = MemoryStore(sponsors=[sponsor()])
    service = make_service(store)

    missing = service.create({})
    duplicate = service.create({"name": " caledonia bank "})
    confirmed = service.create(
        {
            "name": "Caledonia Bank",
            "confirm_duplicate": True,
            "lead_ins": "Presented by:, Sponsored by:",
        }
    )

    assert missing.code == "SPONSOR_NAME_REQUIRED"
    assert duplicate.code == "DUPLICATE_SPONSOR"
    assert duplicate.data["duplicate_sponsor"]["id"] == "sponsor-1"
    assert confirmed.ok
    assert confirmed.data["sponsor"]["id"] == "sponsor-1700000000-abc123"
    assert confirmed.data["sponsor"]["lead_ins"] == [
        "Presented by:",
        "Sponsored by:",
    ]
    assert store.save_count == 1


def test_clean_record_strips_transient_fields_and_limits_values() -> None:
    service = make_service(MemoryStore())
    record = service.clean_record(
        {
            "name": "  Test Sponsor  ",
            "effective_status": "Expired",
            "contract_expired": True,
            "lead_ins": ["A", "", "B"],
            "notes": "x" * 4000,
        }
    )

    assert record["name"] == "Test Sponsor"
    assert "effective_status" not in record
    assert "contract_expired" not in record
    assert record["lead_ins"] == ["A", "B"]
    assert len(record["notes"]) == 3000


def test_update_preserves_created_at_and_blocks_duplicate_name() -> None:
    store = MemoryStore(
        sponsors=[
            sponsor(),
            sponsor(id="sponsor-2", name="Second Sponsor"),
        ]
    )
    service = make_service(store)

    duplicate = service.update("sponsor-1", {"name": "second sponsor"})
    updated = service.update(
        "sponsor-1",
        {
            "name": "Renamed Sponsor",
            "status": "Prospect",
            "effective_status": "Expired",
        },
    )
    missing = service.update("missing", {"name": "Missing"})

    assert duplicate.code == "DUPLICATE_SPONSOR"
    assert updated.ok
    assert updated.data["sponsor"]["name"] == "Renamed Sponsor"
    assert updated.data["sponsor"]["status"] == "Prospect"
    assert updated.data["sponsor"]["created_at"] == 1_600_000_000
    assert updated.data["sponsor"]["updated_at"] == 1_700_000_000
    assert "effective_status" not in updated.data["sponsor"]
    assert missing.code == "SPONSOR_NOT_FOUND"


def test_delete_reports_missing_and_removes_record() -> None:
    store = MemoryStore(sponsors=[sponsor()])
    service = make_service(store)

    missing = service.delete("missing")
    deleted = service.delete("sponsor-1")

    assert missing.code == "SPONSOR_NOT_FOUND"
    assert deleted.ok
    assert deleted.data == {"ok": True}
    assert store.sponsors == []


def test_link_asset_validates_type_supports_unlink_and_missing_sponsor() -> None:
    store = MemoryStore(
        sponsors=[sponsor(asset_id="", logo_url="")],
        assets=[
            logo_asset(),
            logo_asset(id="bad", category="School", asset_type="Logo"),
        ],
    )
    service = make_service(store)

    invalid = service.link_asset("sponsor-1", "bad")
    missing = service.link_asset("missing", "asset-logo")
    linked = service.link_asset("sponsor-1", "asset-logo")
    unlinked = service.link_asset("sponsor-1", "")

    assert invalid.code == "INVALID_SPONSOR_LOGO_ASSET"
    assert missing.code == "SPONSOR_NOT_FOUND"
    assert linked.ok
    assert linked.data["sponsor"]["logo_url"] == "/asset-files/bank.png"
    assert unlinked.ok
    assert unlinked.data["sponsor"]["asset_id"] == ""
    assert unlinked.data["asset"] is None


def test_active_sponsor_requires_active_contract_and_resolves_logo() -> None:
    store = MemoryStore(sponsors=[sponsor()], assets=[logo_asset()])
    service = make_service(store)

    active = service.active_sponsor_by_id("sponsor-1")
    store.sponsors[0]["active"] = False
    inactive = service.active_sponsor_by_id("sponsor-1")
    store.sponsors[0] = sponsor(contract_end="2026-01-01")
    expired = service.active_sponsor_by_id("sponsor-1")

    assert active is not None
    assert active["logo_url"] == "/asset-files/bank.png"
    assert inactive is None
    assert expired is None


def test_apply_to_graphic_handles_linked_stale_and_manual_sponsors() -> None:
    store = MemoryStore(sponsors=[sponsor()], assets=[logo_asset()])
    service = make_service(store)

    linked = service.apply_to_graphic({}, {"sponsor_id": "sponsor-1"})
    stale = service.apply_to_graphic(
        {
            "sponsor_id": "missing",
            "sponsor_name": "Old",
            "sponsor_logo": "/old.png",
            "sponsor_lead_in": "Old",
        },
        {},
    )
    manual = service.apply_to_graphic(
        {"sponsor_id": "sponsor-1"},
        {
            "sponsor_id": "",
            "sponsor_name": "Manual Sponsor",
            "sponsor_logo": "/manual.png",
            "sponsor_lead_in": "Sponsored by:",
        },
    )

    assert linked.data["warning"] == ""
    assert linked.data["graphic"]["sponsor_name"] == "Caledonia Bank"
    assert linked.data["graphic"]["sponsor_logo"] == "/asset-files/bank.png"
    assert stale.data["warning"] == "SPONSOR_EXPIRED_OR_INACTIVE"
    assert stale.data["graphic"]["sponsor_id"] == ""
    assert stale.data["graphic"]["sponsor_name"] == ""
    assert manual.data["graphic"]["sponsor_id"] == ""
    assert manual.data["graphic"]["sponsor_name"] == "Manual Sponsor"


