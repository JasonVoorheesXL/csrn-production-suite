from __future__ import annotations

from pathlib import Path

import tools.apply_phase_4_8 as migration


def test_phase_4_8_migration_is_syntactically_valid_and_idempotent(
    tmp_path: Path,
    monkeypatch,
) -> None:
    source = Path("app.py").read_text(encoding="utf-8")
    target = tmp_path / "app.py"
    target.write_text(source, encoding="utf-8")
    monkeypatch.setattr(migration, "APP_PATH", target)

    migration.main()
    first = target.read_text(encoding="utf-8")

    assert "from broadcast_service import BroadcastService" in first
    assert "BROADCAST_SERVICE: BroadcastService | None = None" in first
    assert "return get_broadcast_service().next_id(" in first
    assert "get_broadcast_service().update_linked_status(" in first
    assert "get_broadcast_service().resume_record(broadcast_id)" in first
    assert "result = get_broadcast_service().create(" in first
    assert first.count('@app.post("/api/create-broadcast")') == 1
    assert first.count('@app.get("/api/broadcasts")') == 1
    assert first.count('@app.get("/api/broadcasts/<broadcast_id>")') == 1
    assert first.count('@app.put("/api/broadcasts/<broadcast_id>")') == 1
    assert first.count('@app.delete("/api/broadcasts/<broadcast_id>")') == 1
    compile(first, str(target), "exec")

    migration.main()
    second = target.read_text(encoding="utf-8")
    assert second == first
