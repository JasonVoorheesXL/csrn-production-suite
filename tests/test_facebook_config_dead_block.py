"""Round 7 Task A: DEFAULT_CONFIG.social.publishing is dead config.

Traced definitively: the string "local_oauth_test" existed only in the
DEFAULT_CONFIG literal; nothing reads config["social"]["publishing"] at all.
Live Facebook behaviour is driven by facebook_connection.json
(FacebookConnectionService) and social_state.json (SocialService); the real
Graph API version default is FacebookConnectionService.DEFAULT_API_VERSION.
"""

from __future__ import annotations

from pathlib import Path

import app
from configuration_service import ConfigurationService
from facebook_connection_service import FacebookConnectionService

ROOT = Path(__file__).resolve().parents[1]


def test_local_oauth_test_sentinel_is_gone() -> None:
    src = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "local_oauth_test" not in src
    assert app.DEFAULT_CONFIG["social"]["publishing"]["facebook_connection"] == ""


def test_no_live_code_reads_publishing_facebook_connection() -> None:
    # Sweep the live modules that touch config or Facebook.
    for rel in (
        "social_service.py",
        "social_platforms.py",
        "facebook_connection_service.py",
        "configuration_service.py",
        "routes/social_routes.py",
    ):
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "publishing" not in text or "facebook_connection" not in text, rel
        assert "local_oauth_test" not in text, rel


def test_config_save_touching_social_drops_the_publishing_block() -> None:
    normalized, _errors = ConfigurationService.normalize_social_block(
        {"facebook": "", "youtube": "", "x": "", "website": ""}
    )
    assert "publishing" not in normalized


def test_real_graph_api_version_default_lives_in_the_facebook_service() -> None:
    assert FacebookConnectionService.DEFAULT_API_VERSION == "v25.0"
