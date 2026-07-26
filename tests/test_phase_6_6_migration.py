from __future__ import annotations

from pathlib import Path

import app as app_module
from operational_rehearsal_service import OperationalRehearsalService
from phase5_architecture import EXPECTED_BLUEPRINTS


ROOT = Path(__file__).resolve().parents[1]


def test_phase_6_6_runtime_identity_is_integrated() -> None:
    assert app_module.RUNTIME_VERSION == (
        "Version 1.13.0-alpha.6f — Operational Rehearsal and Release Freeze"
    )
    assert app_module.RUNTIME_BUILD == "V1.13A6F-OPERATIONAL-REHEARSAL-RELEASE-FREEZE"
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "1.13.0-alpha.6f"


def test_rehearsal_blueprint_is_registered_once() -> None:
    assert "rehearsal_routes" in EXPECTED_BLUEPRINTS
    assert "rehearsal_routes" in app_module.app.blueprints
    assert list(app_module.app.blueprints).count("rehearsal_routes") == 1


def test_rehearsal_service_uses_persistent_release_paths() -> None:
    service = app_module.get_rehearsal_service()
    assert isinstance(service, OperationalRehearsalService)
    assert service.state_file == app_module.REHEARSAL_STATE_FILE
    assert service.release_manifest_file == app_module.RELEASE_MANIFEST_FILE
    assert service.version_file == app_module.VERSION_FILE


def test_rehearsal_routes_are_authenticated_in_application_factory() -> None:
    endpoints = [
        rule.endpoint
        for rule in app_module.app.url_map.iter_rules()
        if rule.endpoint.startswith("rehearsal_routes.")
    ]
    assert endpoints
    for endpoint in endpoints:
        assert getattr(app_module.app.view_functions[endpoint], "_csrn_requires_auth", False)


def test_phase_6_6_data_directories_are_part_of_architecture() -> None:
    app_module.ensure_data_architecture()
    assert app_module.REHEARSAL_STATE_FILE.parent.is_dir()
    assert app_module.RELEASE_MANIFEST_FILE.parent.is_dir()
