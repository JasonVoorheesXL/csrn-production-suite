"""Audit round 3 (2026-10-31): Settings > Sports. A station switches its
licensed sports on and off; football alone is on until it does. A switched-off
sport leaves the login tiles and the sport picker and cannot be entered.
"""
from __future__ import annotations

from functools import wraps
from pathlib import Path
from typing import Any

import pytest
from flask import Flask, jsonify, session

import identity_service
import sport_families
import station_sports_service as service
from routes.access_model_routes import AccessModelRoutesDependencies, create_access_model_blueprint

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")


def test_football_alone_is_on_by_default() -> None:
    assert service.SWITCHABLE == ("football", "basketball", "baseball", "softball")
    assert service.normalize_station_sports(None) == {"on": ["football"]}
    assert service.normalize_station_sports({"on": []}) == {"on": ["football"]}
    assert service.normalize_station_sports({"on": ["Softball", "basketball", "curling"]}) == {
        "on": ["basketball", "softball"]
    }


def test_validation_messages() -> None:
    assert service.validate_station_sports({"on": ["football"]}) is None
    assert service.validate_station_sports({"on": []}) == "Keep at least one sport switched on."
    assert "curling" in service.validate_station_sports({"on": ["curling"]})
    assert service.validate_station_sports({"on": "football"}) is not None


def test_switched_off_sports_leave_the_licensed_list_but_engineless_ones_stay() -> None:
    licensed = ["football", "basketball", "baseball", "softball", "soccer"]
    station = {"on": ["football", "softball"]}
    assert service.families_in_use(licensed, station) == ["football", "softball", "soccer"]
    assert service.switched_off(licensed, station) == ["basketball", "baseball"]


def test_view_marks_switched_off_tiles_and_drops_a_stale_context() -> None:
    view = sport_families.sport_context_view("basketball", ["football"], ["basketball"])
    assert view["sport_context"] == ""
    assert view["switched_off_sports"] == ["basketball"]
    tiles = {tile["family"]: tile for tile in view["family_sports"]}
    assert tiles["basketball"]["switched_off"] is True
    assert tiles["football"]["switched_off"] is False


def test_identity_profile_carries_the_section(tmp_path) -> None:
    path = tmp_path / "identity_profile.json"
    profile = identity_service.load_identity_profile(path, existing_install=True)
    assert profile["station_sports"] == {"on": ["football"]}
    profile["station_sports"] = {"on": ["football", "basketball"]}
    identity_service.save_identity_profile(path, profile, existing_install=True)
    again = identity_service.load_identity_profile(path, existing_install=True)
    assert again["station_sports"] == {"on": ["football", "basketball"]}


def _require_auth(func):
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any):
        if not session.get("authenticated"):
            return jsonify({"error": "AUTH_REQUIRED"}), 401
        return func(*args, **kwargs)

    return wrapper


@pytest.fixture
def client():
    licensed = ["football", "basketball", "baseball", "softball"]
    store: dict[str, Any] = {"station": {"on": ["football"]}}

    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="station-sports-test")
    app.register_blueprint(
        create_access_model_blueprint(
            AccessModelRoutesDependencies(
                require_auth=_require_auth,
                licensed_sport_families=lambda: service.families_in_use(licensed, store["station"]),
                switched_off_sport_families=lambda: service.switched_off(licensed, store["station"]),
                all_licensed_sport_families=lambda: list(licensed),
                load_station_sports=lambda: store["station"],
                save_station_sports=lambda doc: store.update(station=dict(doc)) or doc,
            )
        )
    )
    with app.test_client() as test_client:
        with test_client.session_transaction() as current:
            current["authenticated"] = True
        yield test_client, store


def test_settings_reads_and_saves_the_switches(client) -> None:
    test_client, store = client
    data = test_client.get("/api/station-sports").get_json()
    assert data["on"] == ["football"]
    assert [sport["family"] for sport in data["sports"]] == list(service.SWITCHABLE)
    assert all(sport["licensed"] for sport in data["sports"])

    saved = test_client.post("/api/station-sports", json={"on": ["football", "basketball"]})
    assert saved.status_code == 200
    assert saved.get_json()["on"] == ["football", "basketball"]
    assert store["station"] == {"on": ["football", "basketball"]}

    bad = test_client.post("/api/station-sports", json={"on": []})
    assert bad.status_code == 400
    assert bad.get_json()["message"] == "Keep at least one sport switched on."


def test_a_switched_off_sport_cannot_be_entered(client) -> None:
    test_client, _ = client
    refused = test_client.post("/api/sport-context", json={"sport": "basketball"})
    assert refused.status_code == 403
    assert refused.get_json()["error"] == "SPORT_SWITCHED_OFF"
    assert test_client.post("/api/sport-context", json={"sport": "football"}).status_code == 200

    test_client.post("/api/station-sports", json={"on": ["football", "basketball"]})
    assert test_client.post("/api/sport-context", json={"sport": "basketball"}).status_code == 200


def test_console_hides_switched_off_tiles_and_has_the_settings_section() -> None:
    assert "status.family_sports.filter(f => !f.switched_off)" in HTML
    assert "SPORT_SWITCHED_OFF: 'That sport is switched off in Settings > Sports.'" in HTML
    assert '<div id="stationSportsList" class="station-sports-list"></div>' in HTML
    assert HTML.index("<h2>Sports</h2>") < HTML.index("<h2>Retired Tools</h2>")
    assert "if (module === 'settings') { loadConfig(); loadStationSports(); }" in HTML
    assert "api('/api/station-sports',{on})" in HTML
