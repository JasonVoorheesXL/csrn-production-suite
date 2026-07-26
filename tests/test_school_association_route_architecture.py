from __future__ import annotations

import ast
from pathlib import Path

import app as app_module


ROOT = Path(__file__).resolve().parents[1]
SCHOOL_PATHS = {
    "/api/schools",
    "/api/schools/<school_id>",
    "/api/schools/duplicate-check",
}
ASSOCIATION_PATHS = {
    "/api/imports/associations/profiles",
    "/api/imports/associations/profiles/<profile_id>",
    "/api/imports/associations/preview",
    "/api/imports/associations/import",
    "/api/imports/mhsaa/5A/analyze",
    "/api/imports/mhsaa/5A",
    "/api/imports/mhsaa/5A/branding/analyze",
    "/api/imports/mhsaa/5A/branding",
    "/api/imports/mhsaa/5A/enrichment/analyze",
    "/api/imports/mhsaa/5A/enrichment",
}


def test_school_and_association_routes_are_blueprint_owned() -> None:
    endpoint_by_path: dict[str, set[str]] = {}
    for rule in app_module.app.url_map.iter_rules():
        if rule.rule in SCHOOL_PATHS | ASSOCIATION_PATHS:
            endpoint_by_path.setdefault(rule.rule, set()).add(rule.endpoint)

    assert set(endpoint_by_path) == SCHOOL_PATHS | ASSOCIATION_PATHS
    for path in SCHOOL_PATHS:
        assert all(
            endpoint.startswith("school_routes.")
            for endpoint in endpoint_by_path[path]
        )
    for path in ASSOCIATION_PATHS:
        assert all(
            endpoint.startswith("association_routes.")
            for endpoint in endpoint_by_path[path]
        )


def test_app_collects_each_phase_5_3_blueprint_once() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert source.count(
        "APPLICATION_BLUEPRINTS.append(SCHOOL_ROUTES_BLUEPRINT)"
    ) == 1
    assert source.count(
        "APPLICATION_BLUEPRINTS.append(ASSOCIATION_ROUTES_BLUEPRINT)"
    ) == 1
    assert source.count("SCHOOL_ROUTES_BLUEPRINT = create_school_blueprint(") == 1
    assert source.count(
        "ASSOCIATION_ROUTES_BLUEPRINT = create_association_blueprint("
    ) == 1


def test_migrated_route_decorators_and_helpers_are_removed_from_app() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    markers = (
        '@app.get("/api/schools")',
        '@app.get("/api/schools/<school_id>")',
        '@app.post("/api/schools")',
        '@app.put("/api/schools/<school_id>")',
        '@app.delete("/api/schools/<school_id>")',
        '@app.post("/api/schools/duplicate-check")',
        '@app.get("/api/imports/associations/profiles")',
        '@app.post("/api/imports/associations/preview")',
        '@app.post("/api/imports/associations/import")',
        '@app.get("/api/imports/mhsaa/5A/analyze")',
        '@app.post("/api/imports/mhsaa/5A")',
        "def _association_error_status(",
        "def _association_request_payload(",
        "def _resolve_association_profile(",
    )
    for marker in markers:
        assert marker not in source


def test_phase_5_3_route_modules_do_not_import_application_root() -> None:
    for filename in ("school_routes.py", "association_routes.py"):
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
