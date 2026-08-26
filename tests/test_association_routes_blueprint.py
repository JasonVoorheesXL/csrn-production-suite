from __future__ import annotations

import io
import json
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable

import pytest
from flask import Flask, jsonify, request

from routes.association_routes import (
    AssociationRoutesDependencies,
    association_error_status,
    create_association_blueprint,
)


@dataclass(frozen=True)
class StubResult:
    code: str
    data: dict[str, Any]

    @property
    def ok(self) -> bool:
        return self.code == "OK"


class StubProfileService:
    def __init__(self) -> None:
        self.profile = {"profile_id": "mhsaa", "name": "MHSAA"}
        self.list_result = StubResult("OK", {"profiles": [self.profile]})
        self.read_result = StubResult("OK", {"profile": self.profile})
        self.create_result = StubResult("OK", {"profile": self.profile})
        self.update_result = StubResult("OK", {"profile": self.profile})
        self.delete_result = StubResult("OK", {"deleted": True})
        self.calls: list[tuple[str, Any]] = []

    def list_profiles(self) -> StubResult:
        self.calls.append(("list", None))
        return self.list_result

    def read(self, profile_id: str) -> StubResult:
        self.calls.append(("read", profile_id))
        return self.read_result

    def create(self, payload: dict[str, Any]) -> StubResult:
        self.calls.append(("create", payload))
        return self.create_result

    def update(self, profile_id: str, payload: dict[str, Any]) -> StubResult:
        self.calls.append(("update", (profile_id, payload)))
        return self.update_result

    def delete(self, profile_id: str) -> StubResult:
        self.calls.append(("delete", profile_id))
        return self.delete_result


class StubWorkflowService:
    def __init__(self) -> None:
        self.preview_result = StubResult("OK", {"preview": True})
        self.apply_result = StubResult("OK", {"imported": 2})
        self.preview_calls: list[tuple[Any, dict[str, Any]]] = []
        self.apply_calls: list[tuple[Any, dict[str, Any]]] = []

    def preview(self, profile: Any, **kwargs: Any) -> StubResult:
        self.preview_calls.append((profile, kwargs))
        return self.preview_result

    def apply(self, profile: Any, **kwargs: Any) -> StubResult:
        self.apply_calls.append((profile, kwargs))
        return self.apply_result


class StubImportService:
    def __init__(self) -> None:
        self.analyze_result = StubResult(
            "OK",
            {
                "found": 1,
                "new": 1,
                "existing": 0,
                "possible_duplicates": 0,
                "schools": [
                    {
                        "candidate": {"official_name": "Caledonia"},
                        "status": "new",
                        "matches": [],
                    }
                ],
            },
        )
        self.apply_result = StubResult(
            "OK",
            {
                "imported": 1,
                "enriched_existing": 1,
                "skipped_existing": 2,
                "created_ids": ["caledonia"],
                "total_schools": 4,
            },
        )
        self.analyze_calls: list[tuple[Any, Any]] = []
        self.apply_calls: list[tuple[Any, Any, dict[str, Any]]] = []

    def analyze(self, profile: Any, schools: Any) -> StubResult:
        self.analyze_calls.append((profile, schools))
        return self.analyze_result

    def apply(self, profile: Any, schools: Any, **kwargs: Any) -> StubResult:
        self.apply_calls.append((profile, schools, kwargs))
        return self.apply_result


class StubSupplementService:
    def __init__(self) -> None:
        self.analyze_branding_result = StubResult("OK", {"branding": "analyzed"})
        self.apply_branding_result = StubResult("OK", {"branding": "applied"})
        self.analyze_enrichment_result = StubResult("OK", {"enrichment": "analyzed"})
        self.apply_enrichment_result = StubResult("OK", {"enrichment": "applied"})
        self.calls: list[tuple[str, Any, dict[str, Any]]] = []

    def analyze_branding(self, schools: Any, **kwargs: Any) -> StubResult:
        self.calls.append(("analyze_branding", schools, kwargs))
        return self.analyze_branding_result

    def apply_branding(self, schools: Any, **kwargs: Any) -> StubResult:
        self.calls.append(("apply_branding", schools, kwargs))
        return self.apply_branding_result

    def analyze_enrichment(self, schools: Any, **kwargs: Any) -> StubResult:
        self.calls.append(("analyze_enrichment", schools, kwargs))
        return self.analyze_enrichment_result

    def apply_enrichment(self, schools: Any, **kwargs: Any) -> StubResult:
        self.calls.append(("apply_enrichment", schools, kwargs))
        return self.apply_enrichment_result


