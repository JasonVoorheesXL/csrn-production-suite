from __future__ import annotations

import ast
import re
from pathlib import Path

import app as app_module


ROOT = Path(__file__).resolve().parents[1]
MIGRATED_PATHS = {
    "/",
    "/overlay",
    "/roster-headshots/<filename>",
    "/api/rosters/<roster_id>/players/<player_id>/headshot",
    "/api/connection-info",
    "/api/connection-qr",
}


def test_support_and_page_routes_are_registered_through_blueprints() -> None:
    endpoint_by_path = {
        rule.rule: rule.endpoint
        for rule in app_module.app.url_map.iter_rules()
        if rule.rule in MIGRATED_PATHS
    }
    assert set(endpoint_by_path) == MIGRATED_PATHS
    assert endpoint_by_path["/"].startswith("page_routes.")
    assert endpoint_by_path["/overlay"].startswith("page_routes.")
    assert all(
        endpoint_by_path[path].startswith("support_routes.")
        for path in MIGRATED_PATHS - {"/", "/overlay"}
    )


def test_app_registers_support_and_page_blueprints_once() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert source.count("app.register_blueprint(PAGE_ROUTES_BLUEPRINT)") == 1
    assert source.count("app.register_blueprint(SUPPORT_ROUTES_BLUEPRINT)") == 1
    assert source.count("PAGE_ROUTES_BLUEPRINT = create_page_blueprint(") == 1
    assert source.count("SUPPORT_ROUTES_BLUEPRINT = create_support_blueprint(") == 1


def test_no_direct_flask_route_decorators_remain_in_app() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert not re.search(
        r"@app\.(?:get|post|put|patch|delete|route)\(",
        source,
    )


def test_support_and_page_route_modules_do_not_import_application_root() -> None:
    for filename in ("page_routes.py", "support_routes.py"):
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
