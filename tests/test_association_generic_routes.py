from __future__ import annotations

import io
from typing import Any

import pytest

import app as app_module
from association_profile_service import AssociationProfileResult
from association_workflow_service import AssociationWorkflowResult


class StubAssociationProfileService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.saved_profile = {
            "id": "test-association",
            "name": "Test Association",
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
            "protected": False,
        }

    def list_profiles(self) -> AssociationProfileResult:
        self.calls.append(("list", None))
        return AssociationProfileResult(
            "OK",
            {"profiles": [self.saved_profile], "invalid_profiles": []},
        )

    def read(self, profile_id: str) -> AssociationProfileResult:
        self.calls.append(("read", profile_id))
        if profile_id == "missing":
            return AssociationProfileResult("PROFILE_NOT_FOUND")
        return AssociationProfileResult(
            "OK",
            {"profile": {**self.saved_profile, "id": profile_id}},
        )

    def create(self, incoming: dict[str, Any]) -> AssociationProfileResult:
        self.calls.append(("create", incoming))
        if incoming.get("mode") == "exists":
            return AssociationProfileResult("PROFILE_ALREADY_EXISTS")
        if incoming.get("mode") == "invalid":
            return AssociationProfileResult("FIELD_MAPPING_REQUIRED")
        return AssociationProfileResult(
            "OK",
            {"profile": {**self.saved_profile, **incoming}, "created": True},
        )

    def update(
        self,
        profile_id: str,
        incoming: dict[str, Any],
    ) -> AssociationProfileResult:
        self.calls.append(("update", (profile_id, incoming)))
        if profile_id == "missing":
            return AssociationProfileResult("PROFILE_NOT_FOUND")
        if incoming.get("mode") == "conflict":
            return AssociationProfileResult("PROFILE_ID_CONFLICT")
        return AssociationProfileResult(
            "OK",
            {
                "profile": {
                    **self.saved_profile,
                    **incoming,
                    "id": profile_id,
                },
                "created": False,
            },
        )

    def delete(self, profile_id: str) -> AssociationProfileResult:
        self.calls.append(("delete", profile_id))
        if profile_id == "missing":
            return AssociationProfileResult("PROFILE_NOT_FOUND")
        if profile_id == "protected":
            return AssociationProfileResult("PROFILE_PROTECTED")
        return AssociationProfileResult(
            "OK",
            {"deleted": True, "id": profile_id},
        )


class StubAssociationWorkflowService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.preview_result = AssociationWorkflowResult(
            "OK",
            {
                "profile": {"id": "test-association"},
                "source": {"sha256": "abc123"},
                "warnings": {"missing_source_fields": []},
                "row_count": 2,
                "columns": ["Broadcast", "School"],
                "sample_rows": [{"School": "North High School"}],
                "analysis": {"found": 2, "new": 2, "schools": []},
            },
        )
        self.apply_result = AssociationWorkflowResult(
            "OK",
            {
                "profile": {"id": "test-association"},
                "source": {"sha256": "abc123"},
                "warnings": {"missing_source_fields": []},
                "row_count": 2,
                "result": {"imported": 2, "created_ids": ["MS-001", "MS-002"]},
            },
        )

    def preview(
        self,
        profile: dict[str, Any],
        *,
        supplied_content: bytes | str | None = None,
        supplied_content_type: str = "",
    ) -> AssociationWorkflowResult:
        self.calls.append(
            (
                "preview",
                (profile, supplied_content, supplied_content_type),
            )
        )
        return self.preview_result

    def apply(
        self,
        profile: dict[str, Any],
        *,
        approved: bool,
        expected_sha256: str,
        supplied_content: bytes | str | None = None,
        supplied_content_type: str = "",
        create_venues: bool | None = None,
        allow_possible_duplicates: bool = False,
    ) -> AssociationWorkflowResult:
        self.calls.append(
            (
                "apply",
                (
                    profile,
                    approved,
                    expected_sha256,
                    supplied_content,
                    supplied_content_type,
                    create_venues,
                    allow_possible_duplicates,
                ),
            )
        )
        return self.apply_result


@pytest.fixture
def association_generic_client(monkeypatch: pytest.MonkeyPatch):
    profile_service = StubAssociationProfileService()
    workflow_service = StubAssociationWorkflowService()
    monkeypatch.setattr(
        app_module,
        "ASSOCIATION_PROFILE_SERVICE",
        profile_service,
        raising=False,
    )
    monkeypatch.setattr(
        app_module,
        "ASSOCIATION_WORKFLOW_SERVICE",
        workflow_service,
        raising=False,
    )
    monkeypatch.setattr(app_module, "pin_is_configured", lambda: True)
    monkeypatch.setitem(app_module.app.config, "TESTING", True)
    monkeypatch.setitem(
        app_module.app.config,
        "SECRET_KEY",
        "association-generic-route-test",
    )

    with app_module.app.test_client() as client:
        with client.session_transaction() as active_session:
            active_session["authenticated"] = True
        yield client, profile_service, workflow_service


