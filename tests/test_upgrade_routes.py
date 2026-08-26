from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import app as app_module
from core_repositories import SecurityRepository
from persistence_engine import JsonPersistenceEngine
from security_service import SecurityService
from upgrade_service import UpgradeResult


if not hasattr(app_module, "get_upgrade_service"):
    pytest.skip(
        "UpgradeService routes are not integrated yet.",
        allow_module_level=True,
    )


class StubUpgradeService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.candidate_result = UpgradeResult(
            "OK",
            {
                "candidate": {
                    "available": True,
                    "source_build": "Build_0018",
                }
            },
        )
        self.status_result = UpgradeResult(
            "OK",
            {"report": {"status": "NOT_RUN"}},
        )
        self.run_result = UpgradeResult(
            "OK",
            {
                "report": {
                    "status": "MIGRATED",
                    "active_pin": "CREATE_NEW_PIN",
                }
            },
        )

    def candidate(self) -> UpgradeResult:
        self.calls.append(("candidate", None))
        return self.candidate_result

    def status(self) -> UpgradeResult:
        self.calls.append(("status", None))
        return self.status_result

    def run(self, include_security: Any = True) -> UpgradeResult:
        self.calls.append(("run", include_security))
        return self.run_result


@pytest.fixture
def upgrade_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    service = StubUpgradeService()
    monkeypatch.setattr(app_module, "UPGRADE_SERVICE", service, raising=False)
    monkeypatch.setitem(app_module.app.config, "TESTING", True)

    # /api/upgrade/migrate is now gated on pin_hash being unset (the
    # pre-setup flow this route exists for) -- point security state at an
    # isolated, no-PIN-configured repository instead of the real one, so
    # these route-delegation tests aren't at the mercy of whatever PIN
    # state happens to exist in this dev environment's real security.json.
    security_repository = SecurityRepository(
        JsonPersistenceEngine(
            tmp_path / "backups",
            tmp_path / "quarantine",
        ),
        tmp_path / "security.json",
        {
            "pin_hash": "",
            "secret_key": "upgrade-route-test-secret",
            "failed_attempts": 0,
            "locked_until": 0,
        },
    )
    security_service = SecurityService(
        security_repository,
        max_attempts=app_module.MAX_ATTEMPTS,
        lockout_seconds=app_module.LOCKOUT_SECONDS,
    )
    monkeypatch.setattr(app_module, "SECURITY_REPOSITORY", security_repository)
    monkeypatch.setattr(app_module, "SECURITY_SERVICE", security_service)

    with app_module.app.test_client() as client:
        yield client, service


def test_upgrade_candidate_route_delegates(upgrade_client) -> None:
    client, service = upgrade_client

    response = client.get("/api/upgrade/candidate")

    assert response.status_code == 200
    assert response.get_json() == {
        "available": True,
        "source_build": "Build_0018",
    }
    assert service.calls == [("candidate", None)]


def test_upgrade_candidate_route_reports_failure(upgrade_client) -> None:
    client, service = upgrade_client
    service.candidate_result = UpgradeResult(
        "INSPECTION_FAILED",
        {"message": "inspection broke"},
    )

    response = client.get("/api/upgrade/candidate")

    assert response.status_code == 500
    assert response.get_json() == {
        "error": "INSPECTION_FAILED",
        "message": "inspection broke",
    }


def test_upgrade_status_route_delegates(upgrade_client) -> None:
    client, service = upgrade_client

    response = client.get("/api/upgrade/status")

    assert response.status_code == 200
    assert response.get_json() == {"status": "NOT_RUN"}
    assert service.calls == [("status", None)]


def test_upgrade_migration_defaults_security_to_true(upgrade_client) -> None:
    client, service = upgrade_client

    response = client.post("/api/upgrade/migrate", json={})

    assert response.status_code == 200
    assert response.get_json()["status"] == "MIGRATED"
    assert service.calls == [("run", True)]


def test_upgrade_migration_passes_security_choice(upgrade_client) -> None:
    client, service = upgrade_client

    response = client.post(
        "/api/upgrade/migrate",
        json={"include_security": False},
    )

    assert response.status_code == 200
    assert service.calls == [("run", False)]


def test_upgrade_migration_route_blocked_once_a_pin_is_configured(
    upgrade_client,
) -> None:
    client, service = upgrade_client
    app_module.SECURITY_SERVICE.setup_pin("123456", "123456")

    response = client.post("/api/upgrade/migrate", json={})

    assert response.status_code == 409
    assert response.get_json() == {"error": "PIN_ALREADY_CONFIGURED"}
    assert service.calls == []