@pytest.fixture
def association_client():
    profile = StubProfileService()
    workflow = StubWorkflowService()
    importer = StubImportService()
    supplement = StubSupplementService()
    manifests = {
        "profile": {"profile_id": "legacy-profile"},
        "main": {
            "classification": "5A",
            "source": {"name": "MHSAA"},
            "schools": [{"official_name": "Caledonia"}],
        },
        "branding": {
            "source": {"name": "Branding"},
            "schools": [{"official_name": "Caledonia"}],
        },
        "enrichment": {
            "classification": "5A",
            "source": {"name": "Enrichment"},
            "schools": [{"official_name": "Caledonia"}],
        },
    }

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
        create_association_blueprint(
            AssociationRoutesDependencies(
                require_auth=require_auth,
                get_profile_service=lambda: profile,
                get_workflow_service=lambda: workflow,
                get_import_service=lambda: importer,
                get_supplement_service=lambda: supplement,
                # The dragonfly-import routes (/api/imports/dragonfly/*)
                # were added to association_routes.py after this fixture
                # was last updated; nothing in this file exercises them yet,
                # so these just need to satisfy the dataclass constructor.
                get_dragonfly_service=lambda: None,
                get_dragonfly_sync_service=lambda: None,
                get_school_service=lambda: None,
                load_mhsaa_profile=lambda: manifests["profile"],
                load_mhsaa_manifest=lambda: manifests["main"],
                load_mhsaa_branding_manifest=lambda: manifests["branding"],
                load_mhsaa_enrichment_manifest=lambda: manifests["enrichment"],
            )
        )
    )
    with app.test_client() as client:
        yield client, app, profile, workflow, importer, supplement, manifests


def auth_headers() -> dict[str, str]:
    return {"X-Test-Auth": "yes"}


def test_association_blueprint_registers_preserved_urls(association_client) -> None:
    _, app, *_ = association_client
    paths = {
        rule.rule
        for rule in app.url_map.iter_rules()
        if rule.rule.startswith("/api/imports/")
    }
    assert paths == {
        "/api/imports/associations/profiles",
        "/api/imports/associations/profiles/<profile_id>",
        "/api/imports/associations/preview",
        "/api/imports/associations/import",
        # Dragonfly-import routes, added after this manifest was last
        # updated (see get_dragonfly_service/get_dragonfly_sync_service/
        # get_school_service on AssociationRoutesDependencies).
        "/api/imports/dragonfly/preview",
        "/api/imports/dragonfly/sync-preview",
        "/api/imports/dragonfly/replace-roster",
        "/api/imports/dragonfly/school-info-preview",
        "/api/imports/dragonfly/school-info-apply",
        "/api/imports/mhsaa/5A/analyze",
        "/api/imports/mhsaa/5A",
        "/api/imports/mhsaa/5A/branding/analyze",
        "/api/imports/mhsaa/5A/branding",
        "/api/imports/mhsaa/5A/enrichment/analyze",
        "/api/imports/mhsaa/5A/enrichment",
    }


def test_association_routes_require_authentication(association_client) -> None:
    client, _, profile, *_ = association_client
    response = client.get("/api/imports/associations/profiles")
    assert response.status_code == 401
    assert response.get_json() == {"error": "AUTH_REQUIRED"}
    assert profile.calls == []


