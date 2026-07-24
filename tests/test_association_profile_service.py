from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from association_profile_service import AssociationProfileService


def profile(
    *,
    profile_id: str = "test-association-football",
    name: str = "Test Association Football",
) -> dict[str, Any]:
    return {
        "id": profile_id,
        "name": name,
        "association": "TAHSAA",
        "state": "MS",
        "source_type": "csv",
        "source_url": "https://association.example/schools.csv",
        "field_mapping": {
            "School": "official_name",
            "Broadcast": "broadcast_name",
        },
        "defaults": {"state": "MS"},
        "options": {"create_venues": True},
    }


def fixed_clock() -> datetime:
    return datetime(2026, 7, 24, 20, 15, tzinfo=timezone.utc)


def make_service(
    directory: Path,
    *,
    protected_ids: set[str] | None = None,
) -> AssociationProfileService:
    return AssociationProfileService(
        directory,
        protected_ids=protected_ids,
        clock=fixed_clock,
    )


def test_create_read_and_list_profile(tmp_path: Path) -> None:
    service = make_service(tmp_path)

    created = service.create(profile())
    read = service.read("test-association-football")
    listed = service.list_profiles()

    assert created.ok
    assert created.data["created"] is True
    assert created.data["profile"]["created_at"] == (
        "2026-07-24T20:15:00+00:00"
    )
    assert read.ok
    assert read.data["profile"]["association"] == "TAHSAA"
    assert listed.data["profiles"][0]["id"] == "test-association-football"
    assert listed.data["invalid_profiles"] == []


def test_create_derives_profile_id_from_name_when_missing(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    incoming = profile(profile_id="", name="Alabama Association Schools")

    result = service.create(incoming)

    assert result.ok
    assert result.data["profile"]["id"] == "alabama-association-schools"
    assert (tmp_path / "alabama-association-schools.json").exists()


def test_create_rejects_duplicate_and_invalid_profile(tmp_path: Path) -> None:
    service = make_service(tmp_path)
    assert service.create(profile()).ok

    duplicate = service.create(profile())
    invalid = profile(profile_id="../../unsafe")
    invalid_result = service.create(invalid)
    missing_mapping = profile(profile_id="missing-mapping")
    missing_mapping["field_mapping"] = {}

    assert duplicate.code == "PROFILE_ALREADY_EXISTS"
    assert invalid_result.code == "INVALID_PROFILE_ID"
    assert service.create(missing_mapping).code == "FIELD_MAPPING_REQUIRED"


def test_update_preserves_created_at_and_rejects_id_conflict(
    tmp_path: Path,
) -> None:
    service = make_service(tmp_path)
    created = service.create(profile())
    updated_profile = profile()
    updated_profile["name"] = "Updated Association Football"

    updated = service.update("test-association-football", updated_profile)
    conflicting = profile(profile_id="different-profile")
    conflict = service.update("test-association-football", conflicting)

    assert updated.ok
    assert updated.data["created"] is False
    assert updated.data["profile"]["created_at"] == created.data["profile"][
        "created_at"
    ]
    assert updated.data["profile"]["name"] == "Updated Association Football"
    assert conflict.code == "PROFILE_ID_CONFLICT"


def test_delete_removes_user_profile_and_preserves_protected_profile(
    tmp_path: Path,
) -> None:
    service = make_service(
        tmp_path,
        protected_ids={"protected-profile"},
    )
    user_profile = profile(profile_id="user-profile", name="User Profile")
    protected_profile = profile(
        profile_id="protected-profile",
        name="Protected Profile",
    )
    assert service.create(user_profile).ok
    assert service.create(protected_profile).ok

    deleted = service.delete("user-profile")
    protected = service.delete("protected-profile")

    assert deleted.data == {"deleted": True, "id": "user-profile"}
    assert service.read("user-profile").code == "PROFILE_NOT_FOUND"
    assert protected.code == "PROFILE_PROTECTED"
    assert service.read("protected-profile").data["profile"]["protected"] is True


def test_list_reports_invalid_profile_files_without_hiding_valid_profiles(
    tmp_path: Path,
) -> None:
    service = make_service(tmp_path)
    assert service.create(profile()).ok
    (tmp_path / "broken.json").write_text("{not-json", encoding="utf-8")

    result = service.list_profiles()

    assert [item["id"] for item in result.data["profiles"]] == [
        "test-association-football"
    ]
    assert result.data["invalid_profiles"] == [
        {"filename": "broken.json", "error": "PROFILE_JSON_INVALID"}
    ]


def test_read_rejects_filename_profile_id_mismatch(tmp_path: Path) -> None:
    data = profile(profile_id="inside-profile")
    (tmp_path / "outside-profile.json").write_text(
        json.dumps(data),
        encoding="utf-8",
    )
    service = make_service(tmp_path)

    result = service.read("outside-profile")

    assert result.code == "PROFILE_FILENAME_MISMATCH"
