from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_theme_manager_is_catalog_backed_and_preview_first() -> None:
    page = (ROOT / "templates" / "theme_manager.html").read_text(encoding="utf-8")

    assert 'id="themeSearch"' in page
    assert 'id="categoryFilter"' in page
    assert 'id="previewSelected"' in page
    assert 'id="activateSelected"' in page
    assert "previewedPreset!==selectedPreset" in page
    assert "Live graphics unchanged" in page
    assert "/api/themes/catalog" in page
    assert "/api/themes/preview" in page
    assert "/api/themes/activate" in page


def test_theme_manager_previews_material_graphic_families() -> None:
    page = (ROOT / "templates" / "theme_manager.html").read_text(encoding="utf-8")

    for state in ("scorebug", "lower", "player", "sponsor", "weather", "caption"):
        assert f'data-demo="{state}"' in page
        assert f'data-demo-panel="{state}"' in page

    for label in (
        "Scorebug tokens",
        "Lower-third tokens",
        "Player graphics",
        "Sponsor stage",
        "Weather overlay",
        "Caption overlay",
        "16:9 safe area",
        "Controlled overrides",
    ):
        assert label in page


def test_theme_manager_uses_safe_catalog_rendering_and_responsive_layout() -> None:
    page = (ROOT / "templates" / "theme_manager.html").read_text(encoding="utf-8")

    assert "function escapeHtml(value)" in page
    assert "escapeHtml(preset.name)" in page
    assert "escapeHtml(preset.description)" in page
    assert "@media(max-width:980px)" in page
    assert "grid-template-columns:1fr" in page
    assert 'href="/">Return to Command Center</a>' in page


def test_theme_manager_keeps_advanced_controls_and_season_lock() -> None:
    page = (ROOT / "templates" / "theme_manager.html").read_text(encoding="utf-8")

    for control_id in (
        "primaryColor",
        "secondaryColor",
        "accentColor",
        "fontKey",
        "radius",
        "opacity",
        "variantName",
        "saveVariant",
        "lockButton",
        "unlockButton",
    ):
        assert f'id="{control_id}"' in page

    assert "CHANGE LOCKED SEASON THEME" in page
    assert "LOCK SEASON THEME" in page
    assert "UNLOCK SEASON THEME" in page


def test_theme_manager_repairs_discovery_tabs_and_default_recovery() -> None:
    page = (ROOT / "templates" / "theme_manager.html").read_text(encoding="utf-8")
    assert ".demo{display:none!important}.demo.active{display:block!important}" in page
    assert 'id="previewScorebug" class="csrn-scorebug"' in page
    assert 'id="activateDefault"' in page
    assert "async function activateDefaultTheme()" in page
    assert "preset_id:'modern_network'" in page
    assert "previewThemeCss').textContent=result.css||''" in page
    assert "CSRNScorebugEngine.render" in page

def test_command_center_exposes_real_theme_manager() -> None:
    page = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    assert 'href="/themes"' in page
    assert "Open Theme Catalog" in page or "Theme Manager" in page
    assert 'id="cfgTheme" readonly' in page
    assert "loadActiveGraphicsTheme" in page
    assert "/api/themes/status" in page

def test_theme_manager_scorebug_preview_remains_horizontal_and_themes_are_distinct() -> None:
    page = (ROOT / "templates" / "theme_manager.html").read_text(encoding="utf-8")
    css = (ROOT / "static" / "csrn-scorebug-engine.css").read_text(encoding="utf-8")
    engine = (ROOT / "static" / "csrn-scorebug-engine.js").read_text(encoding="utf-8")
    assert 'id="previewScorebug" class="csrn-scorebug"' in page
    assert "function fitScorebugPreview()" in page
    assert "scale(var(--preview-scale,1))" in css
    for renderer in ("modern", "classic", "pixel", "minimal", "press", "stadium", "neon", "collegiate"):
        assert f"function {renderer}(" in engine

def test_theme_navigation_and_live_overlay_refresh_contract() -> None:
    navigation = (ROOT / "static" / "csrn-navigation.js").read_text(encoding="utf-8")
    overlay = (ROOT / "templates" / "overlay.html").read_text(encoding="utf-8")
    assert "['themes', 'Theme Manager', '/themes']" in navigation
    assert 'id="csrnThemeCss"' in overlay
    assert "pollCsrnThemeRevision" in overlay
    assert "/api/themes/public-state" in overlay


def test_scorebug_preview_uses_production_dom_contract() -> None:
    page = (ROOT / "templates" / "theme_manager.html").read_text(encoding="utf-8")
    engine = (ROOT / "static" / "csrn-scorebug-engine.js").read_text(encoding="utf-8")
    assert 'id="previewScorebug" class="csrn-scorebug"' in page
    assert "/static/csrn-scorebug-engine.js" in page
    assert "CSRNScorebugEngine.render" in page
    assert "function modern(" in engine
    assert "function classic(" in engine
    assert "function minimal(" in engine



def test_component_theme_engine_is_shared_by_preview_and_live() -> None:
    engine = (ROOT / "static" / "csrn-scorebug-engine.js").read_text(encoding="utf-8")
    css = (ROOT / "static" / "csrn-scorebug-engine.css").read_text(encoding="utf-8")
    manager = (ROOT / "templates" / "theme_manager.html").read_text(encoding="utf-8")
    overlay = (ROOT / "templates" / "overlay.html").read_text(encoding="utf-8")
    assert "window.CSRNScorebugEngine" in engine
    assert "const RENDERERS" in engine
    assert 'id="previewScorebug" class="csrn-scorebug"' in manager
    assert "/static/csrn-scorebug-engine.js" in manager
    assert "/static/csrn-scorebug-engine.js" in overlay
    assert "CSRNScorebugEngine.render" in manager
    assert "CSRNScorebugEngine.render" in overlay
    assert "--sb-w:1142px" in css
    assert "--sb-w:1724px" in css
    assert "scale(var(--preview-scale,1))" in css


def test_theme_manifests_select_distinct_scorebug_renderers() -> None:
    source = (ROOT / "theme_service.py").read_text(encoding="utf-8")
    for layout in ("classic","pixel","modern","minimal","press","stadium","neon","collegiate"):
        assert f'"scorebug": "{layout}"' in source
    assert "def _preset_layout_css(" not in source


def test_catalog_renames_retro_and_press_packages() -> None:
    source=(ROOT/"theme_service.py").read_text(encoding="utf-8")
    assert '"name": "8-Bit Gameday"' in source
    assert '"layouts": {"scorebug": "pixel"}' in source
    assert '"name": "Heritage Press"' in source
    assert '"layouts": {"scorebug": "press"}' in source


def test_scorebug_preview_has_visible_failure_state() -> None:
    page=(ROOT/"templates"/"theme_manager.html").read_text(encoding="utf-8")
    assert 'id="scorebugPreviewError"' in page
    assert "Scorebug renderer failed to load." in page
    assert "requestAnimationFrame" in page


