from __future__ import annotations

import ast
from pathlib import Path

import app as app_module


ROOT = Path(__file__).resolve().parents[1]
SPONSOR_PATHS = {
    "/api/sponsors",
    "/api/sponsors/<sponsor_id>",
    "/api/sponsors/<sponsor_id>/logo",
    "/api/sponsors/<sponsor_id>/asset",
    "/sponsor-logos/<filename>",
}
ASSET_PATHS = {
    "/api/assets",
    "/api/assets/<asset_id>",
    "/api/assets/<asset_id>/upload",
    "/asset-files/<filename>",
}
LOGO_PATHS = {
    "/school-logos/<school_id>/<filename>",
    "/api/schools/<school_id>/logo/process",
    "/api/logos",
}


def test_media_routes_are_registered_through_expected_blueprints() -> None:
    endpoints: dict[str, set[str]] = {}
    for rule in app_module.app.url_map.iter_rules():
        endpoints.setdefault(rule.rule, set()).add(rule.endpoint)

    for path in SPONSOR_PATHS:
        assert path in endpoints
        assert all(
            endpoint.startswith("sponsor_routes.")
            for endpoint in endpoints[path]
        )
    for path in ASSET_PATHS:
        assert path in endpoints
        assert all(
            endpoint.startswith("asset_routes.")
            for endpoint in endpoints[path]
        )
    for path in LOGO_PATHS:
        assert path in endpoints
        assert all(
            endpoint.startswith("logo_routes.")
            for endpoint in endpoints[path]
        )


def test_app_collects_each_media_blueprint_once() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    for name in ("SPONSOR", "ASSET", "LOGO"):
        assert source.count(
            f"APPLICATION_BLUEPRINTS.append({name}_ROUTES_BLUEPRINT)"
        ) == 1


def test_migrated_media_route_decorators_are_removed_from_app() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    for marker in (
        '@app.get("/api/sponsors")',
        '@app.post("/api/sponsors")',
        '@app.post("/api/sponsors/<sponsor_id>/logo")',
        '@app.get("/sponsor-logos/<filename>")',
        '@app.get("/api/assets")',
        '@app.post("/api/assets/<asset_id>/upload")',
        '@app.get("/asset-files/<filename>")',
        '@app.get("/school-logos/<school_id>/<filename>")',
        '@app.post("/api/schools/<school_id>/logo/process")',
        '@app.get("/api/logos")',
    ):
        assert marker not in source


def test_media_route_modules_do_not_import_application_root() -> None:
    for filename in (
        "sponsor_routes.py",
        "asset_routes.py",
        "logo_routes.py",
    ):
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


