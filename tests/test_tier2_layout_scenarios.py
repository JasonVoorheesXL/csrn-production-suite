"""Tier 2 goal 5: a fresh install initializes correctly under the new
storage layout, and an EXISTING install with the old hardlinked / co-located
layout migrates-or-degrades safely on first run -- no crash, no data drop.

These exercise the two pieces together the way startup does:
  break_authority_mirror_hardlink(authority, mirror)   # app.py, serve path
  LocalMirroredStateRepository(authority, mirror, ...)  # throttled mirror
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pytest

import app as app_module
from core_repositories import LocalMirroredStateRepository
from persistence_engine import JsonPersistenceEngine

STATE_DEFAULTS = {
    "broadcast_id": "",
    "home_score": 0,
    "visitor_score": 0,
    "next_play_number": 1,
    "history": [],
    "events": [],
    "correction_log": [],
    "crew": {},
}


def _engine(tmp_path: Path) -> JsonPersistenceEngine:
    return JsonPersistenceEngine(tmp_path / "Backups" / "Core", tmp_path / "Backups" / "Quarantine")


def _wait(predicate, timeout: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            if predicate():
                return True
        except (OSError, ValueError, KeyError):
            pass
        time.sleep(0.02)
    try:
        return bool(predicate())
    except Exception:
        return False


# --- fresh install ------------------------------------------------------

def test_fresh_install_initializes_with_no_prior_state(tmp_path: Path) -> None:
    authority = tmp_path / "LocalAppData" / "GameDay" / "state.json"
    mirror = tmp_path / "Drive" / "project" / "state.json"
    assert not authority.exists() and not mirror.exists()

    # startup would call this first; with nothing there it is a no-op
    assert app_module.break_authority_mirror_hardlink(authority, mirror) is None

    repo = LocalMirroredStateRepository(
        _engine(tmp_path),
        authority_path=authority,
        mirror_path=mirror,
        defaults=STATE_DEFAULTS,
        mirror_min_interval=90.0,
        mirror_max_pending_mutations=8,
    )

    # authority created with defaults, load works, first mutation persists
    assert authority.exists()
    assert repo.load()["home_score"] == 0
    repo.replace({**STATE_DEFAULTS, "broadcast_id": "opener", "state_revision": 1})
    assert json.loads(authority.read_text())["broadcast_id"] == "opener"
    # first real mutation reaches the mirror immediately (not stuck on defaults)
    assert _wait(lambda: json.loads(mirror.read_text())["broadcast_id"] == "opener")
    repo.flush()


# --- existing install, old co-located / hardlinked layout --------------

def test_existing_hardlinked_layout_degrades_safely_on_first_run(tmp_path: Path) -> None:
    probe = tmp_path / "probe"
    probe.write_text("x", encoding="utf-8")
    try:
        os.link(probe, tmp_path / "probe2")
    except (OSError, NotImplementedError, AttributeError):
        pytest.skip("hard links not supported here")
    finally:
        probe.unlink(missing_ok=True)
        (tmp_path / "probe2").unlink(missing_ok=True)

    authority = tmp_path / "LocalAppData" / "GameDay" / "state.json"
    authority.parent.mkdir(parents=True)
    authority.write_text(
        json.dumps({**STATE_DEFAULTS, "broadcast_id": "mid-game", "home_score": 21, "state_revision": 20}),
        encoding="utf-8",
    )
    mirror = tmp_path / "Drive" / "project" / "state.json"
    mirror.parent.mkdir(parents=True)
    os.link(authority, mirror)  # the exact bad layout from the incident
    assert authority.stat().st_ino == mirror.stat().st_ino

    # startup step 1: break the link
    msg = app_module.break_authority_mirror_hardlink(authority, mirror)
    assert msg is not None
    assert authority.stat().st_ino != mirror.stat().st_ino
    assert authority.stat().st_nlink == 1

    # startup step 2: repo comes up, no crash, existing game NOT lost
    repo = LocalMirroredStateRepository(
        _engine(tmp_path),
        authority_path=authority,
        mirror_path=mirror,
        defaults=STATE_DEFAULTS,
        mirror_min_interval=90.0,
        mirror_max_pending_mutations=8,
    )
    loaded = repo.load()
    assert loaded["broadcast_id"] == "mid-game"
    assert loaded["home_score"] == 21

    # a subsequent write goes to the (now independent) authority, and the
    # first post-recovery mutation still reaches the mirror promptly
    repo.replace({**STATE_DEFAULTS, "broadcast_id": "mid-game", "home_score": 28, "state_revision": 21})
    assert json.loads(authority.read_text())["home_score"] == 28
    assert _wait(lambda: json.loads(mirror.read_text())["home_score"] == 28)
    # and the two paths stay separate inodes after real writes
    assert authority.stat().st_ino != mirror.stat().st_ino
    repo.flush()


def test_existing_layout_with_newer_mirror_recovers_into_authority(tmp_path: Path) -> None:
    from core_repositories import StateRepository

    eng = _engine(tmp_path)
    authority = tmp_path / "LocalAppData" / "state.json"
    mirror = tmp_path / "Drive" / "state.json"
    StateRepository(eng, authority, STATE_DEFAULTS).replace(
        {**STATE_DEFAULTS, "broadcast_id": "stale-local", "state_revision": 3}
    )
    StateRepository(eng, mirror, STATE_DEFAULTS).replace(
        {**STATE_DEFAULTS, "broadcast_id": "newer-drive", "state_revision": 9}
    )

    repo = LocalMirroredStateRepository(
        eng, authority_path=authority, mirror_path=mirror, defaults=STATE_DEFAULTS,
        mirror_min_interval=90.0, mirror_max_pending_mutations=8,
    )
    assert repo.load()["broadcast_id"] == "newer-drive"
    assert json.loads(authority.read_text())["state_revision"] == 9