def test_profile_crud_routes_delegate_and_preserve_payloads(association_client) -> None:
    client, _, profile, *_ = association_client
    assert client.get(
        "/api/imports/associations/profiles",
        headers=auth_headers(),
    ).get_json()["profiles"][0]["profile_id"] == "mhsaa"
    assert client.get(
        "/api/imports/associations/profiles/mhsaa",
        headers=auth_headers(),
    ).get_json()["profile_id"] == "mhsaa"
    created = client.post(
        "/api/imports/associations/profiles",
        json={"name": "MHSAA"},
        headers=auth_headers(),
    )
    assert created.status_code == 201
    updated = client.put(
        "/api/imports/associations/profiles/mhsaa",
        json={"name": "Updated"},
        headers=auth_headers(),
    )
    assert updated.status_code == 200
    deleted = client.delete(
        "/api/imports/associations/profiles/mhsaa",
        headers=auth_headers(),
    )
    assert deleted.get_json() == {"deleted": True}
    assert ("create", {"name": "MHSAA"}) in profile.calls
    assert ("update", ("mhsaa", {"name": "Updated"})) in profile.calls


def test_profile_routes_preserve_error_status_mapping(association_client) -> None:
    client, _, profile, *_ = association_client
    profile.read_result = StubResult("PROFILE_NOT_FOUND", {})
    assert client.get(
        "/api/imports/associations/profiles/missing",
        headers=auth_headers(),
    ).status_code == 404

    profile.create_result = StubResult("PROFILE_ALREADY_EXISTS", {})
    assert client.post(
        "/api/imports/associations/profiles",
        json={},
        headers=auth_headers(),
    ).status_code == 409

    profile.update_result = StubResult("PROFILE_SAVE_FAILED", {})
    assert client.put(
        "/api/imports/associations/profiles/mhsaa",
        json={},
        headers=auth_headers(),
    ).status_code == 500

    assert association_error_status("SOURCE_FETCH_FAILED") == 502
    assert association_error_status("INVALID_PROFILE_PAYLOAD") == 400


def test_preview_accepts_inline_json_profile(association_client) -> None:
    client, _, _, workflow, *_ = association_client
    inline = {"profile_id": "inline"}
    response = client.post(
        "/api/imports/associations/preview",
        json={
            "profile": inline,
            "source_content": "school,name",
            "source_content_type": "text/csv",
        },
        headers=auth_headers(),
    )
    assert response.status_code == 200
    assert response.get_json() == {"preview": True}
    profile, kwargs = workflow.preview_calls[-1]
    assert profile == inline
    assert kwargs["supplied_content"] == "school,name"
    assert kwargs["supplied_content_type"] == "text/csv"


def test_preview_resolves_saved_profile(association_client) -> None:
    client, _, profile, workflow, *_ = association_client
    response = client.post(
        "/api/imports/associations/preview",
        json={"profile_id": "mhsaa"},
        headers=auth_headers(),
    )
    assert response.status_code == 200
    assert ("read", "mhsaa") in profile.calls
    assert workflow.preview_calls[-1][0]["profile_id"] == "mhsaa"


def test_preview_rejects_invalid_multipart_profile_json(association_client) -> None:
    client, *_ = association_client
    response = client.post(
        "/api/imports/associations/preview",
        data={"profile": "{bad json"},
        headers=auth_headers(),
    )
    assert response.status_code == 400
    assert response.get_json() == {"error": "INVALID_PROFILE_JSON"}


def test_preview_rejects_invalid_request_and_source_payloads(association_client) -> None:
    client, *_ = association_client
    invalid_request = client.post(
        "/api/imports/associations/preview",
        json=["not", "an", "object"],
        headers=auth_headers(),
    )
    assert invalid_request.status_code == 400
    assert invalid_request.get_json() == {"error": "INVALID_REQUEST_PAYLOAD"}

    invalid_source = client.post(
        "/api/imports/associations/preview",
        json={"profile": {}, "source_content": {"bad": True}},
        headers=auth_headers(),
    )
    assert invalid_source.status_code == 400
    assert invalid_source.get_json() == {"error": "INVALID_SOURCE_CONTENT"}


def test_preview_preserves_workflow_error_mapping(association_client) -> None:
    client, _, _, workflow, *_ = association_client
    workflow.preview_result = StubResult("SOURCE_FETCH_FAILED", {})
    response = client.post(
        "/api/imports/associations/preview",
        json={"profile": {}},
        headers=auth_headers(),
    )
    assert response.status_code == 502
    assert response.get_json() == {"error": "SOURCE_FETCH_FAILED"}


