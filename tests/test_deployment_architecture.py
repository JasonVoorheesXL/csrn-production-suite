from __future__ import annotations

from pathlib import Path

import app
from phase5_architecture import audit_phase5_architecture


ROOT = Path(__file__).resolve().parents[1]


def test_deployment_blueprint_is_registered_once() -> None:
    assert "deployment_routes" in app.app.blueprints
    matching = [name for name in app.app.blueprints if name == "deployment_routes"]
    assert matching == ["deployment_routes"]


def test_deployment_routes_pass_application_architecture_audit() -> None:
    report = audit_phase5_architecture(app.app, ROOT / "app.py")
    assert report["ok"], report["errors"]


def test_deployment_endpoints_are_authenticated() -> None:
    endpoints = [
        rule.endpoint
        for rule in app.app.url_map.iter_rules()
        if rule.endpoint.startswith("deployment_routes.")
    ]
    assert endpoints
    assert all(getattr(app.app.view_functions[name], "_csrn_requires_auth", False) for name in endpoints)


def test_source_checkout_preserves_repository_data_layout() -> None:
    assert app.PRODUCT_PATHS.installed_mode is False
    assert app.DATA_DIR == ROOT / "Data"


def test_installer_preserves_external_customer_data() -> None:
    installer = (ROOT / "packaging" / "windows" / "csrn-production-suite.iss").read_text(encoding="utf-8")
    assert "{localappdata}\\Programs\\PossumFrog" in installer
    assert "Customer runtime data" in installer
    assert "{localappdata}\\PossumFrog\\CSRN Production Suite" in installer


def test_release_builder_excludes_customer_and_secret_files() -> None:
    source = (ROOT / "tools" / "build_release_package.py").read_text(encoding="utf-8")
    assert '"Data"' in source
    assert '"security.json"' in source
    assert '"state.json"' in source


def test_client_does_not_embed_a_license_signing_secret() -> None:
    source = (ROOT / "entitlement_service.py").read_text(encoding="utf-8")
    assert "Provider-neutral licensing boundary" in source
    assert "shared signing secret" in source
    assert "hmac" not in source.casefold()


def test_social_publishing_requirement_remains_phase_6_9() -> None:
    roadmap = (ROOT / "docs" / "PHASE_6_GAME_DAY_AND_COMMERCIAL_ROADMAP.md").read_text(encoding="utf-8")
    phase = (ROOT / "docs" / "PHASE_6_7_INSTALLER_UPDATES_LICENSING.md").read_text(encoding="utf-8")
    assert "### 6.9 Social Publishing Engine" in roadmap
    assert "Phase 6.9 remains the Social Publishing Engine" in phase


