from __future__ import annotations

from pathlib import Path

import tools.apply_phase_4_7 as migration


def test_phase_4_7_migration_is_valid_and_idempotent(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = Path("app.py").read_text(encoding="utf-8")
    target = tmp_path / "app.py"
    target.write_text(source, encoding="utf-8")
    monkeypatch.setattr(migration, "APP_PATH", target)

    migration.main()
    first = target.read_text(encoding="utf-8")

    assert "from venue_service import VenueService" in first
    assert "VENUE_SERVICE: VenueService | None = None" in first
    assert "return get_venue_service().for_school(school, sport)" in first
    assert "get_venue_service().migrate_legacy_names()" in first
    assert first.count('@app.get("/api/venues")') == 1
    assert first.count('@app.get("/api/venues/<venue_id>")') == 1
    assert first.count('def readiness_payload() -> dict[str, Any]:') == 1
    assert first.count('def school_duplicate_candidates(') == 1
    compile(first, str(target), "exec")

    migration.main()
    second = target.read_text(encoding="utf-8")
    assert second == first
