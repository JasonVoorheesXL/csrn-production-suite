from __future__ import annotations

from pathlib import Path

from tools.apply_phase_4_14 import apply


def test_phase_4_14_migration_is_idempotent(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[1] / "app.py"
    target = tmp_path / "app.py"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    apply(target)
    second = apply(target)
    text = target.read_text(encoding="utf-8")

    assert second is False
    assert text.count("from configuration_service import ConfigurationService") == 1
    assert text.count(
        "CONFIGURATION_SERVICE: ConfigurationService | None = None"
    ) == 1
    assert "get_configuration_service().read()" in text
    assert "get_configuration_service().update(incoming)" in text
    assert "current[\"application\"][\"version\"] = RUNTIME_VERSION" not in text
