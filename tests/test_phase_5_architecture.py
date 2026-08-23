from __future__ import annotations

from pathlib import Path

import app as app_module

from application_factory import build_route_manifest
from phase5_architecture import (
    EXPECTED_BLUEPRINTS,
    PUBLIC_ENDPOINTS,
    audit_phase5_architecture,
)


ROOT = Path(__file__).resolve().parents[1]


def test_application_factory_returns_distinct_equivalent_instances() -> None:
    first = app_module.create_app({"TESTING": True})
    second = app_module.create_app({"TESTING": True})
    assert first is not second
    assert first is not app_module.app
    assert set(first.blueprints) == EXPECTED_BLUEPRINTS
    assert set(second.blueprints) == EXPECTED_BLUEPRINTS
    first_routes = {
        (entry.rule, entry.methods, entry.endpoint)
        for entry in build_route_manifest(first)
    }
    second_routes = {
        (entry.rule, entry.methods, entry.endpoint)
        for entry in build_route_manifest(second)
    }
    assert first_routes == second_routes


def test_global_application_is_factory_built() -> None:
    assert set(app_module.app.blueprints) == EXPECTED_BLUEPRINTS
    assert app_module.app.extensions["csrn_blueprints"]
    assert app_module.app.extensions["csrn_route_manifest"]


def test_completed_route_manifest_has_expected_public_policy() -> None:
    manifest = build_route_manifest(app_module.app)
    actual_public = {
        entry.endpoint
        for entry in manifest
        if entry.endpoint != "static" and not entry.auth_required
    }
    assert actual_public == PUBLIC_ENDPOINTS


def test_phase_5_architecture_audit_passes() -> None:
    report = audit_phase5_architecture(app_module.app, ROOT / "app.py")
    assert report["ok"] is True, report["errors"]
    assert report["errors"] == []
    assert report["blueprints"] == sorted(EXPECTED_BLUEPRINTS)
    assert report["routes"] > 0
    assert report["authenticated_routes"] > report["public_routes"]


def test_app_source_uses_factory_and_central_registration() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "def create_app(" in source
    assert "app = create_app()" in source
    assert "app = Flask(__name__)" not in source
    assert "app.register_blueprint(" not in source
    assert "@app." not in source
    assert "APPLICATION_BLUEPRINTS.append(" in source


def test_factory_module_does_not_import_composition_root() -> None:
    source = (ROOT / "application_factory.py").read_text(encoding="utf-8")
    assert "import app" not in source
    assert "from app import" not in source


