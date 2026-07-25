from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_migration():
    path = ROOT / "tools" / "apply_phase_4_9.py"
    spec = importlib.util.spec_from_file_location("phase_4_9_migration", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_phase_4_9_migration_is_idempotent_and_wires_personnel_service(
    tmp_path: Path,
) -> None:
    target = tmp_path / "app.py"
    target.write_text((ROOT / "app.py").read_text(encoding="utf-8"), encoding="utf-8")
    migration = load_migration()
    migration.APP_PATH = target

    migration.main()
    first = target.read_text(encoding="utf-8")
    migration.main()
    second = target.read_text(encoding="utf-8")

    assert first == second
    assert "from personnel_service import PersonnelService" in first
    assert "PERSONNEL_SERVICE: PersonnelService | None = None" in first
    assert "result = get_personnel_service().create(" in first
    assert "get_personnel_service().attach_headshot(" in first
    assert "get_personnel_service().validate_social(" in first
    assert 'items = load_broadcasters(); items.append(record)' not in first
