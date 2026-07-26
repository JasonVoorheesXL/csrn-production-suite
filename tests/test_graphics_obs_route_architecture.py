from __future__ import annotations

import ast
from pathlib import Path

import app as app_module


ROOT = Path(__file__).resolve().parents[1]
MIGRATED_PATHS = {
    "/api/obs/status",
    "/api/obs/test",
    "/api/obs/scorebug-visibility",
    "/api/obs/program-visual-mode",
    "/api/graphics/lower-third",
    "/api/graphics/player",
    "/api/graphics/personnel",
}


def test_graphics_and_obs_routes_are_registered_through_blueprints() -> None:
    endpoint_by_path = {
        rule.rule: rule.endpoint
        for rule in app_module.app.url_map.iter_rules()
        if rule.rule in MIGRATED_PATHS
    }
    assert set(endpoint_by_path) == MIGRATED_PATHS
    assert endpoint_by_path["/api/obs/status"].startswith("obs_routes.")
    assert endpoint_by_path["/api/graphics/lower-third"].startswith(
        "graphics_routes."
    )
    assert all(
        endpoint.startswith(("obs_routes.", "graphics_routes."))
        for endpoint in endpoint_by_path.values()
    )


def test_app_registers_graphics_and_obs_blueprints_once() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert source.count("app.register_blueprint(OBS_ROUTES_BLUEPRINT)") == 1
    assert source.count("app.register_blueprint(GRAPHICS_ROUTES_BLUEPRINT)") == 1
    assert source.count("OBS_ROUTES_BLUEPRINT = create_obs_blueprint(") == 1
    assert source.count("GRAPHICS_ROUTES_BLUEPRINT = create_graphics_blueprint(") == 1


def test_migrated_graphics_and_obs_decorators_are_removed_from_app() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    for marker in (
        '@app.get("/api/obs/status")',
        '@app.post("/api/obs/test")',
        '@app.post("/api/obs/scorebug-visibility")',
        '@app.post("/api/obs/program-visual-mode")',
        '@app.post("/api/graphics/lower-third")',
        '@app.post("/api/graphics/player")',
        '@app.post("/api/graphics/personnel")',
    ):
        assert marker not in source


def test_graphics_and_obs_route_modules_do_not_import_application_root() -> None:
    for filename in ("graphics_routes.py", "obs_routes.py"):
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
        assert "app" not in imported_roots, filename
