from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "apply_phase_3_2.py"
spec = importlib.util.spec_from_file_location("apply_phase_3_2", MODULE_PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def sample_source() -> str:
    return f'''from school_repository import SchoolRepository


def _normalize_rosters(items):
    return False

{module.WRITE_OLD}
'''


def test_transform_integrates_repository_after_normalizer() -> None:
    updated = module.transform(sample_source())
    assert "from roster_repository import RosterRepository" in updated
    assert "ROSTER_REPOSITORY = RosterRepository" in updated
    assert updated.index("def _normalize_rosters") < updated.index("ROSTER_REPOSITORY = RosterRepository")
    assert "return ROSTER_REPOSITORY.load()" in updated
    assert "ROSTER_REPOSITORY.save(items)" in updated
    assert 'os.replace(temp_path, ROSTERS_FILE)' not in updated


def test_transform_is_idempotent() -> None:
    once = module.transform(sample_source())
    assert module.transform(once) == once


def test_transform_rejects_missing_anchor() -> None:
    with pytest.raises(RuntimeError):
        module.transform("from __future__ import annotations\n")


