"""Round 12 Task A: the external Identity Profile seeds an existing install
with today's exact literals (zero behaviour change) and a fresh install blank.
"""

from __future__ import annotations

import json
from pathlib import Path

import identity_service

REPO_ROOT = Path(__file__).resolve().parents[1]


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
    # Round 23 quick-launch fields -- blank on the existing install, so the
    # "existing install sees no change" guarantee still holds (the launcher
    # only reads facebook_live / youtube_live).
    "broadcast_software_path": "",
    "youtube_url": "",
    "facebook_url": "",
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
    assert profile["streaming"] == {
        "facebook_live": "",
        "youtube_live": "",
        "broadcast_software_path": "",
        "youtube_url": "",
        "facebook_url": "",
    }
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


# A profile the test writes itself. Every value differs from the historical
# seed (asserted below, so the test cannot pass vacuously), every section key is
# present so the loaded result is exactly this document, and `logo` is an extra
# organization key like the ones a customised install carries.
FIXTURE_PROFILE = {
    "organization": {
        "name": "Delta Valley Network",
        "short_name": "DVN",
        "logo_path": "static/dvn-logo.png",
        "primary_color": "#123456",
        "secondary_color": "#0A0B0C",
        "accent_color": "#FEDCBA",
        "logo": "branding/dvn-wide.png",
    },
    "broadcast_defaults": {
        "venue": "Delta Field",
        "sport": "Football",
        "timezone": "America/Denver",
        "theme": "DVN Light",
        "home_school_id": "delta-valley",
        "visual_mode": "camera",
    },
    "streaming": {
        "facebook_live": "https://fb.example/dvn",
        "youtube_live": "https://yt.example/dvn",
        "broadcast_software_path": "D:\\obs\\obs64.exe",
        "youtube_url": "https://yt.example/studio",
        "facebook_url": "https://fb.example/producer",
    },
    "state_defaults": {"home_team": "Delta Valley", "venue": "Delta Field"},
    "onboarding_complete": True,
}

# What `import app` produces from the profile, printed by a fresh interpreter.
_CHILD = """
import json
import app
print("REPORT:" + json.dumps({
    "identity_file": str(app.IDENTITY_FILE),
    "organization": app.DEFAULT_CONFIG["organization"],
    "broadcast_defaults": app.DEFAULT_CONFIG["broadcast_defaults"],
    "streaming": app.DEFAULT_CONFIG["streaming"],
    "state_defaults_in_config": "state_defaults" in app.DEFAULT_CONFIG,
    "state_home_team": app.DEFAULT_STATE["home_team"],
    "state_venue": app.DEFAULT_STATE["venue"],
    "resolved": app.load_config(),
}))
"""


def _import_app_against(tmp_path, profile_file: Path) -> dict:
    """Import ``app`` in a fresh interpreter whose whole runtime root is under
    ``tmp_path`` and whose identity profile is ``profile_file``.

    app.py builds IDENTITY_PROFILE, DEFAULT_CONFIG and DEFAULT_STATE once, at
    import time, from the profile file -- so the only honest way to test that
    sourcing against a chosen profile is a new interpreter. Nothing here can
    read or write the real identity profile, state, config or state-authority
    file, whatever they contain.
    """
    import os
    import subprocess
    import sys

    root = tmp_path / "runtime"
    (root / "Data").mkdir(parents=True)
    (root / "state.json").write_text("{}", encoding="utf-8")  # => an existing install
    (root / "identity_profile.json").write_bytes(profile_file.read_bytes())
    env = {
        **os.environ,
        "CSRN_RUNTIME_ROOT": str(root),
        "CSRN_DATA_ROOT": str(root / "Data"),
        "CSRN_GAME_DAY_LOCAL_STATE": "1",
        "CSRN_STATE_AUTHORITY_FILE": str(root / "authority-state.json"),
        "CSRN_PRODUCTION_TEMPLATE_STATE_PATH": str(root / "template.json"),
        "LOCALAPPDATA": str(tmp_path / "localappdata"),
        "PYTHONPATH": str(REPO_ROOT),
    }
    done = subprocess.run(
        [sys.executable, "-c", _CHILD], cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=180
    )
    lines = [ln for ln in done.stdout.splitlines() if ln.startswith("REPORT:")]
    assert done.returncode == 0 and lines, f"child failed ({done.returncode}):\n{done.stderr[-2000:]}"
    report = json.loads(lines[-1][len("REPORT:"):])
    # it read the scratch copy, never the real file
    assert Path(report["identity_file"]) == (root / "identity_profile.json").resolve()
    return report