def test_apply_maps_json_options_to_workflow(association_client) -> None:
    client, _, _, workflow, *_ = association_client
    response = client.post(
        "/api/imports/associations/import",
        json={
            "profile": {"profile_id": "inline"},
            "approved": "yes",
            "expected_sha256": "abc123",
            "create_venues": "false",
            "allow_possible_duplicates": "1",
        },
        headers=auth_headers(),
    )
    assert response.status_code == 200
    _, kwargs = workflow.apply_calls[-1]
    assert kwargs["approved"] is True
    assert kwargs["expected_sha256"] == "abc123"
    assert kwargs["create_venues"] is False
    assert kwargs["allow_possible_duplicates"] is True


def test_apply_accepts_multipart_source_upload(association_client) -> None:
    client, _, _, workflow, *_ = association_client
    response = client.post(
        "/api/imports/associations/import",
        data={
            "profile": json.dumps({"profile_id": "inline"}),
            "approved": "true",
            "source": (io.BytesIO(b"school,name"), "schools.csv"),
        },
        headers=auth_headers(),
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    _, kwargs = workflow.apply_calls[-1]
    assert kwargs["supplied_content"] == b"school,name"
    assert kwargs["supplied_content_type"] == "text/csv"


def test_apply_preserves_approval_error_mapping(association_client) -> None:
    client, _, _, workflow, *_ = association_client
    workflow.apply_result = StubResult("IMPORT_APPROVAL_REQUIRED", {})
    response = client.post(
        "/api/imports/associations/import",
        json={"profile": {}},
        headers=auth_headers(),
    )
    assert response.status_code == 409
    assert response.get_json() == {"error": "IMPORT_APPROVAL_REQUIRED"}


def test_legacy_mhsaa_analyze_preserves_response_shape(association_client) -> None:
    client, _, _, _, importer, _, manifests = association_client
    response = client.get(
        "/api/imports/mhsaa/5A/analyze",
        headers=auth_headers(),
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["classification"] == "5A"
    assert payload["source"] == {"name": "MHSAA"}
    assert payload["schools"][0] == {
        "official_name": "Caledonia",
        "status": "new",
        "matches": [],
    }
    assert importer.analyze_calls[-1] == (
        manifests["profile"],
        manifests["main"]["schools"],
    )


def test_legacy_mhsaa_import_preserves_options_and_counts(association_client) -> None:
    client, _, _, _, importer, *_ = association_client
    response = client.post(
        "/api/imports/mhsaa/5A",
        json={"create_venues": False},
        headers=auth_headers(),
    )
    assert response.status_code == 200
    assert response.get_json() == {
        "imported": 1,
        "skipped_existing": 3,
        "created_ids": ["caledonia"],
        "total_schools": 4,
    }
    kwargs = importer.apply_calls[-1][2]
    assert kwargs == {
        "create_venues": False,
        "allow_possible_duplicates": True,
    }


def test_branding_routes_delegate_to_supplement_service(association_client) -> None:
    client, _, _, _, _, supplement, _ = association_client
    analyzed = client.get(
        "/api/imports/mhsaa/5A/branding/analyze",
        headers=auth_headers(),
    )
    applied = client.post(
        "/api/imports/mhsaa/5A/branding",
        headers=auth_headers(),
    )
    assert analyzed.get_json() == {"branding": "analyzed"}
    assert applied.get_json() == {"branding": "applied"}
    assert [call[0] for call in supplement.calls[-2:]] == [
        "analyze_branding",
        "apply_branding",
    ]


def test_enrichment_routes_delegate_with_classification_and_sport(association_client) -> None:
    client, _, _, _, _, supplement, _ = association_client
    analyzed = client.get(
        "/api/imports/mhsaa/5A/enrichment/analyze",
        headers=auth_headers(),
    )
    applied = client.post(
        "/api/imports/mhsaa/5A/enrichment",
        headers=auth_headers(),
    )
    assert analyzed.get_json() == {"enrichment": "analyzed"}
    assert applied.get_json() == {"enrichment": "applied"}
    assert supplement.calls[-2][2]["classification"] == "5A"
    assert supplement.calls[-1][2]["venue_sport"] == "Football"


