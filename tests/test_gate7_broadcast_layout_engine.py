from pathlib import Path
import json
import re

ROOT = Path(__file__).resolve().parents[1]


def test_broadcast_layout_engine_files_exist() -> None:
    for relative in (
        "static/csrn-broadcast-layout-engine.js",
        "static/csrn-broadcast-layout-engine.css",
        "static/csrn-layout-lab.html",
    ):
        assert (ROOT / relative).is_file(), relative


def test_layout_engine_defines_shared_contracts_and_theme_owned_renderers() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    assert "SPORT_CONTRACTS" in source
    assert "PACKAGE_MANIFESTS" in source
    assert "COMPONENT_TYPES" in source
    assert "resolvePlacements" in source
    assert "renderPackage" in source
    for renderer in ("modern", "pixel", "minimal", "press", "stadium", "neon", "classic"):
        assert re.search(rf"\b{renderer}\(state,\s*sport\)", source)
    # collegiate owns the shared video-board mode (player spotlight/highlight
    # video/sponsor spotlight rotating through the VS stage), threaded from
    # renderPackage()'s options.videoMode -- the one renderer with a third
    # parameter for it.
    assert re.search(r"\bcollegiate\(state,\s*sport,\s*videoMode\)", source)
    for component in ("scorebug", "ticker", "playerCard", "highlightVideo", "sponsor", "captions"):
        assert f'"{component}"' in source


def test_layout_engine_supports_initial_multi_sport_contracts() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    for sport in ("football", "basketball", "baseball", "softball"):
        assert f"{sport}:" in source
    assert "inningHalf" in source
    assert "shotClock" in source
    assert "downDistance" in source
    assert "bl-diamond" in source


def test_theme_packages_own_distinct_positions_and_structures() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    assert 'scorebug:{zone:"top-center"' in source
    assert 'scorebug:{zone:"top-right"' in source
    assert 'scorebug:{zone:"top-left"' in source
    assert 'scorebug:{zone:"bottom-center"' in source
    assert "bl-pixel-title" in source
    assert "bl-press-masthead" in source
    assert "bl-stadium-title" in source
    assert "bl-neon-identity-panel" in source
    assert "bl-neon-score-bay" in source


def test_layout_lab_is_parallel_and_does_not_replace_production_overlay() -> None:
    lab = (ROOT / "static" / "csrn-layout-lab.html").read_text(encoding="utf-8")
    overlay = (ROOT / "templates" / "overlay.html").read_text(encoding="utf-8")
    assert "CSRN_LAYOUT_ENGINE_READY" in lab
    assert "csrn-broadcast-layout-engine.js?v=11" in lab
    assert "csrn-broadcast-layout-engine.js" not in overlay
    assert "csrn-scorebug-engine.js" in overlay


def test_layout_engine_has_manifest_and_collision_validation() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    assert "validateManifests" in source
    assert "rectsOverlap" in source
    assert "fallbackZones" in source
    assert "collisionPolicy" in source
    assert 'dataset.collision = "true"' in source


def test_layout_lab_has_diagnostic_mode() -> None:
    lab = (ROOT / "static" / "csrn-layout-lab.html").read_text(encoding="utf-8")
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    assert 'id="diagnostics"' in lab
    assert "diagnostics" in css
    assert 'attr(data-component)' in css
    assert 'attr(data-zone)' in css


def test_every_package_declares_secondary_component_renderer_family() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    assert "PACKAGE_COMPONENT_RENDERERS" in source
    for family in ("modern", "pixel", "minimal", "press", "stadium", "neon", "collegiate", "classic"):
        assert f'{family}: familyRenderers("{family}")' in source
    assert source.count("componentRendererFamily:") == 8


def test_layout_lab_runtime_matrix_covers_all_package_sport_combinations() -> None:
    lab = (ROOT / "static" / "csrn-layout-lab.html").read_text(encoding="utf-8")
    assert "function runMatrix()" in lab
    assert "layoutMatrixCases" in lab
    assert 'dataset.layoutMatrixReady="true"' in lab


def test_stadium_grid_has_explicit_component_placement() -> None:
    css = (ROOT / "static" / "csrn-broadcast-layout-engine.css").read_text(encoding="utf-8")
    assert "grid-column:2;grid-row:2/4" in css
    assert "grid-column:2;grid-row:4" in css
    assert "grid-column:1;grid-row:4" in css
    assert "grid-column:3;grid-row:4" in css


def test_placement_engine_uses_component_sizes_and_auto_fallbacks() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    assert "COMPONENT_DEFAULT_SIZES" in source
    assert "AUTO_FALLBACK_ZONES" in source
    assert "function fitInZone(" in source
    assert "cannot fit in any configured zone" in source


def test_layout_engine_models_presentation_scenarios() -> None:
    source = (ROOT / "static" / "csrn-broadcast-layout-engine.js").read_text(encoding="utf-8")
    lab = (ROOT / "static" / "csrn-layout-lab.html").read_text(encoding="utf-8")
    assert "PRESENTATION_SCENARIOS" in source
    for scenario in ("baseline", "captions", "player", "highlight", "sponsor", "feature"):
        assert f"{scenario}:" in source
    assert 'id="scenario"' in lab
    assert "activeComponents" in lab