def test_profile_list_and_read_routes(association_generic_client) -> None:
    client, profile_service, _workflow_service = association_generic_client

    listed = client.get("/api/imports/associations/profiles")
    read = client.get("/api/imports/associations/profiles/test-association")
    missing = client.get("/api/imports/associations/profiles/missing")

    assert listed.status_code == 200
    assert listed.get_json()["profiles"][0]["id"] == "test-association"
    assert read.status_code == 200
    assert read.get_json()["id"] == "test-association"
    assert missing.status_code == 404
    assert missing.get_json() == {"error": "PROFILE_NOT_FOUND"}
    assert ("list", None) in profile_service.calls


def test_profile_create_and_update_routes(association_generic_client) -> None:
    client, profile_service, _workflow_service = association_generic_client

    created = client.post(
        "/api/imports/associations/profiles",
        json={"id": "new-profile", "name": "New Profile"},
    )
    exists = client.post(
        "/api/imports/associations/profiles",
        json={"mode": "exists"},
    )
    updated = client.put(
        "/api/imports/associations/profiles/test-association",
        json={"name": "Updated Profile"},
    )
    conflict = client.put(
        "/api/imports/associations/profiles/test-association",
        json={"mode": "conflict"},
    )

    assert created.status_code == 201
    assert created.get_json()["id"] == "new-profile"
    assert exists.status_code == 409
    assert updated.status_code == 200
    assert updated.get_json()["name"] == "Updated Profile"
    assert conflict.status_code == 409
    assert any(call[0] == "create" for call in profile_service.calls)


def test_profile_delete_route_maps_protected_and_missing(
    association_generic_client,
) -> None:
    client, _profile_service, _workflow_service = association_generic_client

    deleted = client.delete("/api/imports/associations/profiles/user-profile")
    protected = client.delete("/api/imports/associations/profiles/protected")
    missing = client.delete("/api/imports/associations/profiles/missing")

    assert deleted.status_code == 200
    assert deleted.get_json() == {"deleted": True, "id": "user-profile"}
    assert protected.status_code == 409
    assert protected.get_json() == {"error": "PROFILE_PROTECTED"}
    assert missing.status_code == 404


def test_preview_route_uses_saved_profile_and_supplied_content(
    association_generic_client,
) -> None:
    client, profile_service, workflow_service = association_generic_client

    response = client.post(
        "/api/imports/associations/preview",
        json={
            "profile_id": "test-association",
            "source_content": "School,Broadcast\nNorth High School,North",
            "source_content_type": "text/csv",
        },
    )

    assert response.status_code == 200
    assert response.get_json()["source"]["sha256"] == "abc123"
    assert ("read", "test-association") in profile_service.calls
    assert workflow_service.calls[0][0] == "preview"
    assert workflow_service.calls[0][1][1] == (
        "School,Broadcast\nNorth High School,North"
    )


def test_preview_route_accepts_inline_unsaved_profile(
    association_generic_client,
) -> None:
    client, profile_service, workflow_service = association_generic_client
    inline = {"id": "inline-profile", "name": "Inline"}

    response = client.post(
        "/api/imports/associations/preview",
        json={"profile": inline},
    )

    assert response.status_code == 200
    assert workflow_service.calls[0][1][0] == inline
    assert not any(call[0] == "read" for call in profile_service.calls)


def test_import_route_forwards_approval_hash_and_import_options(
    association_generic_client,
) -> None:
    client, _profile_service, workflow_service = association_generic_client

    response = client.post(
        "/api/imports/associations/import",
        json={
            "profile_id": "test-association",
            "approved": True,
            "expected_sha256": "abc123",
            "create_venues": False,
            "allow_possible_duplicates": True,
        },
    )

    assert response.status_code == 200
    assert response.get_json()["result"]["imported"] == 2
    call = workflow_service.calls[0]
    assert call[0] == "apply"
    assert call[1][1:] == (
        True,
        "abc123",
        None,
        "",
        False,
        True,
    )


def test_preview_route_accepts_multipart_source_upload(
    association_generic_client,
) -> None:
    client, _profile_service, workflow_service = association_generic_client

    response = client.post(
        "/api/imports/associations/preview",
        data={
            "profile_id": "test-association",
            "source": (
                io.BytesIO(b"School,Broadcast\nNorth High School,North"),
                "schools.csv",
                "text/csv",
            ),
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    call = workflow_service.calls[0]
    assert call[0] == "preview"
    assert call[1][1].startswith(b"School,Broadcast")
    assert call[1][2] == "text/csv"


def test_generic_routes_map_resolution_and_workflow_errors(
    association_generic_client,
) -> None:
    client, _profile_service, workflow_service = association_generic_client

    no_profile = client.post("/api/imports/associations/preview", json={})
    missing = client.post(
        "/api/imports/associations/preview",
        json={"profile_id": "missing"},
    )
    workflow_service.preview_result = AssociationWorkflowResult(
        "SOURCE_FETCH_FAILED"
    )
    fetch_failed = client.post(
        "/api/imports/associations/preview",
        json={"profile_id": "test-association"},
    )
    workflow_service.apply_result = AssociationWorkflowResult(
        "SOURCE_CHANGED_SINCE_PREVIEW"
    )
    changed = client.post(
        "/api/imports/associations/import",
        json={
            "profile_id": "test-association",
            "approved": True,
            "expected_sha256": "abc123",
        },
    )

    assert no_profile.status_code == 400
    assert no_profile.get_json() == {"error": "PROFILE_ID_REQUIRED"}
    assert missing.status_code == 404
    assert fetch_failed.status_code == 502
    assert changed.status_code == 409


