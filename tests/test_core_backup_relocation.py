"""Tier 2: core backup snapshots move out of the Drive-synced tree.

JsonPersistenceEngine snapshots every save into Data/Backups/Core (and
quarantines into Data/Backups/Quarantine). That folder was inside the
Google-Drive-synced project, so Drive's uploader churned every snapshot.
New snapshots now go to a local, non-synced root; the historical ones are
relocated with tools/migrate_core_backups.py (manual, not on the live path).
"""

from __future__ import annotations

from pathlib import Path

import app
from tools import migrate_core_backups


def test_core_backup_root_honours_explicit_env(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("CSRN_CORE_BACKUP_ROOT", str(tmp_path / "elsewhere"))
    assert app._core_backup_root() == tmp_path / "elsewhere"


def test_core_backup_root_prefers_localappdata_over_the_data_dir(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("CSRN_CORE_BACKUP_ROOT", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "LocalAppData"))
    root = app._core_backup_root()
    assert str(tmp_path / "LocalAppData") in str(root)
    assert root.name == "Backups"
    # not inside the (possibly synced) project Data dir
    assert app.DATA_DIR not in root.parents


def test_core_backup_root_falls_back_to_data_dir_without_localappdata(monkeypatch) -> None:
    monkeypatch.delenv("CSRN_CORE_BACKUP_ROOT", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", "")
    assert app._core_backup_root() == app.LEGACY_CORE_BACKUP_ROOT


def test_live_app_resolves_core_backups_outside_the_data_dir() -> None:
    # On the real (Windows) machine LOCALAPPDATA is set, so this is the
    # effective layout: snapshots land beside the local state authority.
    assert app.CORE_BACKUP_ROOT != app.LEGACY_CORE_BACKUP_ROOT
    assert app.DATA_DIR not in app.CORE_BACKUP_DIR.parents
    assert app.CORE_BACKUP_DIR.name == "Core"
    assert app.CORE_QUARANTINE_DIR.name == "Quarantine"


def test_legacy_notice_is_quiet_when_nothing_is_left_behind(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(app, "CORE_BACKUP_ROOT", tmp_path / "new")
    monkeypatch.setattr(app, "LEGACY_CORE_BACKUP_ROOT", tmp_path / "old")
    assert app.legacy_core_backup_notice() is None  # old dir does not exist
    (tmp_path / "old" / "Core").mkdir(parents=True)
    assert app.legacy_core_backup_notice() is None  # exists but empty


def test_legacy_notice_reports_size_and_the_tool(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(app, "CORE_BACKUP_ROOT", tmp_path / "new")
    monkeypatch.setattr(app, "LEGACY_CORE_BACKUP_ROOT", tmp_path / "old")
    (tmp_path / "old" / "Core" / "state").mkdir(parents=True)
    (tmp_path / "old" / "Core" / "state" / "snap.json").write_text("x" * 4096, encoding="utf-8")
    note = app.legacy_core_backup_notice()
    assert note is not None
    assert "migrate_core_backups.py --apply" in note
    assert str(tmp_path / "old") in note


def test_legacy_notice_is_none_when_roots_match(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(app, "CORE_BACKUP_ROOT", tmp_path / "same")
    monkeypatch.setattr(app, "LEGACY_CORE_BACKUP_ROOT", tmp_path / "same")
    assert app.legacy_core_backup_notice() is None


# --- the migration tool ---------------------------------------------------

def _seed(root: Path) -> None:
    for sub, name in (("Core", "state"), ("Quarantine", "state")):
        d = root / sub / name
        d.mkdir(parents=True)
        (d / "a.json").write_text("aaaa", encoding="utf-8")
        (d / "b.json").write_text("bbbbbb", encoding="utf-8")


def test_plan_moves_lists_every_unmigrated_file(tmp_path: Path) -> None:
    src, dst = tmp_path / "src", tmp_path / "dst"
    _seed(src)
    (dst / "Core" / "state").mkdir(parents=True)
    (dst / "Core" / "state" / "a.json").write_text("already", encoding="utf-8")  # skip this one
    moves = migrate_core_backups.plan_moves(src, dst)
    names = sorted(s.name for s, _ in moves)
    assert names == ["a.json", "b.json", "b.json"]  # Quarantine/a + Core/b + Quarantine/b


def test_apply_moves_files_and_never_overwrites_or_drops(tmp_path: Path) -> None:
    src, dst = tmp_path / "src", tmp_path / "dst"
    _seed(src)
    (dst / "Core" / "state").mkdir(parents=True)
    (dst / "Core" / "state" / "a.json").write_text("KEEP", encoding="utf-8")

    rc = migrate_core_backups.main(["--source", str(src), "--dest", str(dst), "--apply"])
    assert rc == 0

    # pre-existing target untouched
    assert (dst / "Core" / "state" / "a.json").read_text(encoding="utf-8") == "KEEP"
    # everything else relocated, content intact
    assert (dst / "Core" / "state" / "b.json").read_text(encoding="utf-8") == "bbbbbb"
    assert (dst / "Quarantine" / "state" / "a.json").read_text(encoding="utf-8") == "aaaa"
    assert not (src / "Core" / "state" / "b.json").exists()
    # the skipped file stays in the source (it was not moved)
    assert (src / "Core" / "state" / "a.json").read_text(encoding="utf-8") == "aaaa"
    assert (dst / ".core-backups-migrated").exists()


def test_dry_run_moves_nothing(tmp_path: Path) -> None:
    src, dst = tmp_path / "src", tmp_path / "dst"
    _seed(src)
    rc = migrate_core_backups.main(["--source", str(src), "--dest", str(dst)])
    assert rc == 0
    assert (src / "Core" / "state" / "a.json").exists()
    assert not dst.exists()


def test_apply_closing_message_scopes_deletion_to_core_and_quarantine(tmp_path, capsys) -> None:
    # Data/Backups also holds Recovery/GameDay/Installers this tool never
    # touches; the message must not tell the operator to nuke the whole tree.
    src, dst = tmp_path / "src", tmp_path / "dst"
    _seed(src)
    (src / "Recovery").mkdir()
    (src / "Recovery" / "marker.json").write_text("{}", encoding="utf-8")
    migrate_core_backups.main(["--source", str(src), "--dest", str(dst), "--apply"])
    out = capsys.readouterr().out
    assert "Core" in out and "Quarantine" in out
    assert "delete the empty" not in out
    assert (src / "Recovery" / "marker.json").exists()  # untouched
