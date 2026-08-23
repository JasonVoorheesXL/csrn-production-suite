from __future__ import annotations

import ast
from pathlib import Path

import app as app_module


ROOT = Path(__file__).resolve().parents[1]
MIGRATED_PATHS = {
    "/api/game-day/preflight",
    "/api/game-day/snapshots",
    "/api/game-day/snapshots/<snapshot_id>/verify",
}


def test_game_day_safety_routes_are_blueprint_owned_and_protected() -> None:
    entries = [
        row
        for row in app_module.app.extensions["csrn_route_manifest"]
        if row["rule"] in MIGRATED_PATHS
    ]
    assert {row["rule"] for row in entries} == MIGRATED_PATHS
    assert all(row["blueprint"] == "game_day_safety_routes" for row in entries)
    assert all(row["auth_required"] is True for row in entries)


def test_app_constructs_and_collects_game_day_safety_blueprint_once() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert source.count("GAME_DAY_SAFETY_ROUTES_BLUEPRINT = ") == 1
    assert source.count("create_game_day_safety_blueprint(") == 1
    assert source.count(
        "APPLICATION_BLUEPRINTS.append(GAME_DAY_SAFETY_ROUTES_BLUEPRINT)"
    ) == 1
    assert source.count("def get_game_day_safety_service()") == 1


def test_game_day_safety_modules_do_not_import_application_root() -> None:
    for filename in (
        "game_day_safety_service.py",
        "routes/game_day_safety_routes.py",
    ):
        source = (ROOT / filename).read_text(encoding="utf-8")
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


def test_windows_launcher_runs_preflight_before_application() -> None:
    source = (ROOT / "RUN_CSRN_COMMAND_CENTER.bat").read_text(
        encoding="utf-8"
    )
    preflight = (
        '".venv\\Scripts\\python.exe" tools\\game_day_preflight.py'
    )
    startup = '".venv\\Scripts\\python.exe" app.py'
    assert source.count(preflight) == 1
    assert source.index(preflight) < source.index(startup)
    assert "Game-day preflight failed. The application was not started." in source


