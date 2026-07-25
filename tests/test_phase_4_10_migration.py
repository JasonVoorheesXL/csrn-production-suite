from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_phase_4_10_migration_wires_asset_service(tmp_path: Path) -> None:
    target = tmp_path / "app.py"
    target.write_text(
        (ROOT / "app.py").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "apply_phase_4_10.py")],
        cwd=tmp_path,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout

    migrated = target.read_text(encoding="utf-8")
    assert "from asset_service import AssetService" in migrated
    assert "ASSET_SERVICE: AssetService | None = None" in migrated
    assert "def get_asset_service() -> AssetService:" in migrated
    assert "result = get_asset_service().create(" in migrated
    assert "result = get_asset_service().update(" in migrated
    assert "result = get_asset_service().delete(" in migrated
    assert "service.duplicate_by_hash(sha256, exclude_id=asset_id)" in migrated
    assert "service.attach_file(" in migrated
    assert migrated.count('@app.get("/api/assets")') == 1
    assert migrated.count('@app.post("/api/assets/<asset_id>/upload")') == 1
