from __future__ import annotations

import time
from pathlib import Path

from tools.sweep_state_tmp import find_orphan_tmp, main


def _touch(path: Path, *, age_seconds: float) -> Path:
    path.write_text("x", encoding="utf-8")
    stamp = time.time() - age_seconds
    import os

    os.utime(path, (stamp, stamp))
    return path


def test_find_orphan_tmp_selects_only_old_matching_temp_files(tmp_path: Path) -> None:
    old_a = _touch(tmp_path / ".state.json.aaaaaa.tmp", age_seconds=7200)
    old_b = _touch(tmp_path / ".state.json.bbbbbb.tmp", age_seconds=3900)
    _touch(tmp_path / ".state.json.cccccc.tmp", age_seconds=120)  # too new
    _touch(tmp_path / "state.json", age_seconds=7200)  # real file, wrong suffix
    _touch(tmp_path / ".broadcasts.json.dddddd.tmp", age_seconds=7200)  # wrong stem

    found = find_orphan_tmp(tmp_path, min_age_seconds=3600)

    assert set(found) == {old_a, old_b}
    # newest-first ordering
    assert found[0] == old_b


def test_find_orphan_tmp_never_returns_the_real_state_file(tmp_path: Path) -> None:
    _touch(tmp_path / "state.json", age_seconds=99999)
    assert find_orphan_tmp(tmp_path, min_age_seconds=0) == []


def test_main_dry_run_reports_without_deleting(tmp_path: Path, capsys) -> None:
    stale = _touch(tmp_path / ".state.json.eeeeee.tmp", age_seconds=7200)

    code = main(["--dir", str(tmp_path), "--min-age-minutes", "60"])

    assert code == 0
    assert stale.exists()
    out = capsys.readouterr().out
    assert "would remove" in out.lower()
    assert "--apply" in out


def test_main_apply_deletes_old_temp_files_only(tmp_path: Path, capsys) -> None:
    stale = _touch(tmp_path / ".state.json.ffffff.tmp", age_seconds=7200)
    fresh = _touch(tmp_path / ".state.json.gggggg.tmp", age_seconds=60)
    real = _touch(tmp_path / "state.json", age_seconds=7200)

    code = main(["--dir", str(tmp_path), "--min-age-minutes", "60", "--apply"])

    assert code == 0
    assert not stale.exists()
    assert fresh.exists()
    assert real.exists()
    assert "Removed 1 file" in capsys.readouterr().out
