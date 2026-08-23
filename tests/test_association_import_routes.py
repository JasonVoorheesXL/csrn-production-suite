from __future__ import annotations

from typing import Any

import pytest

import app as app_module
from association_import_service import AssociationImportResult


class StubAssociationImportService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.analyze_result = AssociationImportResult(
            "OK",
            {
                "profile": {"id": "mhsaa-football-5a-2025-27"},
                "found": 2,
                "new": 1,
                "existing": 1,
                "possible_duplicates": 0,
                "invalid": 0,
                "schools": [
                    {
                        "status": "new",
                        "candidate": {
                            "official_name": "South High School",
                            "broadcast_name": "South",
                            "classification": "5A",
                        },
                        "matches": [],
                        "school_id": "",
                    },
                    {
                        "status": "existing",
                        "candidate": {
                            "official_name": "North High School",
                            "broadcast_name": "North",
                            "classification": "5A",
                        },
                        "matches": [{"id": "north", "score": 5}],
                        "school_id": "north",
                    },
                ],
            },
        )
        self.apply_result = AssociationImportResult(
            "OK",
            {
                "profile": {"id": "mhsaa-football-5a-2025-27"},
                "imported": 1,
                "enriched_existing": 1,
                "skipped_existing": 2,
                "possible_duplicates": [],
                "invalid": [],
                "created_ids": ["MS5A-003"],
                "total_schools": 18,
            },
        )

    def analyze(
        self,
        profile: dict[str, Any],
        rows: list[dict[str, Any]],
    ) -> AssociationImportResult:
        self.calls.append(("analyze", (profile, rows)))
        return self.analyze_result

    def apply(
        self,
        profile: dict[str, Any],
        rows: list[dict[str, Any]],
        *,
        create_venues: bool | None = None,
        allow_possible_duplicates: bool = False,
    ) -> AssociationImportResult:
        self.calls.append(
            (
                "apply",
                (
                    profile,
                    rows,
                    create_venues,
                    allow_possible_duplicates,
                ),
            )
        )
        return self.apply_result


@pytest.fixture
def association_client(monkeypatch: pytest.MonkeyPatch):
    service = StubAssociationImportService()
    profile = {
        "id": "mhsaa-football-5a-2025-27",
        "name": "MHSAA 2025-27 Football 5A",
        "association": "MHSAA",
        "state": "MS",
        "source_type": "manifest",
        "source_url": "https://association.example/5a",
        "field_mapping": {
            "official_name": "official_name",
            "broadcast_name": "broadcast_name",
        },
        "defaults": {"classification": "5A", "state": "MS"},
        "options": {"create_venues": True},
    }
    manifest = {
        "classification": "5A",
        "source": {"provider": "MHSAA", "checked_at": "2026-07-11"},
        "schools": [
            {
                "official_name": "South High School",
                "broadcast_name": "South",
            }
        ],
    }

    def fake_load_json(path, default):
        if path == app_module.MHSAA_5A_PROFILE_FILE:
            return profile
        if path == app_module.MHSAA_5A_FILE:
            return manifest
        return default

    monkeypatch.setattr(
        app_module,
        "ASSOCIATION_IMPORT_SERVICE",
        service,
        raising=False,
    )
    monkeypatch.setattr(app_module, "load_json", fake_load_json)
    monkeypatch.setattr(app_module, "pin_is_configured", lambda: True)
    monkeypatch.setitem(app_module.app.config, "TESTING", True)
    monkeypatch.setitem(
        app_module.app.config,
        "SECRET_KEY",
        "association-route-test",
    )

    with app_module.app.test_client() as client:
        with client.session_transaction() as active_session:
            active_session["authenticated"] = True
        yield client, service, profile, manifest


def test_mhsaa_analyze_route_preserves_legacy_contract(
    association_client,
) -> None:
    client, service, profile, manifest = association_client

    response = client.get("/api/imports/mhsaa/5A/analyze")

    assert response.status_code == 200
    assert response.get_json() == {
        "classification": "5A",
        "source": manifest["source"],
        "found": 2,
        "new": 1,
        "existing": 1,
        "possible_duplicates": 0,
        "schools": [
            {
                "official_name": "South High School",
                "broadcast_name": "South",
                "classification": "5A",
                "status": "new",
                "matches": [],
            },
            {
                "official_name": "North High School",
                "broadcast_name": "North",
                "classification": "5A",
                "status": "existing",
                "matches": [{"id": "north", "score": 5}],
            },
        ],
    }
    assert service.calls == [("analyze", (profile, manifest["schools"]))]


def test_mhsaa_import_route_preserves_legacy_contract(
    association_client,
) -> None:
    client, service, profile, manifest = association_client

    response = client.post(
        "/api/imports/mhsaa/5A",
        json={"create_venues": False},
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "imported": 1,
        "skipped_existing": 3,
        "created_ids": ["MS5A-003"],
        "total_schools": 18,
    }
    assert service.calls == [
        (
            "apply",
            (profile, manifest["schools"], False, True),
        )
    ]


def test_mhsaa_routes_map_profile_errors_to_bad_request(
    association_client,
) -> None:
    client, service, _profile, _manifest = association_client
    service.analyze_result = AssociationImportResult("FIELD_MAPPING_REQUIRED")
    service.apply_result = AssociationImportResult("FIELD_MAPPING_REQUIRED")

    analyzed = client.get("/api/imports/mhsaa/5A/analyze")
    imported = client.post("/api/imports/mhsaa/5A", json={})

    assert analyzed.status_code == 400
    assert analyzed.get_json() == {"error": "FIELD_MAPPING_REQUIRED"}
    assert imported.status_code == 400
    assert imported.get_json() == {"error": "FIELD_MAPPING_REQUIRED"}


