from __future__ import annotations

import ast
from pathlib import Path

import app as app_module


ROOT = Path(__file__).resolve().parents[1]
SOCIAL_PATHS = {
    "/api/social/status",
    "/api/social/posts",
    "/api/social/posts/event",
    "/api/social/posts/<post_id>",
    "/api/social/posts/<post_id>/publish",
    "/api/social/posts/<post_id>/retry",
    "/api/social/posts/<post_id>/cancel",
    "/social-cards/<filename>",
}


def test_social_routes_are_blueprint_owned_and_authenticated() -> None:
    entries = {
        item["rule"]: item
        for item in app_module.app.extensions["csrn_route_manifest"]
        if item["rule"] in SOCIAL_PATHS
    }
    assert set(entries) == SOCIAL_PATHS
    assert all(item["blueprint"] == "social_routes" for item in entries.values())
    assert all(item["auth_required"] is True for item in entries.values())


def test_social_blueprint_and_service_are_registered_once() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    assert source.count("SOCIAL_ROUTES_BLUEPRINT = create_social_blueprint(") == 1
    assert source.count("APPLICATION_BLUEPRINTS.append(SOCIAL_ROUTES_BLUEPRINT)") == 1
    assert source.count("def get_social_publishing_service()") == 1
    assert source.count("SOCIAL_POST_REPOSITORY = SocialPostRepository(") == 1


def test_social_modules_do_not_import_application_root() -> None:
    for filename in (
        "social_card_renderer.py",
        "social_post_repository.py",
        "social_publishers.py",
        "social_publishing_service.py",
        "routes/social_routes.py",
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


def test_social_credentials_are_environment_boundaries() -> None:
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    environment_names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        function = node.func
        if not (
            isinstance(function, ast.Attribute)
            and function.attr == "get"
            and isinstance(function.value, ast.Attribute)
            and function.value.attr == "environ"
            and isinstance(function.value.value, ast.Name)
            and function.value.value.id == "os"
        ):
            continue
        first = node.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            environment_names.add(first.value)

    assert {
        "CSRN_X_USER_ACCESS_TOKEN",
        "CSRN_FACEBOOK_PAGE_ID",
        "CSRN_FACEBOOK_PAGE_ACCESS_TOKEN",
    }.issubset(environment_names)
    assert "CSRN_X_USER_ACCESS_TOKEN=" not in source
    assert "CSRN_FACEBOOK_PAGE_ACCESS_TOKEN=" not in source
