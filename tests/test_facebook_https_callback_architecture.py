from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_public_callback_uses_server_side_state_and_returns_local_selection():
    routes = (ROOT / "routes" / "social_routes.py").read_text(encoding="utf-8")
    callback_start = routes.index('@routes.get("/api/social/facebook/callback")')
    callback_end = routes.index('@routes.get("/api/social/facebook/pages")')
    callback = routes[callback_start:callback_end]
    assert "@dependencies.require_auth" not in callback
    assert "localhost_required()" not in callback
    assert "expected_state=" not in callback
    assert "http://127.0.0.1:5050/social?" in callback
    assert '"selection_id": result.data["selection_id"]' in callback
    assert "session[" not in routes


def test_meta_setup_requires_https_callback_and_ui_does_not_restore_http_loopback():
    service = (ROOT / "facebook_connection_service.py").read_text(encoding="utf-8")
    html = (ROOT / "templates" / "social_manager.html").read_text(encoding="utf-8")
    assert 'parsed.scheme.lower() == "https"' in service
    assert 'CALLBACK_PATH = "/api/social/facebook/callback"' in service
    assert "http://127.0.0.1:5050/api/social/facebook/callback" not in service
    assert 'id="metaRedirectUri" readonly' not in html
    assert "https://temporary-host.example/api/social/facebook/callback" in html
    assert "selection_id:facebookSelectionId" in html
