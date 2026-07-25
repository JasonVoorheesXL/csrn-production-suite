from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_phase_4_11_graphics_integration_is_present() -> None:
    text = (ROOT / "app.py").read_text(encoding="utf-8")
    required = (
        "from graphics_service import GraphicsService",
        "GRAPHICS_SERVICE: GraphicsService | None = None",
        "def get_graphics_service() -> GraphicsService:",
        "get_graphics_service().update_lower_third(load_state(), data)",
        "get_graphics_service().update_player(load_state(), data)",
        "get_graphics_service().update_personnel(load_state(), data)",
        "get_graphics_service().show_automation_player(",
    )
    missing = [marker for marker in required if marker not in text]
    assert not missing, f"Missing Phase 4.11 integration markers: {missing}"
