from __future__ import annotations

from pathlib import Path

from tools.apply_phase_4_13 import apply


def test_phase_4_13_migration_is_idempotent(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[1] / "app.py"
    target = tmp_path / "app.py"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    first = apply(target)
    second = apply(target)
    text = target.read_text(encoding="utf-8")

    assert first is True
    assert second is False
    assert text.count("from obs_service import OBSService") == 1
    assert text.count("OBS_SERVICE: OBSService | None = None") == 1
    assert "get_obs_service().test_connection()" in text
    assert "get_obs_service().scorebug_visibility" in text
    assert "get_obs_service().program_visual_mode" in text
    assert "validate_obs_read_only(cfg.get(\"obs\", {}))" not in text
