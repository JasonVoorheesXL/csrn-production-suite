"""Tier 2 goal 1 + 4: the authority and the Drive mirror must be genuinely
independent files, and the startup nlink warning must still catch a
regression.

A hard-linked authority/mirror pair means a Drive lock on the mirror is a
lock on the hot authority write -- the exact contention the local-authority
split is meant to remove. break_authority_mirror_hardlink() rewrites the
authority in place so the two diverge; authority_state_hardlink_warning()
independently flags any leftover extra link (e.g. Drive's transient
.tmp.driveupload).
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

import app as app_module


def _linkable(tmp_path: Path) -> None:
    probe = tmp_path / "a"
    probe.write_text("x", encoding="utf-8")
    try:
        os.link(probe, tmp_path / "b")
    except (OSError, NotImplementedError, AttributeError):
        pytest.skip("hard links not supported on this filesystem")
    finally:
        probe.unlink(missing_ok=True)
        (tmp_path / "b").unlink(missing_ok=True)


def test_no_action_when_files_are_missing(tmp_path: Path) -> None:
    assert app_module.break_authority_mirror_hardlink(tmp_path / "auth.json", tmp_path / "mir.json") is None


def test_no_action_when_already_independent(tmp_path: Path) -> None:
    auth = tmp_path / "auth.json"
    mir = tmp_path / "mir.json"
    auth.write_text('{"state_revision": 5}', encoding="utf-8")
    mir.write_text('{"state_revision": 5}', encoding="utf-8")
    assert app_module.break_authority_mirror_hardlink(auth, mir) is None
    assert auth.stat().st_ino != mir.stat().st_ino


def test_breaks_a_real_hardlinked_pair_and_preserves_content(tmp_path: Path) -> None:
    _linkable(tmp_path)
    auth = tmp_path / "GameDay" / "state.json"
    auth.parent.mkdir()
    auth.write_text('{"state_revision": 42, "broadcast_id": "g"}', encoding="utf-8")
    mir = tmp_path / "Drive" / "state.json"
    mir.parent.mkdir()
    os.link(auth, mir)
    assert auth.stat().st_ino == mir.stat().st_ino  # precondition: same file

    msg = app_module.break_authority_mirror_hardlink(auth, mir)

    assert msg is not None and "independent" in msg
    assert auth.stat().st_ino != mir.stat().st_ino          # now separate inodes
    assert auth.stat().st_nlink == 1
    assert '"state_revision": 42' in auth.read_text(encoding="utf-8")   # content intact
    assert '"state_revision": 42' in mir.read_text(encoding="utf-8")


def test_after_break_the_nlink_warning_is_clear(tmp_path: Path) -> None:
    _linkable(tmp_path)
    auth = tmp_path / "state.json"
    auth.write_text("{}", encoding="utf-8")
    mir = tmp_path / "mirror.json"
    os.link(auth, mir)
    assert app_module.authority_state_hardlink_warning(auth) is not None  # regression detected

    app_module.break_authority_mirror_hardlink(auth, mir)

    assert app_module.authority_state_hardlink_warning(auth) is None       # cleared


def test_a_non_mirror_extra_link_is_left_for_the_warning(tmp_path: Path) -> None:
    # Drive's own .tmp.driveupload link: NOT the mirror. break() must not
    # touch it; the warning must still fire so the operator sees it.
    _linkable(tmp_path)
    auth = tmp_path / "state.json"
    auth.write_text("{}", encoding="utf-8")
    mir = tmp_path / "mirror.json"           # a different, independent file
    mir.write_text("{}", encoding="utf-8")
    drive_tmp = tmp_path / ".tmp.driveupload-463337"
    os.link(auth, drive_tmp)

    assert app_module.break_authority_mirror_hardlink(auth, mir) is None   # not the mirror -> no-op
    assert auth.stat().st_nlink == 2                                       # link untouched
    warning = app_module.authority_state_hardlink_warning(auth)
    assert warning is not None and "hard link" in warning


def test_startup_calls_the_break_only_when_drive_backed() -> None:
    src = Path(app_module.__file__).read_text(encoding="utf-8")
    assert "if DRIVE_BACKED_GAME_DAY_STATE:" in src
    assert "break_authority_mirror_hardlink(STATE_AUTHORITY_PATH, STATE_FILE)" in src
