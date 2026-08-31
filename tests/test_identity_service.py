"""Round 12 Task A: the external Identity Profile seeds an existing install
with today's exact literals (zero behaviour change) and a fresh install blank.
"""

from __future__ import annotations

import json

import identity_service


# The historical literals, frozen here. If app.py's former DEFAULT_CONFIG
# values ever need to change, this golden copy must change with them and the
# "existing install sees no change" guarantee must be re-verified.
HISTORICAL_ORGANIZATION = {
    "name": "Caledonia Sports Radio Network",
    "short_name": "CSRN",
    "logo_path": "static/csrn-logo.png",
    "primary_color": "#C9203B",
    "secondary_color": "#000000",
    "accent_color": "#FFFFFF",
}
HISTORICAL_BROADCAST_DEFAULTS = {
    "venue": "Caledonia High School",
    "sport": "Football",
    "timezone": "America/Chicago",
    "theme": "CSRN Dark",
    "home_school_id": "caledonia",
    "visual_mode": "graphic",
}
HISTORICAL_STREAMING = {
    "facebook_live": (
        "https://www.facebook.com/live/producer/v2/?target_id=100075470576573"
    ),
    "youtube_live": (
        "https://studio.youtube.com/channel/"
        "UCAZZRMpb3HnrSxCnDiQeH7Q/livestreaming"
    ),
}
# Round 13 Task A: former DEFAULT_STATE placeholder team/venue.
HISTORICAL_STATE_DEFAULTS = {
    "home_team": "Caledonia",
    "venue": "Caledonia High School",
}


def test_legacy_seed_matches_the_historical_literals_exactly() -> None:
    assert identity_service.LEGACY_ORGANIZATION == HISTORICAL_ORGANIZATION
    assert identity_service.LEGACY_BROADCAST_DEFAULTS == HISTORICAL_BROADCAST_DEFAULTS
    assert identity_service.LEGACY_STREAMING == HISTORICAL_STREAMING
    assert identity_service.LEGACY_STATE_DEFAULTS == HISTORICAL_STATE_DEFAULTS


def test_branding_logo_never_falls_back_to_csrn_logo() -> None:
    assert identity_service.branding_logo(
        identity_service.LEGACY_ORGANIZATION
    ) == "static/csrn-logo.png"
    assert identity_service.branding_logo(identity_service.BLANK_ORGANIZATION) == ""
    assert identity_service.branding_logo({"logo": "branding/net.png"}) == "branding/net.png"
    assert identity_service.branding_logo({}) == ""
    assert identity_service.branding_logo(None) == ""


def test_existing_install_seeds_with_todays_exact_values(tmp_path) -> None:
    identity_file = tmp_path / "identity_profile.json"
    assert not identity_file.exists()

    profile = identity_service.load_identity_profile(
        identity_file, existing_install=True
    )

    assert identity_file.exists()
    on_disk = json.loads(identity_file.read_text(encoding="utf-8"))
    assert profile == on_disk
    assert profile["organization"] == HISTORICAL_ORGANIZATION
    assert profile["broadcast_defaults"] == HISTORICAL_BROADCAST_DEFAULTS
    assert profile["streaming"] == HISTORICAL_STREAMING
    assert profile["state_defaults"] == HISTORICAL_STATE_DEFAULTS


def test_fresh_install_seeds_blank_identity_not_caledonia(tmp_path) -> None:
    identity_file = tmp_path / "identity_profile.json"

    profile = identity_service.load_identity_profile(
        identity_file, existing_install=False
    )

    assert identity_file.exists()
    assert profile["organization"]["name"] == ""
    assert profile["organization"]["short_name"] == ""
    assert profile["organization"]["logo_path"] == ""
    assert profile["broadcast_defaults"]["venue"] == ""
    assert profile["broadcast_defaults"]["home_school_id"] == ""
    # a sport default is still fine on a blank template
    assert profile["broadcast_defaults"]["sport"] == "Football"
    assert profile["streaming"] == {"facebook_live": "", "youtube_live": ""}
    assert profile["state_defaults"] == {"home_team": "", "venue": ""}
    # nothing Caledonia-identifying and no csrn-logo fallback leaked in
    blob = json.dumps(profile).lower()
    assert "caledonia" not in blob
    assert "csrn-logo" not in blob


