from __future__ import annotations

import ast
from pathlib import Path

from flask import Flask

from routes.weather_routes import WeatherRoutesDependencies, create_weather_blueprint
from weather_service import WeatherResult


ROOT = Path(__file__).resolve().parents[1]


def imports_for(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    names.update(
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    )
    return names


def test_weather_service_does_not_import_flask() -> None:
    imports = imports_for(ROOT / "weather_service.py")
    assert all(not name.startswith("flask") for name in imports)


def test_weather_worker_does_not_import_flask_or_app() -> None:
    imports = imports_for(ROOT / "weather_worker.py")
    assert all(not name.startswith("flask") for name in imports)
    assert "app" not in imports


def test_weather_blueprint_marks_management_routes_authenticated() -> None:
    app = Flask("weather_architecture")

    def require_auth(func):
        setattr(func, "_csrn_requires_auth", True)
        return func

    class Service:
        def public_state(self):
            return WeatherResult("OK", {})

    app.register_blueprint(
        create_weather_blueprint(
            WeatherRoutesDependencies(
                require_auth=require_auth,
                get_weather_service=Service,
            )
        )
    )
    public = {"weather_routes.weather_overlay", "weather_routes.weather_overlay_state"}
    endpoints = [rule.endpoint for rule in app.url_map.iter_rules() if rule.endpoint.startswith("weather_routes.")]
    assert endpoints
    for endpoint in endpoints:
        protected = getattr(app.view_functions[endpoint], "_csrn_requires_auth", False)
        assert protected is (endpoint not in public)


def test_application_composition_contains_weather_service_and_blueprint() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "def get_weather_service()" in source
    assert "WEATHER_STATE_FILE" in source
    assert "APPLICATION_BLUEPRINTS.append(WEATHER_ROUTES_BLUEPRINT)" in source


def test_phase5_architecture_knows_weather_public_contract() -> None:
    source = (ROOT / "phase5_architecture.py").read_text(encoding="utf-8")
    assert '"weather_routes"' in source
    assert '"weather_routes.weather_overlay"' in source
    assert '"weather_routes.weather_overlay_state"' in source


def test_emergency_overlay_has_no_sponsor_slot() -> None:
    source = (ROOT / "templates" / "weather.html").read_text(encoding="utf-8").lower()
    assert "transparent" in source
    assert "sponsor" not in source


def test_weather_documentation_preserves_social_publishing_handoff() -> None:
    source = (ROOT / "docs" / "PHASE_6_5_VENUE_WEATHER_ALERT_OVERLAY.md").read_text(encoding="utf-8")
    assert "Phase 6.9 Social Publishing" in source
    assert "Emergency-warning posts will not contain sponsor branding" in source
