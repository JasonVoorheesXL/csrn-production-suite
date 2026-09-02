"""Round 23: Command Center quick-launch toolbar.

Three per-install fields on the Identity Profile's `streaming` section --
`broadcast_software_path`, `youtube_url`, `facebook_url` -- edited through
the existing Configuration Manager (/api/config), plus a fire-and-forget
launch route for the broadcast software.
"""
from __future__ import annotations

import copy
import json

import pytest

import app as app_module
import identity_service
from configuration_service import ConfigurationService


# --------------------------------------------------------------------------
# Task A -- storage: streaming rides the existing /api/config write path
# --------------------------------------------------------------------------


def test_streaming_templates_carry_the_quick_launch_fields() -> None:
    for template in (identity_service.BLANK_STREAMING, identity_service.LEGACY_STREAMING):
        assert set(template) >= {
            "facebook_live",
            "youtube_live",
            "broadcast_software_path",
            "youtube_url",
            "facebook_url",
        }
    # new fields are blank even on the existing install
    assert identity_service.LEGACY_STREAMING["broadcast_software_path"] == ""
    assert identity_service.LEGACY_STREAMING["youtube_url"] == ""
    assert identity_service.LEGACY_STREAMING["facebook_url"] == ""


def test_default_config_exposes_streaming_from_the_profile() -> None:
    assert "streaming" in app_module.DEFAULT_CONFIG
    assert set(app_module.DEFAULT_CONFIG["streaming"]) >= {
        "broadcast_software_path",
        "youtube_url",
        "facebook_url",
    }


def test_configuration_service_merges_the_streaming_section() -> None:
    config = {
        "organization": {"name": "X"},
        "streaming": {
            "facebook_live": "https://fb.example/live",
            "youtube_live": "https://yt.example/live",
            "broadcast_software_path": "",
            "youtube_url": "",
            "facebook_url": "",
        },
        "application": {"version": "v", "build": "b"},
    }
    saved: list[dict] = []

    def load_config():
        return copy.deepcopy(config)

    def save_config(value):
        config.clear()
        config.update(copy.deepcopy(value))
        saved.append(copy.deepcopy(value))

    service = ConfigurationService(
        load_config=load_config,
        save_config=save_config,
        runtime_version="v",
        runtime_build="b",
    )

    result = service.update(
        {"streaming": {"broadcast_software_path": "C:\\obs\\obs64.exe"}}
    )

    assert result.ok
    streaming = result.data["config"]["streaming"]
    assert streaming["broadcast_software_path"] == "C:\\obs\\obs64.exe"
    # the launcher URLs are untouched by a partial patch
    assert streaming["facebook_live"] == "https://fb.example/live"
    assert streaming["youtube_live"] == "https://yt.example/live"


def test_persist_identity_sections_mirrors_streaming_to_the_profile(monkeypatch, tmp_path):
    # _persist_identity_sections is the half of save_config() that keeps the
    # Identity Profile (which the game-day launcher reads) in sync with a
    # Configuration Manager save. Exercised directly so the test never
    # touches the real config repository.
    identity_file = tmp_path / "identity_profile.json"
    identity_service.save_identity_profile(
        identity_file,
        {
            "streaming": {
                "facebook_live": "https://fb.example/producer",
                "youtube_live": "https://yt.example/studio",
            }
        },
        existing_install=True,
    )
    monkeypatch.setattr(app_module, "IDENTITY_FILE", identity_file)

    app_module._persist_identity_sections(
        {
            "organization": {"name": "Test Org"},
            "streaming": {
                "broadcast_software_path": "C:\\vMix\\vMix64.exe",
                "youtube_url": "https://youtube.com/@testorg/live",
                "facebook_url": "https://facebook.com/testorg",
            },
        }
    )

    on_disk = json.loads(identity_file.read_text(encoding="utf-8"))["streaming"]
    assert on_disk["broadcast_software_path"] == "C:\\vMix\\vMix64.exe"
    assert on_disk["youtube_url"] == "https://youtube.com/@testorg/live"
    assert on_disk["facebook_url"] == "https://facebook.com/testorg"
    # the game-day launcher's URLs survive the Configuration Manager save
    assert on_disk["facebook_live"] == "https://fb.example/producer"
    assert on_disk["youtube_live"] == "https://yt.example/studio"


def test_settings_form_has_the_three_quick_launch_fields() -> None:
    from pathlib import Path

    html = (Path(__file__).resolve().parents[1] / "templates" / "index.html").read_text(
        encoding="utf-8"
    )
    assert 'id="cfgBroadcastSoftware"' in html
    assert 'id="cfgBroadcastSoftwareFile"' in html and 'type="file"' in html
    assert 'id="cfgYoutubeUrl"' in html
    assert 'id="cfgFacebookUrl"' in html
    # wired into the config read/write path
    assert "streaming.broadcast_software_path" in html
    assert "broadcast_software_path: document.getElementById('cfgBroadcastSoftware')" in html
