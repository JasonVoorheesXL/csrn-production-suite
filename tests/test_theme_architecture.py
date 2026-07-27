from __future__ import annotations

from pathlib import Path

import app as app_module
from phase5_architecture import audit_phase5_architecture


ROOT = Path(__file__).resolve().parents[1]


def test_theme_blueprint_is_registered_once() -> None:
    application = app_module.create_app()
    assert "theme_routes" in application.blueprints
    assert list(application.blueprints).count("theme_routes") == 1


def test_theme_routes_have_explicit_public_policy() -> None:
    application = app_module.create_app()
    public = {
        rule.endpoint
        for rule in application.url_map.iter_rules()
        if rule.endpoint.startswith("theme_routes.")
        and not getattr(application.view_functions[rule.endpoint], "_csrn_requires_auth", False)
    }
    assert public == {
        "theme_routes.current_theme_css",
        "theme_routes.public_theme_state",
    }


def test_completed_phase5_architecture_remains_clean() -> None:
    application = app_module.create_app()
    audit = audit_phase5_architecture(application, ROOT / "app.py")
    assert audit["ok"], audit["errors"]


def test_all_live_overlay_templates_load_shared_theme_css() -> None:
    for name in ("overlay.html", "captions.html", "weather.html"):
        source = (ROOT / "templates" / name).read_text(encoding="utf-8")
        assert source.count('/themes/current.css') == 1


def test_theme_manager_is_customer_neutral() -> None:
    source = (ROOT / "templates" / "theme_manager.html").read_text(encoding="utf-8")
    assert "Jason" not in source
    assert "Jordan" not in source
    assert "Caledonia" not in source


def test_theme_service_has_eight_presets_and_no_raw_css_override() -> None:
    source = (ROOT / "theme_service.py").read_text(encoding="utf-8")
    assert source.count('"name":') >= 8
    assert '"raw_css"' not in source
    assert "OVERRIDE_KEYS" in source


def test_theme_state_is_customer_data_not_template_code() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert 'THEME_STATE_FILE = DATA_DIR / "Themes" / "theme_state.json"' in source
    assert '"Themes"' in source


def test_runtime_identity_is_phase_6_8() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "Version 1.13.0-alpha.6h — Graphics Theme Engine" in source
    assert "V1.13A6H-GRAPHICS-THEME-ENGINE" in source
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "1.13.0-alpha.6h"


def test_social_publishing_remains_next_stage() -> None:
    roadmap = (ROOT / "docs" / "PHASE_6_GAME_DAY_AND_COMMERCIAL_ROADMAP.md").read_text(encoding="utf-8")
    assert "### 6.8 Graphics Theme Engine" in roadmap
    assert "Theme Engine implementation status: Phase 6.8 foundation integrated." in roadmap
    assert "### 6.9 Social Publishing Engine" in roadmap
    assert "preview-first one-click publishing" in roadmap


def test_theme_documentation_covers_originality_and_social_handoff() -> None:
    source = (ROOT / "docs" / "PHASE_6_8_GRAPHICS_THEME_ENGINE.md").read_text(encoding="utf-8")
    assert "eight original genre-inspired presets" in source
    assert "do not reproduce" in source
    assert "Phase 6.9" in source
    assert "social cards" in source
