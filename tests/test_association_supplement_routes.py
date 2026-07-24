from __future__ import annotations

from typing import Any

import pytest

import app as app_module
from association_supplement_service import AssociationSupplementResult


class StubAssociationSupplementService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.branding_analysis = AssociationSupplementResult(
            "OK",
            {
                "found": 3,
                "ready": 1,
                "preserved": 1,
                "school_missing": 1,
                "schools": [
                    {
                        "official_name": "Ready High School",
                        "status": "ready",
                        "school_id": "ready",
                    },
                    {
                        "official_name": "Approved High School",
                        "status": "preserved",
                        "school_id": "approved",
                    },
                    {
                        "official_name": "Missing High School",
                        "status": "school_missing",
                        "school_id": "",
                    },
                ],
                "source": {
                    "provider": "MHSAA branding seed",
                    "checked_at": "2026-07-11",
                },
            },
        )
        self.branding_apply = AssociationSupplementResult(
            "OK",
            {
                "updated": 1,
                "preserved": 1,
                "missing_schools": ["Missing High School"],
            },
        )
        self.enrichment_analysis = AssociationSupplementResult(
            "OK",
            {
                "classification": "5A",
                "found": 2,
                "ready": 1,
                "school_missing": 1,
                "source": {
                    "provider": "MHSAA School Directory",
                    "checked_at": "2026-07-11",
                },
                "schools": [
                    {
                        "official_name": "Ready High School",
                        "status": "ready",
                        "missing_source_fields": ["phone"],
                    },
                    {
                        "official_name": "Missing High School",
                        "status": "school_missing",
                        "missing_source_fields": [],
                    },
                ],
            },
        )
        self.enrichment_apply = AssociationSupplementResult(
            "OK",
            {
                "updated": 1,
                "missing_schools": ["Missing High School"],
                "missing_mascot": 0,
                "missing_address": 0,
                "missing_website": 1,
                "logo_pending_approval": 1,
                "venue_verification_needed": 1,
            },
        )

    def analyze_branding(
        self,
        rows: list[dict[str, Any]],
        *,
        source: dict[str, Any] | None = None,
    ) -> AssociationSupplementResult:
        self.calls.append(("analyze_branding", (rows, source)))
        return self.branding_analysis

    def apply_branding(
        self,
        rows: list[dict[str, Any]],
        *,
        source: dict[str, Any] | None = None,
    ) -> AssociationSupplementResult:
        self.calls.append(("apply_branding", (rows, source)))
        return self.branding_apply

    def analyze_enrichment(
        self,
        rows: list[dict[str, Any]],
        *,
        source: dict[str, Any] | None = None,
        classification: str = "",
    ) -> AssociationSupplementResult:
        self.calls.append(
            ("analyze_enrichment", (rows, source, classification))
        )
        return self.enrichment_analysis

    def apply_enrichment(
        self,
        rows: list[dict[str, Any]],
        *,
        source: dict[str, Any] | None = None,
        venue_sport: str = "Football",
    ) -> AssociationSupplementResult:
        self.calls.append(("apply_enrichment", (rows, source, venue_sport)))
        return self.enrichment_apply


@pytest.fixture
def supplement_client(monkeypatch: pytest.MonkeyPatch):
    service = StubAssociationSupplementService()
    branding_manifest = {
        "classification": "5A",
        "source": {
            "provider": "MHSAA branding seed",
            "checked_at": "2026-07-11",
        },
        "schools": [
            {
                "official_name": "Ready High School",
                "primary_color": "#AA0000",
            }
        ],
    }
    enrichment_manifest = {
        "classification": "5A",
        "source": {
            "provider": "MHSAA School Directory",
            "checked_at": "2026-07-11",
        },
        "schools": [
            {
                "official_name": "Ready High School",
                "mascot": "Tigers",
            }
        ],
    }

    def fake_load_json(path, default):
        if path == app_module.MHSAA_5A_BRANDING_FILE:
            return branding_manifest
        if path == app_module.MHSAA_5A_ENRICHMENT_FILE:
            return enrichment_manifest
        return default

    monkeypatch.setattr(
        app_module,
        "ASSOCIATION_SUPPLEMENT_SERVICE",
        service,
        raising=False,
    )
    monkeypatch.setattr(app_module, "load_json", fake_load_json)
    monkeypatch.setattr(app_module, "pin_is_configured", lambda: True)
    monkeypatch.setitem(app_module.app.config, "TESTING", True)
    monkeypatch.setitem(
        app_module.app.config,
        "SECRET_KEY",
        "association-supplement-route-test",
    )

    with app_module.app.test_client() as client:
        with client.session_transaction() as active_session:
            active_session["authenticated"] = True
        yield client, service, branding_manifest, enrichment_manifest


def test_branding_analyze_route_preserves_contract(supplement_client) -> None:
    client, service, branding_manifest, _enrichment_manifest = supplement_client

    response = client.get("/api/imports/mhsaa/5A/branding/analyze")

    assert response.status_code == 200
    assert response.get_json() == service.branding_analysis.data
    assert service.calls == [
        (
            "analyze_branding",
            (branding_manifest["schools"], branding_manifest["source"]),
        )
    ]


def test_branding_apply_route_preserves_contract(supplement_client) -> None:
    client, service, branding_manifest, _enrichment_manifest = supplement_client

    response = client.post("/api/imports/mhsaa/5A/branding", json={})

    assert response.status_code == 200
    assert response.get_json() == service.branding_apply.data
    assert service.calls == [
        (
            "apply_branding",
            (branding_manifest["schools"], branding_manifest["source"]),
        )
    ]


def test_enrichment_analyze_route_preserves_contract(supplement_client) -> None:
    client, service, _branding_manifest, enrichment_manifest = supplement_client

    response = client.get("/api/imports/mhsaa/5A/enrichment/analyze")

    assert response.status_code == 200
    assert response.get_json() == service.enrichment_analysis.data
    assert service.calls == [
        (
            "analyze_enrichment",
            (
                enrichment_manifest["schools"],
                enrichment_manifest["source"],
                "5A",
            ),
        )
    ]


def test_enrichment_apply_route_preserves_contract(supplement_client) -> None:
    client, service, _branding_manifest, enrichment_manifest = supplement_client

    response = client.post("/api/imports/mhsaa/5A/enrichment", json={})

    assert response.status_code == 200
    assert response.get_json() == service.enrichment_apply.data
    assert service.calls == [
        (
            "apply_enrichment",
            (
                enrichment_manifest["schools"],
                enrichment_manifest["source"],
                "Football",
            ),
        )
    ]


def test_supplement_routes_map_service_errors_to_bad_request(
    supplement_client,
) -> None:
    client, service, _branding_manifest, _enrichment_manifest = supplement_client
    error = AssociationSupplementResult("INVALID_SUPPLEMENT_SOURCE")
    service.branding_analysis = error
    service.branding_apply = error
    service.enrichment_analysis = error
    service.enrichment_apply = error

    responses = [
        client.get("/api/imports/mhsaa/5A/branding/analyze"),
        client.post("/api/imports/mhsaa/5A/branding", json={}),
        client.get("/api/imports/mhsaa/5A/enrichment/analyze"),
        client.post("/api/imports/mhsaa/5A/enrichment", json={}),
    ]

    for response in responses:
        assert response.status_code == 400
        assert response.get_json() == {
            "error": "INVALID_SUPPLEMENT_SOURCE"
        }
