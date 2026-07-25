from __future__ import annotations

from pathlib import Path

from tools.apply_phase_4_18 import apply


def test_phase_4_18_migration_is_idempotent(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[1] / "app.py"
    source_text = source.read_text(encoding="utf-8")
    target = tmp_path / "app.py"
    target.write_text(source_text, encoding="utf-8")

    already_integrated = "EVENT_SERVICE: EventService | None = None" in source_text
    first = apply(target)
    second = apply(target)
    text = target.read_text(encoding="utf-8")

    assert first is (not already_integrated)
    assert second is False
    assert text.count("from event_service import EventService") == 1
    assert text.count("EVENT_SERVICE: EventService | None = None") == 1
    assert "get_event_service().trigger" in text
    assert "get_event_service().quick_correction" in text
    assert "get_event_service().edit" in text
    assert "get_event_service().undo" in text
    assert "def event_trigger():\n    data = request.get_json" not in text
