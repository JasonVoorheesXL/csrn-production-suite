"""Round 19: tools/migrate_gameday_backups.py."""
from __future__ import annotations

import json
from pathlib import Path

from tools import migrate_gameday_backups as mig


def _real_snapshot(root: Path, name: str) -> None:
    d = root / name
    (d / "payload" / "Data" / "Schools").mkdir(parents=True)
    (d / "payload" / "Data" / "Schools" / "schools.json").write_text("[]", encoding="utf-8")
    (d / "manifest.json").write_text(json.dumps({"schema": 1, "snapshot_id": name, "kind": "startup",
                                                "files": [], "created_at": 1}), encoding="utf-8")


def _orphan(root: Path, name: str) -> None:
    (root / name / "payload").mkdir(parents=True)
    (root / name / "payload" / "old.json").write_text("{}", encoding="utf-8")  # no manifest.json


def test_classify_splits_real_snapshots_from_junk(tmp_path: Path) -> None:
    old = tmp_path / "old"; old.mkdir()
    _real_snapshot(old, "20260828-180741-startup")
    _real_snapshot(old, "20260830-144742-startup")
    _orphan(old, "20260726-133519-startup")
    (old / ".tmp-20260810-133743-startup" / "payload").mkdir(parents=True)
    (old / "_r1121-emergency-pre-restore-20260810-091847.json").write_text("{}", encoding="utf-8")

    migrate, sweep = mig.classify(old)
    assert sorted(d.name for d in migrate) == ["20260828-180741-startup", "20260830-144742-startup"]
    assert sorted(p.name for p in sweep) == sorted([
        "20260726-133519-startup",
        ".tmp-20260810-133743-startup",
        "_r1121-emergency-pre-restore-20260810-091847.json",
    ])


def test_apply_moves_real_snapshots_and_sweeps_the_rest(tmp_path: Path, monkeypatch) -> None:
    old = tmp_path / "old"; old.mkdir()
    dest = tmp_path / "local" / "GameDay"
    _real_snapshot(old, "20260828-180741-startup")
    _orphan(old, "20260726-133519-startup")
    (old / ".tmp-x" / "payload").mkdir(parents=True)
    (old / "_r1121.json").write_text("{}", encoding="utf-8")

    import app as app_module
    monkeypatch.setattr(app_module, "LEGACY_GAME_DAY_BACKUP_DIR", old, raising=False)
    monkeypatch.setattr(app_module, "GAME_DAY_BACKUP_DIR", dest, raising=False)

    assert mig.main(["--apply"]) == 0

    assert (dest / "20260828-180741-startup" / "manifest.json").is_file()
    assert (dest / ".gameday-backups-migrated").is_file()
    assert not (old / "20260828-180741-startup").exists()   # moved
    assert not (old / "20260726-133519-startup").exists()   # swept
    assert not (old / ".tmp-x").exists()
    assert not (old / "_r1121.json").exists()


def test_dry_run_touches_nothing(tmp_path: Path, monkeypatch) -> None:
    old = tmp_path / "old"; old.mkdir()
    _real_snapshot(old, "20260830-144742-startup")
    _orphan(old, "20260726-133519-startup")
    import app as app_module
    monkeypatch.setattr(app_module, "LEGACY_GAME_DAY_BACKUP_DIR", old, raising=False)
    monkeypatch.setattr(app_module, "GAME_DAY_BACKUP_DIR", tmp_path / "dest", raising=False)

    assert mig.main([]) == 0
    assert (old / "20260830-144742-startup").exists()
    assert (old / "20260726-133519-startup").exists()
    assert not (tmp_path / "dest").exists()
