from __future__ import annotations

from flask import Flask

from operational_rehearsal_service import RehearsalResult
from routes.rehearsal_routes import (
    RehearsalRoutesDependencies,
    create_rehearsal_blueprint,
)


class Service:
    def __init__(self):
        self.calls = []
        self.result = RehearsalResult("OK", {"ok": True})

    def status(self):
        self.calls.append(("status",))
        return self.result

    def catalog(self):
        self.calls.append(("catalog",))
        return self.result

    def create_rehearsal(self, payload):
        self.calls.append(("create", payload))
        return self.result

    def update_drill(self, rehearsal_id, drill_key, payload):
        self.calls.append(("drill", rehearsal_id, drill_key, payload))
        return self.result

    def add_blocker(self, rehearsal_id, payload):
        self.calls.append(("add_blocker", rehearsal_id, payload))
        return self.result

    def update_blocker(self, rehearsal_id, blocker_id, payload):
        self.calls.append(("update_blocker", rehearsal_id, blocker_id, payload))
        return self.result

    def complete_rehearsal(self, rehearsal_id, payload):
        self.calls.append(("complete", rehearsal_id, payload))
        return self.result

    def reopen_rehearsal(self, rehearsal_id, payload):
        self.calls.append(("reopen", rehearsal_id, payload))
        return self.result

    def readiness(self):
        self.calls.append(("readiness",))
        return self.result

    def freeze_release(self, payload):
        self.calls.append(("freeze", payload))
        return self.result

    def unfreeze_release(self, payload):
        self.calls.append(("unfreeze", payload))
        return self.result

    def manifest(self):
        self.calls.append(("manifest",))
        return self.result


def app_and_service():
    app = Flask("rehearsal_routes_test")
    app.config.update(TESTING=True)
    service = Service()

    def require_auth(func):
        setattr(func, "_csrn_requires_auth", True)
        return func

    app.register_blueprint(
        create_rehearsal_blueprint(
            RehearsalRoutesDependencies(
                require_auth=require_auth,
                get_rehearsal_service=lambda: service,
            )
        )
    )
    return app, service


def test_status_and_catalog_routes_call_service() -> None:
    app, service = app_and_service()
    client = app.test_client()
    assert client.get("/api/game-day/rehearsals").status_code == 200
    assert client.get("/api/game-day/rehearsals/catalog").status_code == 200
    assert service.calls == [("status",), ("catalog",)]


def test_create_route_passes_payload_and_returns_created() -> None:
    app, service = app_and_service()
    response = app.test_client().post(
        "/api/game-day/rehearsals",
        json={"name": "Game One", "operator": "Producer"},
    )
    assert response.status_code == 201
    assert service.calls == [("create", {"name": "Game One", "operator": "Producer"})]


def test_create_validation_and_frozen_statuses() -> None:
    app, service = app_and_service()
    service.result = RehearsalResult("NAME_REQUIRED")
    assert app.test_client().post("/api/game-day/rehearsals", json={}).status_code == 400
    service.result = RehearsalResult("RELEASE_FROZEN")
    assert app.test_client().post("/api/game-day/rehearsals", json={}).status_code == 409


def test_drill_route_preserves_dotted_key() -> None:
    app, service = app_and_service()
    response = app.test_client().patch(
        "/api/game-day/rehearsals/r1/drills/failure.obs_disconnect",
        json={"result": "passed", "note": "Recovered"},
    )
    assert response.status_code == 200
    assert service.calls == [
        ("drill", "r1", "failure.obs_disconnect", {"note": "Recovered", "result": "passed"})
    ]


def test_drill_route_maps_validation_conflict_and_missing() -> None:
    app, service = app_and_service()
    client = app.test_client()
    service.result = RehearsalResult("DRILL_NOTE_REQUIRED")
    assert client.patch("/api/game-day/rehearsals/r1/drills/a", json={}).status_code == 400
    service.result = RehearsalResult("REHEARSAL_COMPLETED_LOCKED")
    assert client.patch("/api/game-day/rehearsals/r1/drills/a", json={}).status_code == 409
    service.result = RehearsalResult("DRILL_NOT_FOUND")
    assert client.patch("/api/game-day/rehearsals/r1/drills/a", json={}).status_code == 404


def test_blocker_routes_pass_identifiers_and_payloads() -> None:
    app, service = app_and_service()
    client = app.test_client()
    assert client.post(
        "/api/game-day/rehearsals/r1/blockers",
        json={"description": "Clipping"},
    ).status_code == 201
    assert client.patch(
        "/api/game-day/rehearsals/r1/blockers/b1",
        json={"status": "resolved", "resolution": "Gain reduced"},
    ).status_code == 200
    assert service.calls == [
        ("add_blocker", "r1", {"description": "Clipping"}),
        (
            "update_blocker",
            "r1",
            "b1",
            {"resolution": "Gain reduced", "status": "resolved"},
        ),
    ]


def test_complete_and_reopen_routes_call_service() -> None:
    app, service = app_and_service()
    client = app.test_client()
    assert client.post(
        "/api/game-day/rehearsals/r1/complete",
        json={"confirmation": "COMPLETE REHEARSAL", "signoff": "Producer"},
    ).status_code == 200
    assert client.post(
        "/api/game-day/rehearsals/r1/reopen",
        json={"confirmation": "REOPEN REHEARSAL"},
    ).status_code == 200
    assert service.calls[0][0] == "complete"
    assert service.calls[1][0] == "reopen"


def test_incomplete_rehearsal_returns_conflict() -> None:
    app, service = app_and_service()
    service.result = RehearsalResult("REHEARSAL_INCOMPLETE", {"missing_drills": ["a"]})
    response = app.test_client().post("/api/game-day/rehearsals/r1/complete", json={})
    assert response.status_code == 409
    assert response.get_json()["missing_drills"] == ["a"]


def test_release_readiness_returns_conflict_until_ready() -> None:
    app, service = app_and_service()
    service.result = RehearsalResult("RELEASE_NOT_READY", {"readiness": {"ready": False}})
    assert app.test_client().get("/api/game-day/release-readiness").status_code == 409
    service.result = RehearsalResult("OK", {"readiness": {"ready": True}})
    assert app.test_client().get("/api/game-day/release-readiness").status_code == 200


def test_freeze_route_maps_validation_and_not_ready() -> None:
    app, service = app_and_service()
    client = app.test_client()
    service.result = RehearsalResult("INVALID_RELEASE_COMMIT")
    assert client.post("/api/game-day/release-freeze", json={}).status_code == 400
    service.result = RehearsalResult("RELEASE_NOT_READY", {"readiness": {}})
    assert client.post("/api/game-day/release-freeze", json={}).status_code == 409


def test_unfreeze_and_manifest_statuses() -> None:
    app, service = app_and_service()
    client = app.test_client()
    service.result = RehearsalResult("RELEASE_NOT_FROZEN")
    assert client.post("/api/game-day/release-unfreeze", json={}).status_code == 409
    service.result = RehearsalResult("MANIFEST_NOT_FOUND")
    assert client.get("/api/game-day/release-manifest").status_code == 404


def test_all_rehearsal_routes_are_authenticated() -> None:
    app, _ = app_and_service()
    endpoints = [
        rule.endpoint
        for rule in app.url_map.iter_rules()
        if rule.endpoint.startswith("rehearsal_routes.")
    ]
    assert endpoints
    for endpoint in endpoints:
        assert getattr(app.view_functions[endpoint], "_csrn_requires_auth", False)


