from __future__ import annotations

from pathlib import Path

import tools.apply_phase_4_6 as migration


def test_phase_4_6_migration_is_syntactically_valid_and_idempotent(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = Path("app.py").read_text(encoding="utf-8")
    target = tmp_path / "app.py"
    target.write_text(source, encoding="utf-8")
    monkeypatch.setattr(migration, "APP_PATH", target)

    migration.main()
    first = target.read_text(encoding="utf-8")

    assert "from sponsor_service import SponsorService" in first
    assert "SPONSOR_SERVICE: SponsorService | None = None" in first
    assert "return jsonify(get_sponsor_service().list_payload())" in first
    assert first.count('@app.get("/api/sponsors")') == 1
    assert first.count('@app.get("/sponsor-logos/<filename>")') == 1
    assert first.count("def clean_asset_record(") == 1
    compile(first, str(target), "exec")

    migration.main()
    second = target.read_text(encoding="utf-8")

    assert second == first
