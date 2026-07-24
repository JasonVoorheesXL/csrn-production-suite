from __future__ import annotations

import time
from pathlib import Path

import pytest
from werkzeug.security import check_password_hash, generate_password_hash

import app as app_module
from core_repositories import SecurityRepository
from persistence_engine import JsonPersistenceEngine


@pytest.fixture
def security_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    defaults = {
        "pin_hash": "",
        "secret_key": "route-test-secret",
        "failed_attempts": 0,
        "locked_until": 0,
    }
    repository = SecurityRepository(
        JsonPersistenceEngine(
            tmp_path / "backups",
            tmp_path / "quarantine",
        ),
        tmp_path / "security.json",
        defaults,
    )
    monkeypatch.setattr(app_module, "SECURITY_REPOSITORY", repository)
    monkeypatch.setitem(app_module.app.config, "TESTING", True)
    monkeypatch.setitem(
        app_module.app.config,
        "SECRET_KEY",
        "route-test-secret",
    )

    with app_module.app.test_client() as client:
        yield client, repository


def test_setup_pin_uses_repository_and_authenticates(security_client) -> None:
    client, repository = security_client
    initial = repository.load()
    initial["failed_attempts"] = 2
    initial["locked_until"] = 500
    repository.save(initial)

    response = client.post(
        "/api/setup-pin",
        json={"pin": "123456", "confirm": "123456"},
    )

    assert response.status_code == 200
    assert response.get_json() == {"ok": True}

    stored = repository.load()
    assert check_password_hash(stored["pin_hash"], "123456")
    assert stored["failed_attempts"] == 0
    assert stored["locked_until"] == 0

    with client.session_transaction() as active_session:
        assert active_session["authenticated"] is True


def test_successful_login_clears_failed_attempts(security_client) -> None:
    client, repository = security_client
    repository.update_credentials(
        pin_hash=generate_password_hash("123456", method="scrypt")
    )

    failed = client.post("/api/login", json={"pin": "000000"})
    assert failed.status_code == 401
    assert failed.get_json()["attempts_remaining"] == 2
    assert repository.load()["failed_attempts"] == 1

    successful = client.post("/api/login", json={"pin": "123456"})
    assert successful.status_code == 200
    assert successful.get_json() == {"ok": True}

    stored = repository.load()
    assert stored["failed_attempts"] == 0
    assert stored["locked_until"] == 0


def test_third_failed_login_applies_lockout(security_client) -> None:
    client, repository = security_client
    repository.update_credentials(
        pin_hash=generate_password_hash("123456", method="scrypt")
    )

    first = client.post("/api/login", json={"pin": "000000"})
    second = client.post("/api/login", json={"pin": "000000"})
    third = client.post("/api/login", json={"pin": "000000"})

    assert first.status_code == 401
    assert second.status_code == 401
    assert third.status_code == 429
    assert third.get_json()["error"] == "LOCKED"

    stored = repository.load()
    assert stored["failed_attempts"] == 0
    assert stored["locked_until"] > time.time()

    blocked = client.post("/api/login", json={"pin": "123456"})
    assert blocked.status_code == 429
    assert blocked.get_json()["error"] == "LOCKED"
