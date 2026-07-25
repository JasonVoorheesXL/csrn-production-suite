from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest
from flask import Flask, session

from routes.security_upgrade_routes import (
    SecurityUpgradeRoutesDependencies,
    create_security_upgrade_blueprint,
)


@dataclass(frozen=True)
class StubResult:
    code: str
    data: dict[str, Any]

    @property
    def ok(self) -> bool:
        return self.code == "OK"


class StubSecurityService:
    def __init__(self) -> None:
        self.setup_result = StubResult("OK", {})
        self.authenticate_result = StubResult("OK", {})
        self.setup_calls: list[tuple[str, str]] = []
        self.authenticate_calls: list[str] = []

    def setup_pin(self, pin: str, confirm: str) -> StubResult:
        self.setup_calls.append((pin, confirm))
        return self.setup_result

    def authenticate(self, pin: str) -> StubResult:
        self.authenticate_calls.append(pin)
        return self.authenticate_result


class StubUpgradeService:
    def __init__(self) -> None:
        self.candidate_result = StubResult(
            "OK",
            {"candidate": {"available": True, "source_build": "1.12"}},
        )
        self.status_result = StubResult(
            "OK",
            {"report": {"status": "NOT_RUN"}},
        )
        self.run_result = StubResult(
            "OK",
            {"report": {"status": "COMPLETE"}},
        )
        self.run_calls: list[Any] = []

    def candidate(self) -> StubResult:
        return self.candidate_result

    def status(self) -> StubResult:
        return self.status_result

    def run(self, include_security: Any = True) -> StubResult:
        self.run_calls.append(include_security)
        return self.run_result


@pytest.fixture
def route_client():
    security_service = StubSecurityService()
    upgrade_service = StubUpgradeService()
    security_record: dict[str, Any] = {
        "pin_hash": "",
        "locked_until": 0,
    }
    now = [1_000.0]

    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="security-route-test")
    app.register_blueprint(
        create_security_upgrade_blueprint(
            SecurityUpgradeRoutesDependencies(
                get_security_service=lambda: security_service,
                load_security=lambda: dict(security_record),
                authenticated=lambda: bool(session.get("authenticated")),
                clock=lambda: now[0],
                get_upgrade_service=lambda: upgrade_service,
            )
        )
    )

    with app.test_client() as client:
        yield (
            client,
            app,
            security_service,
            upgrade_service,
            security_record,
            now,
        )


def test_blueprint_registers_preserved_security_and_upgrade_urls(route_client) -> None:
    _, app, _, _, _, _ = route_client
    rules = {
        (rule.rule, tuple(sorted(rule.methods - {"HEAD", "OPTIONS"})))
        for rule in app.url_map.iter_rules()
    }
    expected = {
        ("/api/security-status", ("GET",)),
        ("/api/setup-pin", ("POST",)),
        ("/api/login", ("POST",)),
        ("/api/logout", ("POST",)),
        ("/api/upgrade/candidate", ("GET",)),
        ("/api/upgrade/status", ("GET",)),
        ("/api/upgrade/migrate", ("POST",)),
    }
    assert expected.issubset(rules)


def test_security_status_is_public_and_reports_lock_time(route_client) -> None:
    client, _, _, _, security_record, now = route_client
    security_record.update(pin_hash="configured", locked_until=1_045)
    now[0] = 1_000.2

    response = client.get("/api/security-status")

    assert response.status_code == 200
    assert response.get_json() == {
        "pin_configured": True,
        "authenticated": False,
        "locked_seconds": 44,
    }


def test_security_status_reports_authenticated_session(route_client) -> None:
    client, _, _, _, _, _ = route_client
    with client.session_transaction() as current:
        current["authenticated"] = True

    response = client.get("/api/security-status")

    assert response.status_code == 200
    assert response.get_json()["authenticated"] is True


def test_setup_pin_authenticates_new_session(route_client) -> None:
    client, _, security_service, _, _, _ = route_client

    response = client.post(
        "/api/setup-pin",
        json={"pin": "123456", "confirm": "123456"},
    )

    assert response.status_code == 200
    assert response.get_json() == {"ok": True}
    assert security_service.setup_calls == [("123456", "123456")]
    with client.session_transaction() as current:
        assert current["authenticated"] is True
        assert current.permanent is True


