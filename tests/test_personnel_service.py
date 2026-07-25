from __future__ import annotations

import copy

from personnel_service import PersonnelService


class Store:
    def __init__(self, rows=None) -> None:
        self.rows = copy.deepcopy(rows or [])
        self.saved: list[list[dict]] = []

    def load(self):
        return copy.deepcopy(self.rows)

    def save(self, rows):
        self.rows = copy.deepcopy(rows)
        self.saved.append(copy.deepcopy(rows))


def service(store: Store, *, now: float = 1000.0) -> PersonnelService:
    return PersonnelService(
        load_personnel=store.load,
        save_personnel=store.save,
        clock=lambda: now,
    )


def record(personnel_id: str = "jason") -> dict:
    return {
        "id": personnel_id,
        "full_name": "Jason Voorhees",
        "name": "Jason Voorhees",
        "preferred_name": "Jason",
        "pronunciation": "",
        "pronunciation_verified": False,
        "category": "Broadcast Talent",
        "role": "Play-by-Play",
        "primary_role": "Play-by-Play",
        "title": "Play-by-Play",
        "organization": "CSRN",
        "school_id": "caledonia",
        "bio": "",
        "headshot": "",
        "status": "active",
        "producer": False,
        "social": {
            "facebook": "",
            "x": "",
            "instagram": "",
            "youtube": "",
            "website": "",
        },
        "created_at": 900,
        "updated_at": 900,
    }


def test_normalize_id_and_headshot_url() -> None:
    assert PersonnelService.normalize_id(" Jason  Voorhees! ") == "jason-voorhees"
    assert PersonnelService.normalize_id("") == "staff-member"
    assert (
        PersonnelService.normalize_headshot_url(
            r"Data\Personnel\Headshots\jason.png"
        )
        == "/personnel-headshots/jason.png"
    )


def test_normalize_social_handles_and_urls() -> None:
    value, valid, message = PersonnelService.normalize_social_url("x", "@CSRN")
    assert value == "https://x.com/CSRN"
    assert valid is True
    assert message == ""

    website, valid, _ = PersonnelService.normalize_social_url(
        "website",
        "csrnsports.com",
    )
    assert website == "https://csrnsports.com"
    assert valid is True


def test_invalid_social_domain_is_reported() -> None:
    normalized, errors = PersonnelService.normalize_social_block(
        {"facebook": "https://example.com/not-facebook"}
    )
    assert normalized["facebook"] == "https://example.com/not-facebook"
    assert "facebook" in errors


def test_migrate_legacy_record_preserves_compatible_fields() -> None:
    migrated = PersonnelService.migrate_record(
        {
            "id": "jordan",
            "name": "Jordan",
            "primary_role": "Color Analyst",
            "headshot": "data/Personnel/Headshots/jordan.jpg",
        }
    )
    assert migrated["full_name"] == "Jordan"
    assert migrated["role"] == "Color Analyst"
    assert migrated["category"] == "Broadcast Talent"
    assert migrated["headshot"] == "/personnel-headshots/jordan.jpg"


def test_list_records_filters_and_sorts() -> None:
    active = record("z-person")
    active["full_name"] = active["name"] = "Zed Person"
    inactive = record("a-person")
    inactive["full_name"] = inactive["name"] = "Alpha Person"
    inactive["status"] = "inactive"
    inactive["role"] = inactive["primary_role"] = "Producer"
    inactive["category"] = "Production Staff"
    store = Store([active, inactive])

    result = service(store).list_records(include_inactive=False)
    assert [row["id"] for row in result.data["personnel"]] == ["z-person"]

    filtered = service(store).list_records(role="Producer")
    assert [row["id"] for row in filtered.data["personnel"]] == ["a-person"]


def test_create_validates_required_name_role_and_social() -> None:
    subject = service(Store())
    assert subject.create({}).code == "STAFF_NAME_REQUIRED"
    assert subject.create({"full_name": "Test", "role": "Invalid"}).code == "INVALID_STAFF_ROLE"
    invalid = subject.create(
        {
            "full_name": "Test",
            "role": "Other",
            "social": {"youtube": "https://example.com/video"},
        }
    )
    assert invalid.code == "INVALID_SOCIAL_URL"
    assert "youtube" in invalid.data["fields"]


def test_create_generates_unique_ids_and_timestamps() -> None:
    store = Store([record("jason-voorhees")])
    result = service(store).create(
        {
            "full_name": "Jason Voorhees",
            "role": "Play-by-Play",
            "category": "Broadcast Talent",
        }
    )
    assert result.ok
    assert result.data["personnel"]["id"] == "jason-voorhees-2"
    assert result.data["personnel"]["created_at"] == 1000
    assert store.rows[-1]["id"] == "jason-voorhees-2"


def test_update_preserves_id_and_created_at() -> None:
    store = Store([record()])
    result = service(store, now=1100).update(
        "jason",
        {
            "full_name": "Jason V.",
            "role": "Producer",
            "category": "Production Staff",
        },
    )
    assert result.ok
    updated = result.data["personnel"]
    assert updated["id"] == "jason"
    assert updated["created_at"] == 900
    assert updated["updated_at"] == 1100
    assert updated["role"] == "Producer"


def test_read_and_update_missing_records() -> None:
    subject = service(Store())
    assert subject.read("missing").code == "BROADCASTER_NOT_FOUND"
    assert subject.update("missing", {"full_name": "Missing"}).code == "BROADCASTER_NOT_FOUND"


def test_delete_existing_and_missing_records() -> None:
    store = Store([record()])
    subject = service(store)
    result = subject.delete("jason")
    assert result.data == {"ok": True, "deleted": "jason"}
    assert store.rows == []
    assert subject.delete("jason").code == "BROADCASTER_NOT_FOUND"


def test_attach_headshot_and_validate_social() -> None:
    store = Store([record()])
    subject = service(store, now=1200)
    attached = subject.attach_headshot(
        "jason",
        "data/Personnel/Headshots/jason.webp",
    )
    assert attached.ok
    assert attached.data["path"] == "/personnel-headshots/jason.webp"
    assert store.rows[0]["updated_at"] == 1200

    missing = subject.attach_headshot("missing", "/personnel-headshots/x.png")
    assert missing.code == "PERSONNEL_NOT_FOUND"

    checked = subject.validate_social("instagram", "@csrn")
    assert checked.data == {
        "normalized": "https://instagram.com/csrn",
        "valid": True,
        "message": "",
    }
