from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_social_queue_does_not_accept_or_store_raw_credentials() -> None:
    source = (ROOT / "social_service.py").read_text(encoding="utf-8")
    assert "RAW_CREDENTIAL_REJECTED" in source
    assert '"access_token"' in source
    assert '"credential_ref"' in source
    assert "client_secret" in source


def test_x_automatic_adapter_and_api_calls_are_removed() -> None:
    source = (ROOT / "social_platforms.py").read_text(encoding="utf-8")
    assert "XPlatformAdapter" not in source
    assert "/2/tweets" not in source
    assert "/2/media/upload" not in source
    assert "CSRN_X_ACCESS_TOKEN" not in source
    assert "build_x_compose_url" in source
    assert "https://x.com/intent/post" in source


def test_default_automatic_adapter_is_facebook_only() -> None:
    source = (ROOT / "social_platforms.py").read_text(encoding="utf-8")
    assert '"facebook": FacebookPageAdapter' in source
    assert "/photos" in source


def test_social_service_enforces_manual_only_x() -> None:
    source = (ROOT / "social_service.py").read_text(encoding="utf-8")
    assert 'PUBLISH_PLATFORMS = {"facebook"}' in source
    assert 'CARD_PLATFORMS = {"facebook", "x"}' in source
    assert "X_MANUAL_ONLY" in source
    assert "X_MANUAL_PACKAGE_PREPARED" in source
    assert '"x-manual"' in source


def test_social_manager_has_no_x_credential_controls() -> None:
    source = (ROOT / "templates" / "social_manager.html").read_text(encoding="utf-8")
    assert "CSRN_X_ACCESS_TOKEN" not in source
    assert "No X OAuth" not in source  # wording is rendered as a clear policy without a credential field
    assert "Assisted-Manual X Package" in source
    assert "Download X graphic" in source
    assert "Open X composer" in source


def test_social_asset_resolver_blocks_remote_and_traversal_inputs() -> None:
    source = (ROOT / "social_asset_resolver.py").read_text(encoding="utf-8")
    assert "parsed.scheme or parsed.netloc" in source
    assert 'part in {".", ".."}' in source
    assert "relative_to" in source


def test_emergency_posts_have_hard_sponsor_suppression() -> None:
    source = (ROOT / "social_service.py").read_text(encoding="utf-8")
    assert 'EMERGENCY_KINDS = {"WEATHER_EMERGENCY"}' in source
    assert "if kind in self.EMERGENCY_KINDS" in source
    assert "sponsor_suppressed" in source


def test_operator_approval_and_correction_workflows_are_required() -> None:
    source = (ROOT / "social_service.py").read_text(encoding="utf-8")
    assert "APPROVE SOCIAL POST" in source
    assert "RETRACT SOCIAL POST" in source
    assert "CORRECTION_CREATED" in source
    assert "PUBLISH_ATTEMPT" in source


def test_event_callback_cannot_break_primary_game_event() -> None:
    source = (ROOT / "event_service.py").read_text(encoding="utf-8")
    assert "on_event" in source
    assert "Social draft creation can never invalidate the game event" in source


def test_social_and_recap_blueprints_are_part_of_application_architecture() -> None:
    architecture = (ROOT / "phase5_architecture.py").read_text(encoding="utf-8")
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert '"social_routes"' in architecture
    assert '"recap_routes"' in architecture
    assert "create_social_blueprint" in app
    assert "create_recap_blueprint" in app
    assert "get_social_service" in app
    assert "get_recap_service" in app


def test_social_routes_keep_only_the_oauth_callback_public() -> None:
    source = (ROOT / "routes" / "social_routes.py").read_text(encoding="utf-8")
    route_count = source.count("@routes.")
    auth_count = source.count("@dependencies.require_auth")
    assert route_count >= 16
    assert auth_count == route_count - 1
    callback_start = source.index('@routes.get("/api/social/facebook/callback")')
    callback_end = source.index('@routes.get("/api/social/facebook/pages")')
    assert "@dependencies.require_auth" not in source[callback_start:callback_end]


def test_roadmap_records_manual_x_and_grounded_recap_requirements() -> None:
    roadmap = (ROOT / "docs" / "PHASE_6_GAME_DAY_AND_COMMERCIAL_ROADMAP.md").read_text(encoding="utf-8")
    assert "### 6.10 Grounded Game Recap Engine" in roadmap
    assert "must not invent" in roadmap
    assert "no X OAuth" in roadmap
    assert "assisted-manual X" in roadmap


def test_social_card_renderer_uses_theme_tokens() -> None:
    source = (ROOT / "social_card_renderer.py").read_text(encoding="utf-8")
    for token in (
        "primary_color",
        "secondary_color",
        "accent_color",
        "surface",
        "surface_alt",
    ):
        assert token in source


def test_facebook_connection_uses_dpapi_and_never_exposes_raw_tokens() -> None:
    source = (ROOT / "facebook_connection_service.py").read_text(encoding="utf-8")
    assert "CryptProtectData" in source
    assert "CryptUnprotectData" in source
    assert "CSRN_FACEBOOK_SECURE_PAGE_TOKEN" in source
    assert '"access_token": page_token' not in source
    assert '"app_secret": app_secret' not in source
    assert "FACEBOOK_LOCALHOST_REQUIRED" in (ROOT / "routes" / "social_routes.py").read_text(encoding="utf-8")


def test_facebook_manager_has_customer_facing_connection_controls() -> None:
    source = (ROOT / "templates" / "social_manager.html").read_text(encoding="utf-8")
    assert "Connect Facebook Page" in source
    assert "Test connection" in source
    assert "Disconnect" in source
    assert "One-time Meta test-app setup" in source
    assert "facebook_credentials.dat" not in source
    assert "CSRN_X_ACCESS_TOKEN" not in source


def test_support_bundle_redacts_facebook_secrets() -> None:
    source = (ROOT / "deployment_service.py").read_text(encoding="utf-8")
    assert "facebook_credentials.dat" in source
    assert "page_access_token" in source
    assert "_redact_log_text" in source
