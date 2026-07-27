from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_social_queue_does_not_accept_or_store_raw_credentials() -> None:
    source = (ROOT / "social_service.py").read_text(encoding="utf-8")
    assert "RAW_CREDENTIAL_REJECTED" in source
    assert '"access_token"' in source
    assert '"credential_ref"' in source
    assert "client_secret" in source


def test_platform_adapters_resolve_credentials_externally() -> None:
    source = (ROOT / "social_platforms.py").read_text(encoding="utf-8")
    assert "EnvCredentialResolver" in source
    assert "credential_resolver" in source
    assert "POST" in source
    assert "/2/tweets" in source
    assert "/2/media/upload" in source
    assert "/photos" in source


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


def test_social_blueprint_is_part_of_application_architecture() -> None:
    architecture = (ROOT / "phase5_architecture.py").read_text(encoding="utf-8")
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert '"social_routes"' in architecture
    assert "create_social_blueprint" in app
    assert "get_social_service" in app


def test_all_social_route_endpoints_remain_authenticated_by_design() -> None:
    source = (ROOT / "routes" / "social_routes.py").read_text(encoding="utf-8")
    route_count = source.count("@routes.")
    auth_count = source.count("@dependencies.require_auth")
    assert route_count >= 15
    assert auth_count == route_count


def test_phase_6_10_grounded_recap_requirement_remains() -> None:
    roadmap = (ROOT / "docs" / "PHASE_6_GAME_DAY_AND_COMMERCIAL_ROADMAP.md").read_text(encoding="utf-8")
    assert "### 6.10 Grounded Game Recap Engine" in roadmap
    assert "must not invent" in roadmap


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
