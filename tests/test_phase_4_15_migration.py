from __future__ import annotations

from pathlib import Path

from tools.apply_phase_4_15 import apply


def test_phase_4_15_migration_is_idempotent(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[1] / "app.py"
    source_text = source.read_text(encoding="utf-8")
    target = tmp_path / "app.py"
    target.write_text(source_text, encoding="utf-8")

    already_integrated = "STATE_SERVICE: StateService | None = None" in source_text
    first = apply(target)
    second = apply(target)
    text = target.read_text(encoding="utf-8")

    assert first is (not already_integrated)
    assert second is False
    assert text.count("from state_service import StateService") == 1
    assert text.count("STATE_SERVICE: StateService | None = None") == 1
    assert 'return get_state_service().load().data["state"]' in text
    assert 'get_state_service().save(state)' in text
    assert 'return get_state_service().public(state).data["state"]' in text
    assert "STATE_REPOSITORY.replace(normalize_state(state))" not in text
