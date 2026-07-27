from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_phase_6_7_runtime_identity_is_applied() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "Version 1.13.0-alpha.6g — Installer, Updates, and Licensing Foundation" in source
    assert "V1.13A6G-INSTALLER-UPDATES-LICENSING" in source
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "1.13.0-alpha.6g"


def test_phase_6_7_stable_paths_are_integrated() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "PRODUCT_PATHS = resolve_product_paths" in source
    assert "STATE_FILE = PRODUCT_PATHS.state_file" in source
    assert "DATA_DIR = PRODUCT_PATHS.data_dir" in source


def test_phase_6_7_services_and_routes_are_integrated() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "get_entitlement_service" in source
    assert "get_deployment_service" in source
    assert "create_deployment_blueprint" in source
    architecture = (ROOT / "phase5_architecture.py").read_text(encoding="utf-8")
    assert '"deployment_routes"' in architecture


def test_phase_6_7_commercial_sequence_is_preserved() -> None:
    roadmap = (ROOT / "docs" / "PHASE_6_GAME_DAY_AND_COMMERCIAL_ROADMAP.md").read_text(encoding="utf-8")
    assert "### 6.7 Installer, Updates, and Licensing Foundation" in roadmap
    assert "### 6.8 Graphics Theme Engine" in roadmap
    assert "### 6.9 Social Publishing Engine" in roadmap
