from __future__ import annotations

import mimetypes
import os
import tempfile


def pytest_configure() -> None:
    """Keep multipart CSV tests deterministic on Windows and Linux."""

    mimetypes.add_type("text/csv", ".csv", strict=True)

    # build_command_center_server() takes a game-day safety snapshot, and
    # app.GAME_DAY_BACKUP_DIR is fixed at import time from this variable
    # (default: %LOCALAPPDATA%\PossumFrog\...\GameDay, the operator's real
    # rollback points). Point every test process at a throwaway folder before
    # anything imports app, so tests can never add or prune real snapshots.
    os.environ["CSRN_GAME_DAY_BACKUP_ROOT"] = tempfile.mkdtemp(
        prefix="csrn-test-gameday-"
    )


# Archived tests for the RETIRED standalone Neon build (2026-09 redesign; see
# tests/retired/neon_v1/README.md). They document that attempt's frozen-pixel
# architecture and are kept for history, not run.
collect_ignore = ["retired"]
