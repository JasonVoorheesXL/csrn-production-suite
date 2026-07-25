from __future__ import annotations

from pathlib import Path

from tools.apply_phase_4_19 import apply


def test_phase_4_19_migration_integrates_rules_service(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[1] / "app.py"
    target = tmp_path / "app.py"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    assert apply(target) is True
    migrated = target.read_text(encoding="utf-8")

    assert "from rules_service import RulesService" in migrated
    assert "RULES_SERVICE: RulesService | None = None" in migrated
    assert "get_rules_service().clock_control" in migrated
    assert "get_rules_service().field_direction" in migrated
    assert "get_rules_service().play" in migrated
    assert 'state=load_state(); action=str(data.get("action","")).lower()' not in migrated
    assert apply(target) is False
