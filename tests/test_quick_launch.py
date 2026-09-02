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


# --------------------------------------------------------------------------
# Task B -- launch mechanics: fire-and-forget, graceful failure
# --------------------------------------------------------------------------


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(app_module, "pin_is_configured", lambda: True)
    monkeypatch.setitem(app_module.app.config, "TESTING", True)
    with app_module.app.test_client() as test_client:
        with test_client.session_transaction() as session:
            session["authenticated"] = True
        yield test_client


def _configure_software_path(monkeypatch, path: str) -> None:
    monkeypatch.setattr(
        app_module, "load_config", lambda: {"streaming": {"broadcast_software_path": path}}
    )


def test_launch_route_requires_auth(monkeypatch):
    monkeypatch.setattr(app_module, "pin_is_configured", lambda: True)
    with app_module.app.test_client() as anon:
        response = anon.post("/api/launch/broadcast-software")
    assert response.status_code in (401, 403)


def test_launch_route_reports_not_configured(client, monkeypatch):
    _configure_software_path(monkeypatch, "")
    response = client.post("/api/launch/broadcast-software")
    assert response.status_code == 400
    assert response.get_json()["error"] == "NOT_CONFIGURED"


def test_launch_route_reports_a_missing_file(client, monkeypatch, tmp_path):
    _configure_software_path(monkeypatch, str(tmp_path / "gone" / "obs64.exe"))
    response = client.post("/api/launch/broadcast-software")
    assert response.status_code == 400
    body = response.get_json()
    assert body["error"] == "NOT_FOUND"
    assert "obs64.exe" in body["message"]


def test_launch_route_starts_the_process_without_blocking(client, monkeypatch, tmp_path):
    exe = tmp_path / "obs" / "obs64.exe"
    exe.parent.mkdir(parents=True)
    exe.write_text("stub", encoding="utf-8")
    _configure_software_path(monkeypatch, str(exe))

    calls: list[dict] = []

    class _FakePopen:
        def __init__(self, args, **kwargs):
            calls.append({"args": args, "kwargs": kwargs})

        # a real Popen is never waited on by the helper; if the handler
        # blocked on one of these the test would hang.
        def wait(self, *a, **k):  # pragma: no cover - must not be called
            raise AssertionError("launch must be fire-and-forget")

    monkeypatch.setattr("subprocess.Popen", _FakePopen)

    response = client.post("/api/launch/broadcast-software")

    assert response.status_code == 200
    assert response.get_json()["ok"] is True
    assert len(calls) == 1
    assert calls[0]["args"] == [str(exe)]
    assert calls[0]["kwargs"]["cwd"] == str(exe.parent)


def test_launch_helper_handles_a_popen_oserror(monkeypatch, tmp_path):
    exe = tmp_path / "vmix.exe"
    exe.write_text("stub", encoding="utf-8")
    monkeypatch.setattr(
        app_module,
        "load_config",
        lambda: {"streaming": {"broadcast_software_path": str(exe)}},
    )

    def _boom(*a, **k):
        raise OSError("access denied")

    monkeypatch.setattr("subprocess.Popen", _boom)

    status, body = app_module._launch_broadcast_software()
    assert status == 500
    assert body["error"] == "LAUNCH_FAILED"


# --------------------------------------------------------------------------
# Task C -- the Command Center toolbar
# --------------------------------------------------------------------------


def test_command_center_has_the_quick_launch_toolbar() -> None:
    from pathlib import Path

    html = (Path(__file__).resolve().parents[1] / "templates" / "index.html").read_text(
        encoding="utf-8"
    )
    assert 'id="qlBroadcastBtn"' in html
    # YouTube / Facebook are plain target="_blank" anchors, no backend route
    assert 'id="qlYoutubeLink"' in html and 'id="qlFacebookLink"' in html
    assert 'target="_blank"' in html
    assert "launchBroadcastSoftware()" in html
    assert "/api/launch/broadcast-software" in html
    # disabled + tooltip when unconfigured
    assert "not configured yet" in html
    assert "renderQuickLaunch()" in html
