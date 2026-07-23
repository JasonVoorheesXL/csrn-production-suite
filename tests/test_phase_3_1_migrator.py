from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "apply_phase_3_1.py"
spec = importlib.util.spec_from_file_location("apply_phase_3_1", MODULE_PATH)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def sample_source() -> str:
    return f'''from core_repositories import ConfigurationRepository, StateRepository, SecurityRepository\n\n{module.REPOSITORY_ANCHOR}\n\ndef reconcile_5a_csrn_ids(schools):\n    return False\n\ndef ensure_school_schema(school, schools):\n    return school\n\n{module.LOAD_OLD}\n'''


def test_transform_integrates_repository() -> None:
    updated = module.transform(sample_source())
    assert "from school_repository import SchoolRepository" in updated
    assert "SCHOOL_REPOSITORY = SchoolRepository" in updated
    assert "return SCHOOL_REPOSITORY.load()" in updated
    assert "SCHOOL_REPOSITORY.save(schools)" in updated
    assert "SCHOOLS_FILE.write_text" not in updated


def test_transform_is_idempotent() -> None:
    once = module.transform(sample_source())
    assert module.transform(once) == once


def test_transform_rejects_missing_anchor() -> None:
    with pytest.raises(RuntimeError):
        module.transform("from __future__ import annotations\n")
