from __future__ import annotations

import ast
from pathlib import Path

from flask import Flask

from recovery_service import RecoveryResult
from routes.recovery_routes import (
    RecoveryRoutesDependencies,
    create_recovery_blueprint,
)


ROOT = Path(__file__).resolve().parents[1]


def test_recovery_service_does_not_import_flask() -> None:
    source = (ROOT / "recovery_service.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    from_imports = {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    assert "flask" not in imports
    assert all(not module.startswith("flask") for module in from_imports)


def test_recovery_blueprint_marks_all_routes_authenticated() -> None:
    app = Flask("recovery_architecture")

    def require_auth(func):
        setattr(func, "_csrn_requires_auth", True)
        return func

    class Service:
        def status(self):
            return RecoveryResult("OK", {"recovery": {}})

    app.register_blueprint(
        create_recovery_blueprint(
            RecoveryRoutesDependencies(
                require_auth=require_auth,
                get_recovery_service=Service,
            )
        )
    )
    endpoints = [
        rule.endpoint
        for rule in app.url_map.iter_rules()
        if rule.endpoint.startswith("recovery_routes.")
    ]
    assert endpoints
    for endpoint in endpoints:
        assert getattr(app.view_functions[endpoint], "_csrn_requires_auth", False)


def test_phase_6_roadmap_retains_caption_weather_theme_and_social_requirements() -> None:
    roadmap = (
        ROOT / "docs" / "PHASE_6_GAME_DAY_AND_COMMERCIAL_ROADMAP.md"
    ).read_text(encoding="utf-8")
    assert "### 6.4 Channel-Based Captioning" in roadmap
    assert "### 6.5 Venue Weather Monitoring and Alert Overlay" in roadmap
    assert "### 6.8 Graphics Theme Engine" in roadmap
    assert "### 6.9 Social Publishing Engine" in roadmap
    assert "player headshots" in roadmap
    assert "approved sponsor assets" in roadmap


