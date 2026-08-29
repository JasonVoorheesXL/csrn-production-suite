from __future__ import annotations

import os
from pathlib import Path

import pytest

import app as app_module


def test_no_warning_when_file_is_missing(tmp_path: Path) -> None:
    assert app_module.authority_state_hardlink_warning(tmp_path / "nope.json") is None


def test_no_warning_for_a_normal_single_link_file(tmp_path: Path) -> None:
    state = tmp_path / "state.json"
    state.write_text("{}", encoding="utf-8")
    assert app_module.authority_state_hardlink_warning(state) is None


def test_warns_when_authority_file_has_an_extra_hard_link(tmp_path: Path) -> None:
    state = tmp_path / "state.json"
    state.write_text("{}", encoding="utf-8")
    link = tmp_path / ".tmp.driveupload-463337"
    try:
        os.link(state, link)
    except (OSError, NotImplementedError, AttributeError):
        pytest.skip("hard links not supported on this filesystem")

    warning = app_module.authority_state_hardlink_warning(state)
    assert warning is not None
    assert "hard link" in warning
    assert str(state) in warning


def test_bad_path_type_is_swallowed_not_raised() -> None:
    # Must never take down startup.
    assert app_module.authority_state_hardlink_warning(object()) is None
