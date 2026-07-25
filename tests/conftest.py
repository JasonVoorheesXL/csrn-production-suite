from __future__ import annotations

import mimetypes


def pytest_configure() -> None:
    """Keep multipart CSV tests deterministic on Windows and Linux."""

    mimetypes.add_type("text/csv", ".csv", strict=True)
