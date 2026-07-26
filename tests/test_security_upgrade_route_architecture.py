from __future__ import annotations

import ast
from pathlib import Path

import app as app_module


ROOT = Path(__file__).resolve().parents[1]
MIGRATED_PATHS = {
    "/api/security-status",
    "/api/setup-pin",
    "/api/login",
    "/api/logout",
    "/api/upgrade/candidate",
    "/api/upgrade/status",
    "/api/upgrade/migrate",
}


def test_security_upgrade_routes_are_registered_through_blueprint() -> None:
    endpoint_by_path = {
        rule.rule: rule.endpoint
        for rule in app_module.app.url_map.iter_rules()
        if rule.rule in MIGRATED_PATHS
    }
    assert set(endpoint_by_path) == MIGRATED_PATHS
    assert all(
        endpoint.startswith("security_upgrade_routes.")
        for endpoint in endpoint_by_path.values()
    )


def test_app_collects_security_upgrade_blueprint_once() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert source.count(
        "APPLICATION_BLUEPRINTS.append(SECURITY_UPGRADE_ROUTES_BLUEPRINT)"
    ) == 1
    assert source.count(
        "SECURITY_UPGRADE_ROUTES_BLUEPRINT = "
        "create_security_upgrade_blueprint("
    ) == 1


def test_migrated_security_upgrade_decorators_are_removed_from_app() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    for marker in (
        '@app.get("/api/security-status")',
        '@app.post("/api/setup-pin")',
        '@app.post("/api/login")',
        '@app.post("/api/logout")',
        '@app.get("/api/upgrade/candidate")',
        '@app.get("/api/upgrade/status")',
        '@app.post("/api/upgrade/migrate")',
    ):
        assert marker not in source


def test_security_upgrade_routes_module_does_not_import_application_root() -> None:
    source = (
        ROOT / "routes" / "security_upgrade_routes.py"
    ).read_text(encoding="utf-8")
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