def test_existing_profile_file_is_loaded_and_normalized(tmp_path) -> None:
    identity_file = tmp_path / "identity_profile.json"
    identity_file.write_text(
        json.dumps(
            {
                "organization": {"name": "Delta Valley Network", "short_name": "DVN"},
                "broadcast_defaults": {"home_school_id": "delta-valley"},
                "streaming": {"facebook_live": "https://fb.example/dvn"},
                "junk_section": {"ignored": True},
            }
        ),
        encoding="utf-8",
    )

    profile = identity_service.load_identity_profile(
        identity_file, existing_install=True
    )

    assert profile["organization"]["name"] == "Delta Valley Network"
    # missing keys fall back to the template, unknown sections are dropped
    assert profile["organization"]["primary_color"] == "#C9203B"
    assert profile["broadcast_defaults"]["home_school_id"] == "delta-valley"
    assert profile["streaming"]["facebook_live"] == "https://fb.example/dvn"
    # a key omitted from an existing-install profile falls back to the seed
    assert profile["streaming"]["youtube_live"] == identity_service.LEGACY_STREAMING["youtube_live"]
    assert "junk_section" not in profile


def test_app_default_config_is_sourced_from_the_identity_profile() -> None:
    import app

    # This checkout is an existing install (config.json / state.json present),
    # so DEFAULT_CONFIG must still carry exactly the former inline literals and
    # load_config() must still resolve the Caledonia identity unchanged.
    assert app.DEFAULT_CONFIG["organization"] == HISTORICAL_ORGANIZATION
    assert app.DEFAULT_CONFIG["broadcast_defaults"] == HISTORICAL_BROADCAST_DEFAULTS
    assert "streaming" not in app.DEFAULT_CONFIG
    assert "state_defaults" not in app.DEFAULT_CONFIG
    resolved = app.load_config()
    assert resolved["organization"]["name"] == "Caledonia Sports Radio Network"
    assert resolved["broadcast_defaults"]["home_school_id"] == "caledonia"
    # Round 13: DEFAULT_STATE placeholders now come from the profile, unchanged.
    assert app.DEFAULT_STATE["home_team"] == "Caledonia"
    assert app.DEFAULT_STATE["venue"] == "Caledonia High School"


def test_launcher_streaming_links_endpoint_is_public_and_serves_the_profile() -> None:
    import app

    # existing install -> seeded with the launcher's former hard-coded URLs
    assert app.identity_streaming_links() == {
        "facebook_live": HISTORICAL_STREAMING["facebook_live"],
        "youtube_live": HISTORICAL_STREAMING["youtube_live"],
    }

    app.app.config["TESTING"] = True
    with app.app.test_client() as client:
        response = client.get("/api/identity/streaming-links")  # no auth session
    assert response.status_code == 200
    body = response.get_json()
    assert body == {
        "facebook_live": HISTORICAL_STREAMING["facebook_live"],
        "youtube_live": HISTORICAL_STREAMING["youtube_live"],
    }


def test_launcher_script_no_longer_hardcodes_only_and_reads_the_endpoint() -> None:
    from pathlib import Path

    script = Path(__file__).resolve().parents[1] / "CSRN_GAME_DAY_LAUNCHER.ps1"
    text = script.read_text(encoding="utf-8")
    assert "/api/identity/streaming-links" in text
    # the former literals remain only as the documented fallback
    assert "target_id=100075470576573" in text
    assert 'if ($streamLinks.facebook_live)' in text


def test_save_identity_profile_round_trips(tmp_path) -> None:
    identity_file = tmp_path / "identity_profile.json"
    identity_service.load_identity_profile(identity_file, existing_install=True)

    saved = identity_service.save_identity_profile(
        identity_file,
        {
            "organization": {"name": "New Network", "short_name": "NN"},
            "broadcast_defaults": {"venue": "New Stadium"},
        },
    )
    reloaded = identity_service.load_identity_profile(
        identity_file, existing_install=True
    )
    assert reloaded == saved
    assert reloaded["organization"]["name"] == "New Network"
    assert reloaded["broadcast_defaults"]["venue"] == "New Stadium"
