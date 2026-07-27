from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_phase_6_8_service_and_routes_are_integrated() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "from theme_service import GraphicsThemeService" in source
    assert "create_theme_blueprint" in source
    assert "get_theme_service" in source
    assert "APPLICATION_BLUEPRINTS.append(THEME_ROUTES_BLUEPRINT)" in source


def test_phase_6_8_default_state_is_created() -> None:
    path = ROOT / "Data" / "Themes" / "theme_state.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema"] == 1
    assert payload["active_preset"] == "modern_network"
    assert payload["locked"] is False
    assert payload["variants"] == {}


def test_phase_6_8_overlay_links_are_idempotent() -> None:
    for name in ("overlay.html", "captions.html", "weather.html"):
        source = (ROOT / "templates" / name).read_text(encoding="utf-8")
        assert source.count('/themes/current.css') == 1


def test_phase_6_8_blueprint_audit_is_updated() -> None:
    source = (ROOT / "phase5_architecture.py").read_text(encoding="utf-8")
    assert '"theme_routes"' in source
    assert '"theme_routes.current_theme_css"' in source
    assert '"theme_routes.public_theme_state"' in source


def test_phase_6_8_theme_config_is_present() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert '"graphics_theme": {' in source
    assert '"school_color_adaptation": True' in source
    assert '"season_lock": False' in source


def test_phase_6_8_social_stage_is_not_removed() -> None:
    roadmap = (ROOT / "docs" / "PHASE_6_GAME_DAY_AND_COMMERCIAL_ROADMAP.md").read_text(encoding="utf-8")
    assert "### 6.9 Social Publishing Engine" in roadmap
    assert "Facebook and X" in roadmap
