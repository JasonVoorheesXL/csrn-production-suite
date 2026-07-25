from __future__ import annotations

from pathlib import Path

from tools.apply_phase_4_17 import apply


def test_phase_4_17_migration_is_idempotent(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[1] / "app.py"
    source_text = source.read_text(encoding="utf-8")
    target = tmp_path / "app.py"
    target.write_text(source_text, encoding="utf-8")

    already_integrated = "UPGRADE_SERVICE: UpgradeService | None = None" in source_text
    first = apply(target)
    second = apply(target)
    text = target.read_text(encoding="utf-8")

    assert first is (not already_integrated)
    assert second is False
    assert text.count("from upgrade_service import UpgradeService") == 1
    assert text.count("UPGRADE_SERVICE: UpgradeService | None = None") == 1
    assert "get_upgrade_service().candidate()" in text
    assert "get_upgrade_service().status()" in text
    assert "get_upgrade_service().run(" in text
    assert "report = migrate(BASE_DIR, DEFAULT_CONFIG" not in text
