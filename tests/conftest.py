from __future__ import annotations

import mimetypes


def pytest_configure() -> None:
    """Keep multipart CSV tests deterministic on Windows and Linux."""

    mimetypes.add_type("text/csv", ".csv", strict=True)


# Archived tests for the RETIRED standalone Neon build (2026-09 redesign; see
# tests/retired/neon_v1/README.md). They document that attempt's frozen-pixel
# architecture and are kept for history, not run.
collect_ignore = ["retired"]
