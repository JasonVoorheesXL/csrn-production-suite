from __future__ import annotations

from functools import wraps
from typing import Any

import pytest
from flask import Flask, jsonify, session

from routes.access_model_routes import (
    AccessModelRoutesDependencies,
    create_access_model_blueprint,
)


def _require_auth(func):
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any):
        if not session.get("authenticated"):
            return jsonify({"error": "AUTH_REQUIRED"}), 401
        return func(*args, **kwargs)

    return wrapper


@pytest.fixture
def client():
    licensed = [["football", "basketball"]]

    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="access-model-test")
    app.register_blueprint(
        create_access_model_blueprint(
            AccessModelRoutesDependencies(
                require_auth=_require_auth,
                licensed_sport_families=lambda: list(licensed[0]),
            )
        )
    )
    with app.test_client() as test_client:
        yield test_client, licensed


def _authenticate(test_client) -> None:
    with test_client.session_transaction() as current:
        current["authenticated"] = True


def test_session_context_requires_auth(client) -> None:
    test_client, _ = client
    assert test_client.get("/api/session-context").status_code == 401
    assert test_client.post("/api/sport-context", json={"sport": "football"}).status_code == 401


def test_session_context_reports_current_context_and_license(client) -> None:
    test_client, _ = client
    _authenticate(test_client)
    with test_client.session_transaction() as current:
        current["sport_context"] = "football"

    body = test_client.get("/api/session-context").get_json()

    assert body["sport_context"] == "football"
    assert body["sport_scope"] == "football"
    assert body["licensed_sports"] == ["football", "basketball"]
    assert body["all_sports_licensed"] is False
    assert [o["context"] for o in body["other_sports"]][:1] == ["canadian_football"]
    fams = {f["family"]: f for f in body["family_sports"]}
    assert fams["football"]["available"] is True          # licensed + engine
    assert fams["basketball"]["available"] is False        # licensed, no engine
    assert fams["basketball"]["licensed"] is True
    assert fams["baseball"]["licensed"] is False


def test_sport_context_switch_sets_a_licensed_engine_ready_family(client) -> None:
    test_client, _ = client
    _authenticate(test_client)

    body = test_client.post("/api/sport-context", json={"sport": "Football"}).get_json()

    assert body["sport_context"] == "football"
    assert body["sport_scope"] == "football"
    with test_client.session_transaction() as current:
        assert current["sport_context"] == "football"


def test_canadian_football_context_is_covered_by_the_football_license(client) -> None:
    # Invariant 1: one football license entry, both football contexts.
    test_client, licensed = client
    licensed[0] = ["football"]
    _authenticate(test_client)

    body = test_client.post("/api/sport-context", json={"sport": "canadian_football"}).get_json()

    assert body["sport_context"] == "canadian_football"
    assert body["sport_scope"] == "football"       # invariant 2: shared roster/sponsor pool
    with test_client.session_transaction() as current:
        assert current["sport_context"] == "canadian_football"


def test_sport_context_switch_rejects_an_unlicensed_engine_ready_family(client) -> None:
    test_client, licensed = client
    licensed[0] = ["basketball"]  # football not licensed on this install
    _authenticate(test_client)

    response = test_client.post("/api/sport-context", json={"sport": "football"})

    assert response.status_code == 403
    assert response.get_json()["error"] == "SPORT_NOT_LICENSED"
    with test_client.session_transaction() as current:
        assert "sport_context" not in current


def test_sport_context_switch_licensed_but_engineless_family_is_not_ready(client) -> None:
    # basketball IS licensed on this stub install, but there is no engine
    # for it yet -- a distinct reason from "unlicensed".
    test_client, _ = client
    _authenticate(test_client)

    response = test_client.post("/api/sport-context", json={"sport": "basketball"})

    assert response.status_code == 400
    assert response.get_json()["error"] == "SPORT_ENGINE_NOT_READY"
    with test_client.session_transaction() as current:
        assert "sport_context" not in current


def test_sport_context_switch_unlicensed_engineless_family_is_coming_soon(client) -> None:
    # "baseball" used to be this scenario's example (unlicensed AND no
    # engine); P5 gave baseball/softball a real engine
    # (sport_families.ENGINE_READY), so a sport genuinely still lacking
    # both is needed -- "soccer" is unlicensed in this fixture (licensed =
    # ["football", "basketball"]) and still has no broadcast engine.
    test_client, _ = client
    _authenticate(test_client)

    response = test_client.post("/api/sport-context", json={"sport": "soccer"})

    assert response.status_code == 400
    assert response.get_json()["error"] == "SPORT_COMING_SOON"


def test_sport_context_switch_rejects_coming_soon_sport(client) -> None:
    test_client, _ = client
    _authenticate(test_client)

    response = test_client.post("/api/sport-context", json={"sport": "hockey"})

    assert response.status_code == 400
    assert response.get_json()["error"] == "SPORT_COMING_SOON"
    with test_client.session_transaction() as current:
        assert "sport_context" not in current


def test_sport_context_switch_rejects_the_gateway_token(client) -> None:
    test_client, _ = client
    _authenticate(test_client)

    response = test_client.post("/api/sport-context", json={"sport": "all_others"})

    assert response.status_code == 400
    assert response.get_json()["error"] == "SPORT_NOT_RECOGNIZED"


def test_sport_context_switch_rejects_unknown_sport(client) -> None:
    test_client, _ = client
    _authenticate(test_client)

    response = test_client.post("/api/sport-context", json={"sport": "curling"})

    assert response.status_code == 400
    assert response.get_json()["error"] == "SPORT_NOT_RECOGNIZED"


def test_sport_context_empty_string_clears_the_context(client) -> None:
    test_client, _ = client
    _authenticate(test_client)
    test_client.post("/api/sport-context", json={"sport": "football"})

    body = test_client.post("/api/sport-context", json={"sport": ""}).get_json()

    assert body["sport_context"] == ""
    with test_client.session_transaction() as current:
        assert "sport_context" not in current


def test_sport_context_switch_needs_no_pin(client) -> None:
    # The whole point: an authenticated operator changes sport without
    # re-entering the PIN. There is no security service in this blueprint.
    test_client, _ = client
    _authenticate(test_client)
    first = test_client.post("/api/sport-context", json={"sport": "football"}).get_json()
    second = test_client.post("/api/sport-context", json={"sport": "canadian_football"}).get_json()
    assert first["sport_context"] == "football"
    assert second["sport_context"] == "canadian_football"
