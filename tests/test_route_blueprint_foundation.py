from __future__ import annotations

import ast
from pathlib import Path

import app as app_module


ROOT = Path(__file__).resolve().parents[1]
MIGRATED_PATHS = {
    "/api/config",
    "/api/diagnostics",
    "/api/state",
    "/api/readiness",
    "/api/build-journal",
}


def test_system_routes_are_registered_through_blueprint() -> None:
    endpoint_by_path = {
        rule.rule: rule.endpoint
        for rule in app_module.app.url_map.iter_rules()
        if rule.rule in MIGRATED_PATHS
    }
    assert set(endpoint_by_path) == MIGRATED_PATHS
    assert all(
        endpoint.startswith("system_routes.")
        for endpoint in endpoint_by_path.values()
    )


def test_app_collects_system_blueprint_once() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert source.count(
        "APPLICATION_BLUEPRINTS.append(SYSTEM_ROUTES_BLUEPRINT)"
    ) == 1
    assert source.count("SYSTEM_ROUTES_BLUEPRINT = create_system_blueprint(") == 1


def test_migrated_route_decorators_are_removed_from_app() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    for marker in (
        '@app.get("/api/config")',
        '@app.post("/api/config")',
        '@app.get("/api/diagnostics")',
        '@app.get("/api/state")',
        '@app.get("/api/readiness")',
        '@app.get("/api/build-journal")',
    ):
        assert marker not in source


def test_system_routes_module_does_not_import_application_root() -> None:
    source = (ROOT / "routes" / "system_routes.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported_roots.update(
                alias.name.split(".", 1)[0] for alias in node.names
            )
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported_roots.add(node.module.split(".", 1)[0])
    assert "app" not in imported_roots
