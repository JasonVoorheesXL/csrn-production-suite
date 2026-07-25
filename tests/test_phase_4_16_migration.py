from __future__ import annotations

from pathlib import Path

from tools.apply_phase_4_16 import apply


def test_phase_4_16_migration_is_idempotent(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[1] / "app.py"
    source_text = source.read_text(encoding="utf-8")
    target = tmp_path / "app.py"
    target.write_text(source_text, encoding="utf-8")

    already_integrated = (
        "DIAGNOSTICS_SERVICE: DiagnosticsService | None = None"
        in source_text
    )
    first = apply(target)
    second = apply(target)
    text = target.read_text(encoding="utf-8")

    assert first is (not already_integrated)
    assert second is False
    assert text.count("from diagnostics_service import DiagnosticsService") == 1
    assert text.count(
        "DIAGNOSTICS_SERVICE: DiagnosticsService | None = None"
    ) == 1
    assert "get_diagnostics_service().diagnostics()" in text
    assert "get_diagnostics_service().readiness()" in text
    assert "migrate_venue_names()\n    return jsonify(readiness_payload())" not in text
