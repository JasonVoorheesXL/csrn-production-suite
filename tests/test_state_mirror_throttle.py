"""Tier 2: the Drive mirror is coalesced, and it is configurable.

The local authority write still happens on every mutation; the mirror into
the (Drive-synced) project folder is disaster-recovery only, so the
background writer flushes at most once per interval / per N mutations.
"""

from __future__ import annotations

import app


def test_env_float_and_int_parse_with_fallbacks(monkeypatch) -> None:
    monkeypatch.setenv("CSRN_TEST_F", "12.5")
    monkeypatch.setenv("CSRN_TEST_I", "7")
    assert app._env_float("CSRN_TEST_F", 1.0) == 12.5
    assert app._env_int("CSRN_TEST_I", 1) == 7
    monkeypatch.setenv("CSRN_TEST_F", "not-a-number")
    monkeypatch.delenv("CSRN_TEST_I", raising=False)
    assert app._env_float("CSRN_TEST_F", 3.0) == 3.0
    assert app._env_int("CSRN_TEST_I", 9) == 9


def test_live_state_repository_is_mirror_throttled_with_defaults() -> None:
    repo = app.STATE_REPOSITORY
    # This machine is Drive-backed, so it's the mirrored variant.
    assert type(repo).__name__ == "LocalMirroredStateRepository"
    assert repo._mirror_min_interval == 90.0
    assert repo._mirror_max_pending_mutations == 8
    assert app.STATE_MIRROR_INTERVAL_SECONDS == 90.0
    assert app.STATE_MIRROR_MAX_MUTATIONS == 8


def test_shutdown_flush_is_wired() -> None:
    # flush() must exist for the atexit / signal-handler hooks in app.py.
    assert hasattr(app.STATE_REPOSITORY, "flush")
    src = (app.Path(app.__file__)).read_text(encoding="utf-8")
    assert "_atexit.register(STATE_REPOSITORY.flush)" in src
    assert "STATE_REPOSITORY.flush()" in src  # in _record_clean_shutdown_and_stop
