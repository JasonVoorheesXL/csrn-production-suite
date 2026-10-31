from __future__ import annotations

import mimetypes
import os
import tempfile

import pytest


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


@pytest.fixture(autouse=True)
def _no_real_operator_dialogs(monkeypatch):
    """Never pop a real Windows message box from a test.

    csrn_desktop._warn_operator() calls MessageBoxW, which shows on the
    operator's desktop (and blocks its thread until OK). The headless
    csrn_desktop.run() test starts against an empty temp folder, so the
    startup safety snapshot fails and a "Game-day safety snapshot FAILED"
    box appeared on every full suite run. Tests that check the warning patch
    _warn_operator themselves, which overrides this.
    """
    import csrn_desktop  # stdlib-only imports; safe to load for every test

    monkeypatch.setattr(csrn_desktop, "_warn_operator", lambda title, message: None)


# Archived tests for the RETIRED standalone Neon build (2026-09 redesign; see
# tests/retired/neon_v1/README.md). They document that attempt's frozen-pixel
# architecture and are kept for history, not run.
collect_ignore = ["retired"]