def test_app_default_config_is_sourced_from_the_identity_profile(tmp_path) -> None:
    """DEFAULT_CONFIG / DEFAULT_STATE come from the identity profile *file*, not
    from inline literals -- verified against a profile this test writes, so it
    holds whatever is in the real, user-specific, gitignored identity_profile.json
    (a customised install used to fail the version of this test that asserted the
    stock Caledonia palette)."""
    # The fixture must be unmistakably not the historical seed, or a regression to
    # inline literals would still pass.
    assert FIXTURE_PROFILE["organization"]["primary_color"] != HISTORICAL_ORGANIZATION["primary_color"]
    assert FIXTURE_PROFILE["organization"]["name"] != HISTORICAL_ORGANIZATION["name"]
    assert FIXTURE_PROFILE["broadcast_defaults"] != HISTORICAL_BROADCAST_DEFAULTS
    assert FIXTURE_PROFILE["streaming"] != HISTORICAL_STREAMING
    assert FIXTURE_PROFILE["state_defaults"] != HISTORICAL_STATE_DEFAULTS

    profile_file = tmp_path / "fixture_identity_profile.json"
    profile_file.write_text(json.dumps(FIXTURE_PROFILE, indent=2), encoding="utf-8")

    report = _import_app_against(tmp_path, profile_file)

    assert report["organization"] == FIXTURE_PROFILE["organization"]  # incl. the extra `logo` key
    assert report["broadcast_defaults"] == FIXTURE_PROFILE["broadcast_defaults"]
    # Round 23: streaming is in DEFAULT_CONFIG (Configuration Manager edits it);
    # state_defaults feed DEFAULT_STATE and are deliberately not a config section.
    assert report["streaming"] == FIXTURE_PROFILE["streaming"]
    assert report["state_defaults_in_config"] is False
    # Round 13: DEFAULT_STATE placeholders come from the profile.
    assert report["state_home_team"] == FIXTURE_PROFILE["state_defaults"]["home_team"]
    assert report["state_venue"] == FIXTURE_PROFILE["state_defaults"]["venue"]
    # load_config() on a fresh install root (no saved config.json) resolves the
    # profile's identity, not a built-in one.
    resolved = report["resolved"]
    assert resolved["organization"]["name"] == FIXTURE_PROFILE["organization"]["name"]
    assert resolved["broadcast_defaults"]["home_school_id"] == FIXTURE_PROFILE["broadcast_defaults"]["home_school_id"]


def test_app_default_config_follows_whatever_profile_is_installed(tmp_path) -> None:
    """The same sourcing guarantee for the profile actually installed here --
    stock, customised, or absent -- with expectations read from the file itself
    rather than hard-coded. Works on a *copy*, so the live file is never touched;
    if there is none (a fresh clone), the seed for an existing install is used."""
    installed = REPO_ROOT / "identity_profile.json"
    copy = tmp_path / "installed_identity_profile_copy.json"
    if installed.exists():
        copy.write_bytes(installed.read_bytes())
    else:
        identity_service.load_identity_profile(copy, existing_install=True)  # seeds the file

    expected = identity_service.load_identity_profile(copy, existing_install=True)
    report = _import_app_against(tmp_path, copy)

    assert report["organization"] == expected["organization"]
    assert report["broadcast_defaults"] == expected["broadcast_defaults"]
    assert report["streaming"] == expected["streaming"]
    assert report["state_defaults_in_config"] is False
    assert report["state_home_team"] == expected["state_defaults"]["home_team"]
    assert report["state_venue"] == expected["state_defaults"]["venue"]


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
