from __future__ import annotations

from dataclasses import dataclass
from functools import wraps
from typing import Any

import pytest
from flask import Flask, jsonify

from recovery_service import RecoveryResult
from routes.recovery_routes import (
    RecoveryRoutesDependencies,
    create_recovery_blueprint,
)


@dataclass
class StubRecoveryService:
    result: RecoveryResult = RecoveryResult("OK", {"recovery": {}})
    calls: list[tuple[str, Any]] | None = None

    def __post_init__(self) -> None:
        self.calls = []

    def status(self):
        self.calls.append(("status", None))
        return self.result

    def rehearse_restore(self, snapshot_id: str):
        self.calls.append(("rehearse", snapshot_id))
        return self.result

    def restore_snapshot(self, snapshot_id: str, *, confirmation: str, note: str):
        self.calls.append(("restore", (snapshot_id, confirmation, note)))
        return self.result

    def clear_unclean_shutdown(self):
        self.calls.append(("clear", None))
        return self.result

    def register_known_good(self, *, commit: str, note: str):
        self.calls.append(("known_good", (commit, note)))
        return self.result

    def rollback_plan(self):
        self.calls.append(("plan", None))
        return self.result


@pytest.fixture
def recovery_client():
    app = Flask("test_recovery_routes")
    app.config.update(TESTING=True)
    service = StubRecoveryService()

    def require_auth(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if not app.config.get("AUTHENTICATED", True):
                return jsonify({"error": "AUTH_REQUIRED"}), 401
            return func(*args, **kwargs)

        setattr(wrapper, "_csrn_requires_auth", True)
        return wrapper

    app.register_blueprint(
        create_recovery_blueprint(
            RecoveryRoutesDependencies(
                require_auth=require_auth,
                get_recovery_service=lambda: service,
            )
        )
    )
    return app.test_client(), app, service


def test_status_returns_recovery_payload(recovery_client) -> None:
    client, _, service = recovery_client
    service.result = RecoveryResult("OK", {"recovery": {"ready": True}})
    response = client.get("/api/game-day/recovery/status")
    assert response.status_code == 200
    assert response.get_json()["recovery"]["ready"] is True


def test_routes_require_authentication(recovery_client) -> None:
    client, app, _ = recovery_client
    app.config["AUTHENTICATED"] = False
    assert client.get("/api/game-day/recovery/status").status_code == 401


def test_rehearsal_maps_missing_snapshot_to_404(recovery_client) -> None:
    client, _, service = recovery_client
    service.result = RecoveryResult("SNAPSHOT_NOT_FOUND")
    response = client.post("/api/game-day/recovery/snapshots/missing/rehearse")
    assert response.status_code == 404


def test_restore_passes_confirmation_and_note(recovery_client) -> None:
    client, _, service = recovery_client
    service.result = RecoveryResult("SNAPSHOT_RESTORED", {"restore": {}})
    response = client.post(
        "/api/game-day/recovery/snapshots/snap-1/restore",
        json={"confirm_snapshot_id": "snap-1", "note": "Operator approved"},
    )
    assert response.status_code == 200
    assert service.calls[-1] == (
        "restore",
        ("snap-1", "snap-1", "Operator approved"),
    )


def test_restore_confirmation_failure_is_400(recovery_client) -> None:
    client, _, service = recovery_client
    service.result = RecoveryResult("RESTORE_CONFIRMATION_REQUIRED")
    response = client.post(
        "/api/game-day/recovery/snapshots/snap-1/restore",
        json={},
    )
    assert response.status_code == 400


def test_live_restore_lockout_is_409(recovery_client) -> None:
    client, _, service = recovery_client
    service.result = RecoveryResult("LIVE_BROADCAST_ACTIVE")
    response = client.post(
        "/api/game-day/recovery/snapshots/snap-1/restore",
        json={"confirm_snapshot_id": "snap-1"},
    )
    assert response.status_code == 409


def test_register_known_good_validates_commit(recovery_client) -> None:
    client, _, service = recovery_client
    service.result = RecoveryResult("INVALID_RELEASE_COMMIT")
    response = client.post(
        "/api/game-day/recovery/known-good",
        json={"commit": "bad"},
    )
    assert response.status_code == 400


def test_rollback_plan_without_release_is_404(recovery_client) -> None:
    client, _, service = recovery_client
    service.result = RecoveryResult("KNOWN_GOOD_NOT_SET")
    response = client.get("/api/game-day/recovery/rollback-plan")
    assert response.status_code == 404


def test_clear_unclean_shutdown(recovery_client) -> None:
    client, _, service = recovery_client
    service.result = RecoveryResult("UNCLEAN_MARKER_CLEARED", {"previous": {}})
    response = client.delete("/api/game-day/recovery/unclean-shutdown")
    assert response.status_code == 200
    assert service.calls[-1][0] == "clear"
