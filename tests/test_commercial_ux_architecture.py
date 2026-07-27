from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_setup_hub_contains_visible_return_and_feature_navigation() -> None:
    source = (ROOT / "templates" / "setup_hub.html").read_text(encoding="utf-8")
    assert "Back to Command Center" in source
    assert "All product areas" in source
    for feature in ("Graphics appearance", "Social accounts", "Audio & captions", "Venue weather", "Recovery & backups", "Licensing & updates"):
        assert feature in source


def test_command_center_exposes_setup_and_integrations() -> None:
    source = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    assert "Setup &amp; Integrations" in source
    assert "window.location.href='/setup'" in source
    assert "Advanced Settings" in source


def test_known_theme_choices_use_a_selector_not_free_text() -> None:
    source = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    assert '<label>Theme<select id="cfgTheme">' in source
    assert '<label>Theme<input id="cfgTheme">' not in source
    for preset_id in ("classic_1980s", "modern_network", "minimal_radio", "friday_night_stadium", "collegiate_traditional"):
        assert preset_id in source


def test_theme_and_social_pages_have_return_navigation() -> None:
    themes = (ROOT / "templates" / "theme_manager.html").read_text(encoding="utf-8")
    social = (ROOT / "templates" / "social_manager.html").read_text(encoding="utf-8")
    for source in (themes, social):
        assert "Back to Command Center" in source
        assert "Setup &amp; Integrations" in source


def test_customer_oauth_screen_does_not_expose_raw_token_or_secret_fields() -> None:
    source = (ROOT / "templates" / "setup_hub.html").read_text(encoding="utf-8")
    forbidden = ("access_token", "refresh_token", "client_secret", "app_secret", "credentialRef", "environment reference")
    for value in forbidden:
        assert value not in source
    assert "Connect ${escapeHtml(provider.label)}" in source


def test_oauth_tokens_are_protected_outside_social_queue_state() -> None:
    vault = (ROOT / "credential_vault.py").read_text(encoding="utf-8")
    oauth = (ROOT / "oauth_onboarding_service.py").read_text(encoding="utf-8")
    assert "CryptProtectData" in vault
    assert "CryptUnprotectData" in vault
    assert "vault:" in oauth
    assert '"access_token"' in oauth
    assert "access-secret" not in oauth


def test_x_pkce_and_facebook_broker_boundaries_are_explicit() -> None:
    source = (ROOT / "oauth_onboarding_service.py").read_text(encoding="utf-8")
    assert "code_challenge_method" in source
    assert '"S256"' in source
    assert "offline.access" in source
    assert "media.write" in source
    assert "CSRN_META_OAUTH_BROKER_URL" in source
    assert "Meta application secrets are never distributed" in source


def test_commercial_ux_blueprint_is_in_architecture_audit() -> None:
    source = (ROOT / "phase5_architecture.py").read_text(encoding="utf-8")
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert '"commercial_ux_routes"' in source
    assert "create_commercial_ux_blueprint" in app
    assert "get_commercial_ux_service" in app


def test_runtime_identity_is_phase_6_10() -> None:
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "Version 1.13.0-alpha.6j — Commercial UX and Account Onboarding" in app
    assert "V1.13A6J-COMMERCIAL-UX-ACCOUNT-ONBOARDING" in app
    assert (ROOT / "VERSION.txt").read_text(encoding="utf-8").strip() == "1.13.0-alpha.6j"


def test_grounded_recap_remains_next_stage() -> None:
    roadmap = (ROOT / "docs" / "PHASE_6_GAME_DAY_AND_COMMERCIAL_ROADMAP.md").read_text(encoding="utf-8")
    assert "### 6.10 Commercial UX, Navigation, and Account Onboarding" in roadmap
    assert "### 6.11 Grounded Game Recap Engine" in roadmap
    assert "must not invent" in roadmap
