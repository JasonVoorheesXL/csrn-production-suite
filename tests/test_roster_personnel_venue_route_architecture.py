from __future__ import annotations

import ast
from pathlib import Path

import app as app_module


ROOT = Path(__file__).resolve().parents[1]
MIGRATED_PATHS = {
    "/api/broadcasters",
    "/api/broadcasters/<broadcaster_id>",
    "/personnel-headshots/<filename>",
    "/api/personnel/<personnel_id>/headshot",
    "/api/validate-social",
    "/api/rosters",
    "/api/rosters/<roster_id>",
    "/api/rosters/<roster_id>/players",
    "/api/rosters/<roster_id>/players/<player_id>",
    "/api/rosters/<roster_id>/players/import",
    "/api/venues",
    "/api/venues/<venue_id>",
}


def test_migrated_routes_are_registered_through_expected_blueprints() -> None:
    endpoints = {
        rule.rule: rule.endpoint
        for rule in app_module.app.url_map.iter_rules()
        if rule.rule in MIGRATED_PATHS
    }
    assert set(endpoints) == MIGRATED_PATHS
    expected_prefixes = {
        "/api/broadcasters": "personnel_routes.",
        "/api/broadcasters/<broadcaster_id>": "personnel_routes.",
        "/personnel-headshots/<filename>": "personnel_routes.",
        "/api/personnel/<personnel_id>/headshot": "personnel_routes.",
        "/api/validate-social": "personnel_routes.",
        "/api/rosters": "roster_routes.",
        "/api/rosters/<roster_id>": "roster_routes.",
        "/api/rosters/<roster_id>/players": "roster_routes.",
        "/api/rosters/<roster_id>/players/<player_id>": "roster_routes.",
        "/api/rosters/<roster_id>/players/import": "roster_routes.",
        "/api/venues": "venue_routes.",
        "/api/venues/<venue_id>": "venue_routes.",
    }
    assert all(
        endpoints[path].startswith(prefix)
        for path, prefix in expected_prefixes.items()
    )


def test_app_collects_each_phase_5_4_blueprint_once() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    for name in (
        "PERSONNEL_ROUTES_BLUEPRINT",
        "ROSTER_ROUTES_BLUEPRINT",
        "VENUE_ROUTES_BLUEPRINT",
    ):
        assert source.count(f"APPLICATION_BLUEPRINTS.append({name})") == 1


def test_migrated_route_decorators_are_removed_from_app() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    for marker in (
        '@app.get("/api/broadcasters")',
        '@app.post("/api/broadcasters")',
        '@app.get("/personnel-headshots/<filename>")',
        '@app.post("/api/personnel/<personnel_id>/headshot")',
        '@app.post("/api/validate-social")',
        '@app.get("/api/rosters")',
        '@app.post("/api/rosters")',
        '@app.get("/api/venues")',
        '@app.post("/api/venues")',
    ):
        assert marker not in source


def test_phase_5_4_route_modules_do_not_import_application_root() -> None:
    for filename in (
        "personnel_routes.py",
        "roster_routes.py",
        "venue_routes.py",
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