@pytest.mark.parametrize(
    ("code", "expected_status"),
    [
        ("PIN_ALREADY_CONFIGURED", 409),
        ("PIN_MUST_BE_6_DIGITS", 400),
        ("PIN_MISMATCH", 400),
    ],
)
def test_setup_pin_maps_service_errors(
    route_client,
    code: str,
    expected_status: int,
) -> None:
    client, _, security_service, _, _, _ = route_client
    security_service.setup_result = StubResult(code, {})

    response = client.post(
        "/api/setup-pin",
        json={"pin": "123456", "confirm": "654321"},
    )

    assert response.status_code == expected_status
    assert response.get_json() == {"error": code}


def test_login_authenticates_valid_pin(route_client) -> None:
    client, _, security_service, _, _, _ = route_client

    response = client.post("/api/login", json={"pin": "123456"})

    assert response.status_code == 200
    assert response.get_json() == {"ok": True}
    assert security_service.authenticate_calls == ["123456"]
    with client.session_transaction() as current:
        assert current["authenticated"] is True
        assert current.permanent is True


def test_login_maps_invalid_pin(route_client) -> None:
    client, _, security_service, _, _, _ = route_client
    security_service.authenticate_result = StubResult(
        "INVALID_PIN",
        {"attempts_remaining": 2},
    )

    response = client.post("/api/login", json={"pin": "000000"})

    assert response.status_code == 401
    assert response.get_json() == {
        "error": "INVALID_PIN",
        "attempts_remaining": 2,
    }


def test_login_maps_lockout(route_client) -> None:
    client, _, security_service, _, _, _ = route_client
    security_service.authenticate_result = StubResult(
        "LOCKED",
        {"locked_seconds": 60},
    )

    response = client.post("/api/login", json={"pin": "000000"})

    assert response.status_code == 429
    assert response.get_json() == {
        "error": "LOCKED",
        "locked_seconds": 60,
    }


def test_logout_clears_session(route_client) -> None:
    client, _, _, _, _, _ = route_client
    with client.session_transaction() as current:
        current["authenticated"] = True
        current["other"] = "value"

    response = client.post("/api/logout")

    assert response.status_code == 200
    assert response.get_json() == {"ok": True}
    with client.session_transaction() as current:
        assert dict(current) == {}


def test_upgrade_candidate_returns_candidate(route_client) -> None:
    client, _, _, _, _, _ = route_client

    response = client.get("/api/upgrade/candidate")

    assert response.status_code == 200
    assert response.get_json() == {
        "available": True,
        "source_build": "1.12",
    }


def test_upgrade_candidate_maps_inspection_failure(route_client) -> None:
    client, _, _, upgrade_service, _, _ = route_client
    upgrade_service.candidate_result = StubResult(
        "INSPECTION_FAILED",
        {"message": "candidate scan failed"},
    )

    response = client.get("/api/upgrade/candidate")

    assert response.status_code == 500
    assert response.get_json() == {
        "error": "INSPECTION_FAILED",
        "message": "candidate scan failed",
    }


def test_upgrade_status_returns_report(route_client) -> None:
    client, _, _, _, _, _ = route_client

    response = client.get("/api/upgrade/status")

    assert response.status_code == 200
    assert response.get_json() == {"status": "NOT_RUN"}


def test_upgrade_migration_defaults_to_security_migration(route_client) -> None:
    client, _, _, upgrade_service, _, _ = route_client

    response = client.post("/api/upgrade/migrate", json={})

    assert response.status_code == 200
    assert response.get_json() == {"status": "COMPLETE"}
    assert upgrade_service.run_calls == [True]


def test_upgrade_migration_preserves_include_security_value(route_client) -> None:
    client, _, _, upgrade_service, _, _ = route_client

    response = client.post(
        "/api/upgrade/migrate",
        json={"include_security": False},
    )

    assert response.status_code == 200
    assert upgrade_service.run_calls == [False]
