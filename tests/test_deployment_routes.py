from __future__ import annotations

from types import SimpleNamespace

from flask import Flask

from routes.deployment_routes import DeploymentRoutesDependencies, create_deployment_blueprint


class Deployment:
    def __init__(self):
        self.calls = []
        self.result = SimpleNamespace(code="OK", data={"deployment": {}}, ok=True)

    def status(self):
        self.calls.append(("status",))
        return self.result

    def validate_update(self, package_root, *, allow_downgrade=False):
        self.calls.append(("validate", str(package_root), allow_downgrade))
        return self.result

    def prepare_update(self, package_root, *, confirmation=None):
        self.calls.append(("prepare", str(package_root), confirmation))
        return self.result

    def create_support_bundle(self, *, note=""):
        self.calls.append(("support", note))
        return self.result


class Entitlements:
    def __init__(self):
        self.calls = []
        self.result = SimpleNamespace(code="OK", data={"licensing": {}}, ok=True)

    def status(self):
        self.calls.append(("status",))
        return self.result

    def installation_request(self):
        self.calls.append(("request",))
        return self.result

    def install_license(self, payload):
        self.calls.append(("install", payload))
        return self.result

    def remove_license(self, confirmation):
        self.calls.append(("remove", confirmation))
        return self.result


def app_services():
    app = Flask("deployment_routes_test")
    app.config.update(TESTING=True)
    deployment = Deployment()
    entitlements = Entitlements()

    def require_auth(func):
        setattr(func, "_csrn_requires_auth", True)
        return func

    app.register_blueprint(
        create_deployment_blueprint(
            DeploymentRoutesDependencies(
                require_auth=require_auth,
                get_deployment_service=lambda: deployment,
                get_entitlement_service=lambda: entitlements,
            )
        )
    )
    return app, deployment, entitlements


def test_status_routes_call_services() -> None:
    app, deployment, entitlements = app_services()
    client = app.test_client()
    assert client.get("/api/deployment/status").status_code == 200
    assert client.get("/api/licensing/status").status_code == 200
    assert deployment.calls == [("status",)]
    assert entitlements.calls == [("status",)]


def test_activation_request_route() -> None:
    app, _, entitlements = app_services()
    assert app.test_client().get("/api/licensing/activation-request").status_code == 200
    assert entitlements.calls == [("request",)]


def test_install_license_passes_payload() -> None:
    app, _, entitlements = app_services()
    payload = {"license_id": "abc"}
    assert app.test_client().post("/api/licensing/install", json=payload).status_code == 200
    assert entitlements.calls == [("install", payload)]


def test_install_license_conflict_status() -> None:
    app, _, entitlements = app_services()
    entitlements.result = SimpleNamespace(code="SIGNATURE_INVALID", data={}, ok=False)
    assert app.test_client().post("/api/licensing/install", json={}).status_code == 409


def test_remove_license_confirmation_is_forwarded() -> None:
    app, _, entitlements = app_services()
    response = app.test_client().post(
        "/api/licensing/remove",
        json={"confirmation": "REMOVE CSRN LICENSE"},
    )
    assert response.status_code == 200
    assert entitlements.calls == [("remove", "REMOVE CSRN LICENSE")]


def test_validate_update_forwards_downgrade_flag() -> None:
    app, deployment, _ = app_services()
    response = app.test_client().post(
        "/api/deployment/update/validate",
        json={"package_root": "C:/update", "allow_downgrade": True},
    )
    assert response.status_code == 200
    assert deployment.calls[0][0] == "validate"
    assert deployment.calls[0][1].replace("\\", "/") == "C:/update"
    assert deployment.calls[0][2] is True


def test_prepare_update_conflict_returns_409() -> None:
    app, deployment, _ = app_services()
    deployment.result = SimpleNamespace(code="CONFIRMATION_REQUIRED", data={}, ok=False)
    response = app.test_client().post("/api/deployment/update/prepare", json={})
    assert response.status_code == 409


def test_support_bundle_note_is_forwarded() -> None:
    app, deployment, _ = app_services()
    response = app.test_client().post(
        "/api/deployment/support-bundle",
        json={"note": "OBS disconnected"},
    )
    assert response.status_code == 200
    assert deployment.calls == [("support", "OBS disconnected")]


def test_all_deployment_routes_are_authenticated() -> None:
    app, _, _ = app_services()
    endpoints = [rule.endpoint for rule in app.url_map.iter_rules() if rule.endpoint.startswith("deployment_routes.")]
    assert endpoints
    assert all(getattr(app.view_functions[name], "_csrn_requires_auth", False) for name in endpoints)
