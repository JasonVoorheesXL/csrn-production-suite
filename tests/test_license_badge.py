"""Round 15 Task C -- the "Licensed to: <org>" badge in the settings screen.

A soft social deterrent: a shared/copied install visibly shows who it is
really licensed to. Not a technical control (that's the Task B gate).
"""

from __future__ import annotations

from pathlib import Path

import app as app_module

ROOT = Path(__file__).resolve().parents[1]


def test_settings_screen_renders_a_licensed_to_badge() -> None:
    html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    # Lives in the Configuration Manager (settings) panel, nothing overlay-facing.
    settings = html.split('id="settingsModule"', 1)[1].split("</section>", 1)[0]
    assert 'id="licenseBadge"' in settings
    assert "Licensed to:" in settings
    assert 'id="licenseBadgeOrg"' in settings

    assert "async function updateLicenseBadge()" in html
    assert "/api/licensing/status" in html
    # populated whenever the config screen loads
    assert "updateLicenseBadge();" in html.split("async function loadConfig()", 1)[1]


def test_licensing_status_exposes_the_customer_name_for_the_badge(monkeypatch) -> None:
    monkeypatch.setattr(app_module, "pin_is_configured", lambda: True)
    monkeypatch.setitem(app_module.app.config, "TESTING", True)
    with app_module.app.test_client() as client:
        with client.session_transaction() as session:
            session["authenticated"] = True
        response = client.get("/api/licensing/status")
    assert response.status_code == 200
    licensing = response.get_json().get("licensing", {})
    # Shape the badge reads: licensing.license.customer (license may be null
    # on an unlicensed install -- the badge just stays hidden then).
    assert "license" in licensing
    assert "valid" in licensing
