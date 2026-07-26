from __future__ import annotations

import ast
from pathlib import Path

from flask import Flask

from commissioning_service import HardwareOBSCommissioningService
from routes.commissioning_routes import (
    CommissioningRoutesDependencies,
    create_commissioning_blueprint,
)


ROOT = Path(__file__).resolve().parents[1]


def test_commissioning_service_has_no_flask_dependency() -> None:
    source = (ROOT / "commissioning_service.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imports.update(
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    )
    assert "flask" not in imports


def test_commissioning_routes_do_not_import_app() -> None:
    source = (ROOT / "routes" / "commissioning_routes.py").read_text(
        encoding="utf-8"
    )
    assert "import app" not in source
    assert "from app import" not in source


def test_commissioning_blueprint_marks_every_route_authenticated() -> None:
    def require_auth(func):
        setattr(func, "_csrn_requires_auth", True)
        return func

    class Service:
        pass

    blueprint = create_commissioning_blueprint(
        CommissioningRoutesDependencies(
            require_auth=require_auth,
            get_commissioning_service=lambda: Service(),
        )
    )
    app = Flask(__name__)
    app.register_blueprint(blueprint)
    endpoints = [
        rule.endpoint
        for rule in app.url_map.iter_rules()
        if rule.endpoint.startswith("commissioning_routes.")
    ]
    assert len(endpoints) == 5
    assert all(getattr(app.view_functions[item], "_csrn_requires_auth", False) for item in endpoints)


def test_default_profile_matches_p4next_multitrack_contract() -> None:
    profile = HardwareOBSCommissioningService.default_profile()
    device = profile["device"]
    assert device["model"] == "P4next"
    assert device["usb_mode"] == "Multi Track"
    assert device["recorder_mode"] == "Multi Track"
    assert device["sample_rate_hz"] == 48000
    assert device["bit_depth"] == 24
    assert [item["channel"] for item in profile["channels"]] == [1, 2, 3, 4]
