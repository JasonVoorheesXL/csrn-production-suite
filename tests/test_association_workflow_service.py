from __future__ import annotations

from typing import Any

from association_import_service import AssociationImportResult
from association_source_service import AssociationSourceResult
from association_workflow_service import AssociationWorkflowService


class StubSourceService:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []
        self.result = AssociationSourceResult(
            "OK",
            {
                "rows": [
                    {"School": "North High School", "Broadcast": "North"},
                    {"School": "South High School", "Broadcast": "South"},
                ],
                "row_count": 2,
                "source": {
                    "sha256": "abc123",
                    "requested_url": "https://association.example/schools.csv",
                    "final_url": "https://association.example/schools.csv",
                    "content_type": "text/csv",
                    "retrieved_at": "2026-07-24T20:30:00+00:00",
                    "size_bytes": 100,
                },
                "warnings": {"missing_source_fields": []},
            },
        )

    def load(
        self,
        profile: dict[str, Any],
        *,
        supplied_content: bytes | str | None = None,
        supplied_content_type: str = "",
    ) -> AssociationSourceResult:
        self.calls.append((profile, supplied_content, supplied_content_type))
        return self.result


class StubImportService:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, ...]] = []
        self.analysis = AssociationImportResult(
            "OK",
            {
                "profile": {"id": "test-association"},
                "found": 2,
                "new": 2,
                "existing": 0,
                "possible_duplicates": 0,
                "invalid": 0,
                "schools": [
                    {"status": "new", "candidate": {"official_name": "North"}},
                    {"status": "new", "candidate": {"official_name": "South"}},
                ],
            },
        )
        self.applied = AssociationImportResult(
            "OK",
            {
                "profile": {"id": "test-association"},
                "imported": 2,
                "enriched_existing": 0,
                "skipped_existing": 0,
                "possible_duplicates": [],
                "invalid": [],
                "created_ids": ["MS-001", "MS-002"],
                "total_schools": 2,
            },
        )

    def analyze(
        self,
        profile: dict[str, Any],
        rows: list[dict[str, Any]],
    ) -> AssociationImportResult:
        self.calls.append(("analyze", profile, rows))
        return self.analysis

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
                profile,
                rows,
                create_venues,
                allow_possible_duplicates,
            )
        )
        return self.applied


def profile(*, preview_limit: int = 500) -> dict[str, Any]:
    return {
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
        "options": {"preview_limit": preview_limit},
    }


def make_service() -> tuple[
    AssociationWorkflowService,
    StubSourceService,
    StubImportService,
]:
    source = StubSourceService()
    importer = StubImportService()
    return (
        AssociationWorkflowService(
            source_service=source,
            import_service=importer,
        ),
        source,
        importer,
    )


def test_preview_combines_source_metadata_samples_and_analysis() -> None:
    service, source, importer = make_service()

    result = service.preview(
        profile(),
        supplied_content="School,Broadcast\nNorth High School,North",
        supplied_content_type="text/csv",
    )

    assert result.ok
    assert result.data["source"]["sha256"] == "abc123"
    assert result.data["row_count"] == 2
    assert result.data["columns"] == ["Broadcast", "School"]
    assert result.data["sample_rows"][0]["School"] == "North High School"
    assert result.data["analysis"]["found"] == 2
    assert result.data["analysis"]["truncated"] is False
    assert source.calls[0][1] == "School,Broadcast\nNorth High School,North"
    assert importer.calls[0][0] == "analyze"


def test_preview_applies_profile_preview_limit() -> None:
    service, _source, _importer = make_service()

    result = service.preview(profile(preview_limit=1))

    assert result.data["analysis"]["returned"] == 1
    assert result.data["analysis"]["truncated"] is True
    assert len(result.data["analysis"]["schools"]) == 1


def test_preview_propagates_source_and_analysis_errors() -> None:
    service, source, importer = make_service()
    source.result = AssociationSourceResult("SOURCE_PARSE_FAILED")
    source_error = service.preview(profile())

    source.result = AssociationSourceResult(
        "OK",
        {
            "rows": [],
            "row_count": 0,
            "source": {"sha256": "abc123"},
            "warnings": {},
        },
    )
    importer.analysis = AssociationImportResult("FIELD_MAPPING_REQUIRED")
    analysis_error = service.preview(profile())

    assert source_error.code == "SOURCE_PARSE_FAILED"
    assert analysis_error.code == "FIELD_MAPPING_REQUIRED"


def test_apply_requires_explicit_approval_and_preview_hash() -> None:
    service, source, importer = make_service()

    not_approved = service.apply(
        profile(),
        approved=False,
        expected_sha256="abc123",
    )
    no_preview = service.apply(
        profile(),
        approved=True,
        expected_sha256="",
    )

    assert not_approved.code == "IMPORT_APPROVAL_REQUIRED"
    assert no_preview.code == "SOURCE_PREVIEW_REQUIRED"
    assert source.calls == []
    assert importer.calls == []


def test_apply_rejects_source_changed_since_preview() -> None:
    service, _source, importer = make_service()

    result = service.apply(
        profile(),
        approved=True,
        expected_sha256="different-hash",
    )

    assert result.code == "SOURCE_CHANGED_SINCE_PREVIEW"
    assert result.data == {
        "expected_sha256": "different-hash",
        "actual_sha256": "abc123",
    }
    assert importer.calls == []


def test_apply_imports_exact_previewed_source_and_forwards_options() -> None:
    service, _source, importer = make_service()

    result = service.apply(
        profile(),
        approved=True,
        expected_sha256="ABC123",
        create_venues=False,
        allow_possible_duplicates=True,
    )

    assert result.ok
    assert result.data["source"]["sha256"] == "abc123"
    assert result.data["result"]["imported"] == 2
    assert importer.calls[0][0] == "apply"
    assert importer.calls[0][3:] == (False, True)
