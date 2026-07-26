from __future__ import annotations

import ast
from pathlib import Path

import app as app_module


ROOT = Path(__file__).resolve().parents[1]
ROUTE_MODULES = (
    "broadcast_package_routes.py",
    "broadcast_routes.py",
    "broadcast_lifecycle_routes.py",
)
MIGRATED_PATHS = {
    "/api/packages",
    "/api/packages/<package_id>",
    "/api/packages/<package_id>/duplicate",
    "/api/packages/<package_id>/load",
    "/api/create-broadcast",
    "/api/broadcasts",
    "/api/broadcasts/<broadcast_id>",
    "/api/broadcasts/<broadcast_id>/status",
    "/api/broadcasts/<broadcast_id>/load",
    "/api/initialize-broadcast",
    "/api/start-broadcast",
    "/api/resume-broadcast",
}


def test_broadcast_routes_are_registered_through_blueprints() -> None:
    endpoint_by_path = {
        rule.rule: rule.endpoint
        for rule in app_module.app.url_map.iter_rules()
        if rule.rule in MIGRATED_PATHS
    }
    assert set(endpoint_by_path) == MIGRATED_PATHS
    assert all(
        endpoint.startswith(
            (
                "broadcast_package_routes.",
                "broadcast_routes.",
                "broadcast_lifecycle_routes.",
            )
        )
        for endpoint in endpoint_by_path.values()
    )


def test_app_registers_each_broadcast_blueprint_once() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    for name in (
        "BROADCAST_PACKAGE_ROUTES_BLUEPRINT",
        "BROADCAST_ROUTES_BLUEPRINT",
        "BROADCAST_LIFECYCLE_ROUTES_BLUEPRINT",
    ):
        assert source.count(f"app.register_blueprint({name})") == 1


def test_migrated_broadcast_route_decorators_are_removed_from_app() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    for marker in (
        '@app.get("/api/packages")',
        '@app.post("/api/packages")',
        '@app.post("/api/create-broadcast")',
        '@app.get("/api/broadcasts")',
        '@app.post("/api/initialize-broadcast")',
        '@app.post("/api/start-broadcast")',
        '@app.post("/api/resume-broadcast")',
    ):
        assert marker not in source


def test_broadcast_route_modules_do_not_import_application_root() -> None:
    for filename in ROUTE_MODULES:
        source = (ROOT / "routes" / filename).read_text(encoding="utf-8")
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
