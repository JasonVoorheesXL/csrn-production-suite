from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any

from association_import_service import AssociationImportService
from association_source_service import AssociationSourceService


Record = dict[str, Any]


@dataclass(frozen=True)
class AssociationWorkflowResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.code == "OK"


class AssociationWorkflowService:
    """Coordinate source loading, preview analysis, and approved imports."""

    DEFAULT_PREVIEW_LIMIT = 500
    DEFAULT_SAMPLE_LIMIT = 10

    def __init__(
        self,
        *,
        source_service: AssociationSourceService,
        import_service: AssociationImportService,
    ) -> None:
        self._source_service = source_service
        self._import_service = import_service

    def preview(
        self,
        profile: Record,
        *,
        supplied_content: bytes | str | None = None,
        supplied_content_type: str = "",
    ) -> AssociationWorkflowResult:
        source_result = self._source_service.load(
            profile,
            supplied_content=supplied_content,
            supplied_content_type=supplied_content_type,
        )
        if not source_result.ok:
            return AssociationWorkflowResult(source_result.code, source_result.data)

        rows = source_result.data.get("rows", [])
        analysis_result = self._import_service.analyze(profile, rows)
        if not analysis_result.ok:
            return AssociationWorkflowResult(
                analysis_result.code,
                analysis_result.data,
            )

        analysis = copy.deepcopy(analysis_result.data)
        preview_limit = self._preview_limit(profile)
        schools = list(analysis.get("schools", []))
        analysis["schools"] = schools[:preview_limit]
        analysis["returned"] = len(analysis["schools"])
        analysis["truncated"] = len(schools) > preview_limit

        sample_limit = self.DEFAULT_SAMPLE_LIMIT
        return AssociationWorkflowResult(
            "OK",
            {
                "profile": copy.deepcopy(analysis.get("profile", {})),
                "source": copy.deepcopy(source_result.data.get("source", {})),
                "warnings": copy.deepcopy(
                    source_result.data.get("warnings", {})
                ),
                "row_count": int(source_result.data.get("row_count", 0)),
                "columns": self._columns(rows),
                "sample_rows": copy.deepcopy(list(rows)[:sample_limit]),
                "analysis": analysis,
            },
        )

    def apply(
        self,
        profile: Record,
        *,
        approved: bool,
        expected_sha256: str,
        supplied_content: bytes | str | None = None,
        supplied_content_type: str = "",
        create_venues: bool | None = None,
        allow_possible_duplicates: bool = False,
    ) -> AssociationWorkflowResult:
        if not approved:
            return AssociationWorkflowResult("IMPORT_APPROVAL_REQUIRED")

        expected_hash = str(expected_sha256 or "").strip().lower()
        if not expected_hash:
            return AssociationWorkflowResult("SOURCE_PREVIEW_REQUIRED")

        source_result = self._source_service.load(
            profile,
            supplied_content=supplied_content,
            supplied_content_type=supplied_content_type,
        )
        if not source_result.ok:
            return AssociationWorkflowResult(source_result.code, source_result.data)

        actual_hash = str(
            source_result.data.get("source", {}).get("sha256", "")
        ).strip().lower()
        if not actual_hash or actual_hash != expected_hash:
            return AssociationWorkflowResult(
                "SOURCE_CHANGED_SINCE_PREVIEW",
                {
                    "expected_sha256": expected_hash,
                    "actual_sha256": actual_hash,
                },
            )

        result = self._import_service.apply(
            profile,
            source_result.data.get("rows", []),
            create_venues=create_venues,
            allow_possible_duplicates=allow_possible_duplicates,
        )
        if not result.ok:
            return AssociationWorkflowResult(result.code, result.data)

        return AssociationWorkflowResult(
            "OK",
            {
                "profile": copy.deepcopy(result.data.get("profile", {})),
                "source": copy.deepcopy(source_result.data.get("source", {})),
                "warnings": copy.deepcopy(
                    source_result.data.get("warnings", {})
                ),
                "row_count": int(source_result.data.get("row_count", 0)),
                "result": copy.deepcopy(result.data),
            },
        )

    @classmethod
    def _preview_limit(cls, profile: Record) -> int:
        options = profile.get("options") or {}
        try:
            requested = int(options.get("preview_limit", cls.DEFAULT_PREVIEW_LIMIT))
        except (TypeError, ValueError):
            requested = cls.DEFAULT_PREVIEW_LIMIT
        return min(1000, max(1, requested))

    @staticmethod
    def _columns(rows: list[Record]) -> list[str]:
        columns: set[str] = set()
        for row in rows[:100]:
            if isinstance(row, dict):
                columns.update(str(key) for key in row)
        return sorted(columns, key=str.casefold)
