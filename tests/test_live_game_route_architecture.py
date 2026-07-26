from __future__ import annotations

import ast
from pathlib import Path

import app as app_module


ROOT = Path(__file__).resolve().parents[1]
MIGRATED_PATHS = {
    "/api/score",
    "/api/set",
    "/api/statistics",
    "/api/control-source",
    "/api/event-trigger",
    "/api/game-correction",
    "/api/events/<event_id>/edit",
    "/api/corrections",
    "/api/toggle-scorebug",
    "/api/toggle-halftime",
    "/api/end-game",
    "/api/reset-data",
    "/api/new-broadcast",
    "/api/clock-control",
    "/api/field-direction",
    "/api/rules-play",
    "/api/undo",
}


def test_live_game_routes_are_registered_through_blueprint() -> None:
    endpoint_by_path = {
        rule.rule: rule.endpoint
        for rule in app_module.app.url_map.iter_rules()
        if rule.rule in MIGRATED_PATHS
    }
    assert set(endpoint_by_path) == MIGRATED_PATHS
    assert all(
        endpoint.startswith("live_game_routes.")
        for endpoint in endpoint_by_path.values()
    )


def test_app_collects_live_game_blueprint_once() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert source.count("LIVE_GAME_ROUTES_BLUEPRINT = create_live_game_blueprint(") == 1
    assert source.count(
        "APPLICATION_BLUEPRINTS.append(LIVE_GAME_ROUTES_BLUEPRINT)"
    ) == 1


def test_migrated_live_game_decorators_are_removed_from_app() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    for path in MIGRATED_PATHS:
        assert f'@app.get("{path}")' not in source
        assert f'@app.post("{path}")' not in source


def test_live_game_route_module_does_not_import_application_root() -> None:
    source = (ROOT / "routes" / "live_game_routes.py").read_text(
        encoding="utf-8"
    )
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
