"""Real end-to-end coverage for GET /api/broadcasts/<id>/maxpreps-export.txt
through the actual Flask app (not a stub) -- proves app.py's DI wiring and
routes/broadcast_routes.py's blueprint registration both work, on top of the
service-level coverage in test_maxpreps_export_service.py.
"""
from __future__ import annotations

import copy

import pytest

import app as app_module
from tests.test_maxpreps_export_service import BROADCAST_ID, game_state


@pytest.fixture
def maxpreps_client(monkeypatch: pytest.MonkeyPatch):
    state = game_state()
    broadcasts = [
        {
            "broadcast_id": BROADCAST_ID,
            "home_team": "Home Eagles",
            "visitor_team": "Visitor Hawks",
            "date": "2026-10-04",
            "sport": "Football",
        }
    ]
    monkeypatch.setattr(app_module, "MAXPREPS_EXPORT_SERVICE", None, raising=False)
    monkeypatch.setattr(app_module, "pin_is_configured", lambda: True)
    monkeypatch.setattr(app_module, "load_broadcasts", lambda: copy.deepcopy(broadcasts))
    monkeypatch.setattr(app_module, "load_state", lambda: copy.deepcopy(state))
    monkeypatch.setattr(app_module, "load_final_state_archive", lambda broadcast_id: None)
    monkeypatch.setitem(app_module.app.config, "TESTING", True)
    monkeypatch.setitem(app_module.app.config, "SECRET_KEY", "maxpreps-export-route-test")
    with app_module.app.test_client() as client:
        with client.session_transaction() as active_session:
            active_session["authenticated"] = True
        yield client


def test_route_returns_a_real_pipe_delimited_txt_attachment(maxpreps_client) -> None:
    response = maxpreps_client.get(
        f"/api/broadcasts/{BROADCAST_ID}/maxpreps-export.txt?team=home"
    )
    assert response.status_code == 200
    assert response.mimetype == "text/plain"
    assert "attachment" in response.headers["Content-Disposition"]
    assert response.headers["Content-Disposition"].endswith('.txt"')
    body = response.get_data(as_text=True)
    assert body.splitlines()[0] == "Jersey|" + "|".join(
        app_module.MaxPrepsExportService.FIELD_ORDER
    )
    assert "22|2|10|" in body


def test_route_requires_a_valid_team_query_param(maxpreps_client) -> None:
    response = maxpreps_client.get(
        f"/api/broadcasts/{BROADCAST_ID}/maxpreps-export.txt"
    )
    assert response.status_code == 400
    assert response.get_json()["error"] == "INVALID_TEAM"


def test_route_404s_for_an_unknown_broadcast(maxpreps_client) -> None:
    response = maxpreps_client.get(
        "/api/broadcasts/NOPE/maxpreps-export.txt?team=home"
    )
    assert response.status_code == 404


def test_route_422s_with_a_clear_message_for_a_final_score_only_game(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    empty_state = {"broadcast_id": BROADCAST_ID, "events": [], "plays": []}
    broadcasts = [
        {
            "broadcast_id": BROADCAST_ID,
            "home_team": "Home Eagles",
            "visitor_team": "Visitor Hawks",
            "date": "2026-10-04",
            "sport": "Football",
        }
    ]
    monkeypatch.setattr(app_module, "MAXPREPS_EXPORT_SERVICE", None, raising=False)
    monkeypatch.setattr(app_module, "pin_is_configured", lambda: True)
    monkeypatch.setattr(app_module, "load_broadcasts", lambda: copy.deepcopy(broadcasts))
    monkeypatch.setattr(app_module, "load_state", lambda: copy.deepcopy(empty_state))
    monkeypatch.setattr(app_module, "load_final_state_archive", lambda broadcast_id: None)
    monkeypatch.setitem(app_module.app.config, "TESTING", True)
    monkeypatch.setitem(app_module.app.config, "SECRET_KEY", "maxpreps-export-route-test-empty")
    with app_module.app.test_client() as client:
        with client.session_transaction() as active_session:
            active_session["authenticated"] = True
        response = client.get(
            f"/api/broadcasts/{BROADCAST_ID}/maxpreps-export.txt?team=home"
        )
    assert response.status_code == 422
    body = response.get_json()
    assert body["error"] == "NO_PLAYER_DATA"
    assert "Home Eagles" in body["message"]


def test_route_requires_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app_module, "pin_is_configured", lambda: True)
    monkeypatch.setitem(app_module.app.config, "TESTING", True)
    monkeypatch.setitem(app_module.app.config, "SECRET_KEY", "maxpreps-export-route-test-noauth")
    with app_module.app.test_client() as client:
        response = client.get(
            f"/api/broadcasts/{BROADCAST_ID}/maxpreps-export.txt?team=home"
        )
    assert response.status_code == 401
