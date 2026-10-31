"""Personnel was removed (2026-10-31, Jason: "Remove it too"): no Personnel
page, API, crew picks, roster coaches panel, print-sheet staff page or
personnel ID graphic. The Settings social-link check it used to serve now
lives in the system routes."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")


def test_files_menu_and_console_are_gone() -> None:
    for name in ("personnel_service.py", "routes/personnel_routes.py"):
        assert not (ROOT / name).exists(), name
    nav = (ROOT / "static" / "csrn-navigation.js").read_text(encoding="utf-8")
    assert "'broadcasters'" not in nav
    for gone in ('id="broadcastersModule"', 'id="crewPlayByPlay"', 'id="rosterStaffPanel"',
                 "/api/broadcasters", "function loadBroadcasters", "RosterStaff", "/api/graphics/personnel"):
        assert gone not in HTML, gone


def test_routes_are_gone_but_the_social_link_check_remains() -> None:
    import app as app_module

    rules = {rule.rule: rule.endpoint for rule in app_module.app.url_map.iter_rules()}
    assert not any(r.startswith(("/api/broadcasters", "/personnel-headshots", "/api/personnel"))
                   or r == "/api/graphics/personnel" for r in rules)
    assert rules["/api/validate-social"].startswith("system_routes.")
    client = app_module.app.test_client()
    with client.session_transaction() as session:
        session["authenticated"] = True
    result = client.post("/api/validate-social", json={"platform": "facebook", "value": "facebook.com/WestsideSN"})
    assert result.status_code == 200 and result.get_json()["valid"] is True
