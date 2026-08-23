from __future__ import annotations

from pathlib import Path

from werkzeug.security import check_password_hash

from core_repositories import SecurityRepository
from persistence_engine import JsonPersistenceEngine
from security_service import SecurityService


DEFAULTS = {
    "pin_hash": "",
    "secret_key": "test-secret",
    "failed_attempts": 0,
    "locked_until": 0,
}


def make_service(
    tmp_path: Path,
    *,
    now: float = 1000.0,
) -> tuple[SecurityService, SecurityRepository]:
    repository = SecurityRepository(
        JsonPersistenceEngine(
            tmp_path / "backups",
            tmp_path / "quarantine",
        ),
        tmp_path / "security.json",
        DEFAULTS,
    )
    service = SecurityService(
        repository,
        max_attempts=3,
        lockout_seconds=60,
        clock=lambda: now,
    )
    return service, repository


def test_setup_pin_validates_and_persists_hash(tmp_path: Path) -> None:
    service, repository = make_service(tmp_path)

    invalid = service.setup_pin("123", "123")
    mismatch = service.setup_pin("123456", "654321")
    created = service.setup_pin("123456", "123456")

    assert invalid.code == "PIN_MUST_BE_6_DIGITS"
    assert mismatch.code == "PIN_MISMATCH"
    assert created.ok

    stored = repository.load()
    assert check_password_hash(stored["pin_hash"], "123456")
    assert stored["failed_attempts"] == 0
    assert stored["locked_until"] == 0


def test_successful_authentication_clears_failures(tmp_path: Path) -> None:
    service, repository = make_service(tmp_path)
    assert service.setup_pin("123456", "123456").ok

    failed = service.authenticate("000000")
    successful = service.authenticate("123456")

    assert failed.code == "INVALID_PIN"
    assert failed.data["attempts_remaining"] == 2
    assert successful.ok
    assert repository.load()["failed_attempts"] == 0


def test_third_failure_locks_authentication(tmp_path: Path) -> None:
    service, repository = make_service(tmp_path)
    assert service.setup_pin("123456", "123456").ok

    first = service.authenticate("000000")
    second = service.authenticate("000000")
    third = service.authenticate("000000")
    blocked = service.authenticate("123456")

    assert first.data["attempts_remaining"] == 2
    assert second.data["attempts_remaining"] == 1
    assert third.code == "LOCKED"
    assert third.data["locked_seconds"] == 60
    assert blocked.code == "LOCKED"

    stored = repository.load()
    assert stored["failed_attempts"] == 0
    assert stored["locked_until"] == 1060


