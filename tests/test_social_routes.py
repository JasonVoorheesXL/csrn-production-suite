from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from flask import Flask

from routes.social_routes import SocialRoutesDependencies, create_social_blueprint


class Service:
    def __init__(self, tmp_path: Path):
        self.calls = []
        self.result = SimpleNamespace(code="OK", data={"social": {}}, ok=True)
        self.card = tmp_path / "card.png"
        self.card.write_bytes(b"png")

    def status(self):
        self.calls.append(("status",))
        return self.result

    def configure_account(self, data):
        self.calls.append(("account", data))
        return self.result

    def remove_account(self, account_id, confirmation):
        self.calls.append(("remove_account", account_id, confirmation))
        return self.result

    def update_settings(self, data):
        self.calls.append(("settings", data))
        return self.result

    def update_sponsor_rules(self, data):
        self.calls.append(("sponsors", data))
        return self.result

    def eligible_events(self):
        self.calls.append(("eligible",))
        return self.result

    def create_draft(self, kind, *, event_id="", payload=None, force_duplicate=False):
        self.calls.append(("create", kind, event_id, payload, force_duplicate))
        return self.result

    def read_draft(self, draft_id):
        self.calls.append(("read", draft_id))
        return self.result

    def update_draft(self, draft_id, data):
        self.calls.append(("update", draft_id, data))
        return self.result

    def delete_draft(self, draft_id, confirmation):
        self.calls.append(("delete", draft_id, confirmation))
        return self.result

    def approve_draft(self, draft_id, *, operator, confirmation):
        self.calls.append(("approve", draft_id, operator, confirmation))
        return self.result

    def publish_draft(self, draft_id, *, account_ids=None):
        self.calls.append(("publish", draft_id, account_ids))
        return self.result

    def manual_package(self, draft_id, platform="x"):
        self.calls.append(("manual", draft_id, platform))
        return self.result

    def process_auto_queue(self, *, limit=10):
        self.calls.append(("auto", limit))
        return self.result

    def create_correction(self, draft_id, data):
        self.calls.append(("correction", draft_id, data))
        return self.result

    def retract_publication(self, draft_id, account_id, confirmation):
        self.calls.append(("retract", draft_id, account_id, confirmation))
        return self.result

    def card_path(self, draft_id, platform):
        self.calls.append(("card", draft_id, platform))
        return SimpleNamespace(code="OK", data={"path": str(self.card), "filename": self.card.name}, ok=True)

    def postgame_handoff(self):
        self.calls.append(("handoff",))
        return self.result


class FacebookService:
    def __init__(self):
        self.calls = []
        self.result = SimpleNamespace(code="OK", data={"facebook": {}}, ok=True)

    def status(self):
        self.calls.append(("facebook_status",))
        return self.result

    def configure_app(self, data):
        self.calls.append(("configure_app", data))
        return self.result

    def remove_app_configuration(self, confirmation):
        self.calls.append(("remove_app", confirmation))
        return self.result

    def authorization_url(self, state):
        self.calls.append(("authorization_url", state))
        return SimpleNamespace(code="AUTHORIZATION_READY", data={"authorization_url": "https://www.facebook.com/test"}, ok=True)

    def complete_authorization(self, **kwargs):
        self.calls.append(("complete_authorization", kwargs))
        return SimpleNamespace(code="OK", data={"selection_id": "selection-1", "warning": ""}, ok=True)

    def pending_pages(self, selection_id):
        self.calls.append(("pending_pages", selection_id))
        return SimpleNamespace(code="OK", data={"pages": [{"id": "page-1", "name": "Page"}]}, ok=True)

    def connect_page(self, selection_id, page_id):
        self.calls.append(("connect_page", selection_id, page_id))
        return self.result

    def test_connection(self):
        self.calls.append(("test_connection",))
        return self.result

    def disconnect(self, confirmation):
        self.calls.append(("disconnect", confirmation))
        return self.result


def app_service(tmp_path: Path):
    app = Flask("social_routes_test", template_folder=str(Path(__file__).resolve().parents[1] / "templates"))
    app.config.update(TESTING=True)
    service = Service(tmp_path)
    facebook = FacebookService()

    def require_auth(func):
        setattr(func, "_csrn_requires_auth", True)
        return func

    app.register_blueprint(
        create_social_blueprint(
            SocialRoutesDependencies(
                require_auth=require_auth,
                get_social_service=lambda: service,
                get_facebook_connection_service=lambda: facebook,
            )
        )
    )
    app.config["FACEBOOK_TEST_SERVICE"] = facebook
    return app, service


def test_manager_page_renders(tmp_path: Path) -> None:
    app, _ = app_service(tmp_path)
    response = app.test_client().get("/social")
    assert response.status_code == 200
    assert b"Social Publishing" in response.data


def test_status_calls_service(tmp_path: Path) -> None:
    app, service = app_service(tmp_path)
    assert app.test_client().get("/api/social/status").status_code == 200
    assert service.calls == [("status",)]


def test_account_payload_is_forwarded(tmp_path: Path) -> None:
    app, service = app_service(tmp_path)
    payload = {"id": "facebook-primary", "platform": "facebook", "page_id": "page-1"}
    assert app.test_client().post("/api/social/accounts", json=payload).status_code == 200
    assert service.calls == [("account", payload)]


def test_account_remove_confirmation_is_forwarded(tmp_path: Path) -> None:
    app, service = app_service(tmp_path)
    response = app.test_client().delete(
        "/api/social/accounts/facebook-primary",
        json={"confirmation": "REMOVE SOCIAL ACCOUNT"},
    )
    assert response.status_code == 200
    assert service.calls == [("remove_account", "facebook-primary", "REMOVE SOCIAL ACCOUNT")]


def test_create_draft_forwards_event_and_payload(tmp_path: Path) -> None:
    app, service = app_service(tmp_path)
    payload = {"kind": "TOUCHDOWN", "event_id": "EV-1", "payload": {"message": "Touchdown"}}
    assert app.test_client().post("/api/social/drafts", json=payload).status_code == 200
    assert service.calls == [("create", "TOUCHDOWN", "EV-1", {"message": "Touchdown"}, False)]


def test_approval_phrase_is_forwarded(tmp_path: Path) -> None:
    app, service = app_service(tmp_path)
    payload = {"operator": "Alex", "confirmation": "APPROVE SOCIAL POST"}
    assert app.test_client().post("/api/social/drafts/SOC-1/approve", json=payload).status_code == 200
    assert service.calls == [("approve", "SOC-1", "Alex", "APPROVE SOCIAL POST")]


def test_publish_account_selection_is_forwarded(tmp_path: Path) -> None:
    app, service = app_service(tmp_path)
    assert app.test_client().post("/api/social/drafts/SOC-1/publish", json={"account_ids": ["facebook-primary"]}).status_code == 200
    assert service.calls == [("publish", "SOC-1", ["facebook-primary"])]


def test_correction_and_retraction_are_forwarded(tmp_path: Path) -> None:
    app, service = app_service(tmp_path)
    client = app.test_client()
    assert client.post("/api/social/drafts/SOC-1/corrections", json={"detail": "Corrected"}).status_code == 200
    assert client.post(
        "/api/social/drafts/SOC-1/publications/facebook-primary/retract",
        json={"confirmation": "RETRACT SOCIAL POST"},
    ).status_code == 200
    assert service.calls == [
        ("correction", "SOC-1", {"detail": "Corrected"}),
        ("retract", "SOC-1", "facebook-primary", "RETRACT SOCIAL POST"),
    ]



def test_manual_x_package_route_is_forwarded(tmp_path: Path) -> None:
    app, service = app_service(tmp_path)
    response = app.test_client().get("/api/social/drafts/SOC-1/manual/x")
    assert response.status_code == 200
    assert service.calls == [("manual", "SOC-1", "x")]

def test_card_route_sends_png(tmp_path: Path) -> None:
    app, service = app_service(tmp_path)
    response = app.test_client().get("/api/social/drafts/SOC-1/cards/x")
    assert response.status_code == 200
    assert response.mimetype == "image/png"
    assert service.calls == [("card", "SOC-1", "x")]


def test_service_conflict_maps_to_409(tmp_path: Path) -> None:
    app, service = app_service(tmp_path)
    service.result = SimpleNamespace(code="APPROVAL_CONFIRMATION_REQUIRED", data={}, ok=False)
    assert app.test_client().post("/api/social/drafts/SOC-1/approve", json={}).status_code == 409



def test_x_manual_only_maps_to_400(tmp_path: Path) -> None:
    app, service = app_service(tmp_path)
    service.result = SimpleNamespace(code="X_MANUAL_ONLY", data={"message": "manual"}, ok=False)
    response = app.test_client().post("/api/social/accounts", json={"platform": "x"})
    assert response.status_code == 400

def test_raw_credential_rejection_maps_to_400(tmp_path: Path) -> None:
    app, service = app_service(tmp_path)
    service.result = SimpleNamespace(code="RAW_CREDENTIAL_REJECTED", data={"fields": ["access_token"]}, ok=False)
    response = app.test_client().post("/api/social/accounts", json={"access_token": "secret"})
    assert response.status_code == 400
    assert response.get_json()["error"] == "RAW_CREDENTIAL_REJECTED"


def test_only_facebook_oauth_callback_is_public(tmp_path: Path) -> None:
    app, _ = app_service(tmp_path)
    endpoints = [rule.endpoint for rule in app.url_map.iter_rules() if rule.endpoint.startswith("social_routes.")]
    assert endpoints
    public = {
        name
        for name in endpoints
        if not getattr(app.view_functions[name], "_csrn_requires_auth", False)
    }
    assert public == {"social_routes.complete_facebook_connection"}


def test_facebook_status_route(tmp_path: Path) -> None:
    app, _ = app_service(tmp_path)
    response = app.test_client().get("/api/social/facebook/status")
    assert response.status_code == 200
    facebook = app.config["FACEBOOK_TEST_SERVICE"]
    assert facebook.calls == [("facebook_status",)]


def test_facebook_app_configuration_route(tmp_path: Path) -> None:
    app, _ = app_service(tmp_path)
    payload = {"app_id": "123", "app_secret": "secret"}
    response = app.test_client().post("/api/social/facebook/app", json=payload)
    assert response.status_code == 200
    facebook = app.config["FACEBOOK_TEST_SERVICE"]
    assert facebook.calls == [("configure_app", payload)]


def test_facebook_page_selection_route(tmp_path: Path) -> None:
    app, _ = app_service(tmp_path)
    response = app.test_client().post(
        "/api/social/facebook/select",
        json={"selection_id": "selection-1", "page_id": "page-1"},
    )
    assert response.status_code == 200
    facebook = app.config["FACEBOOK_TEST_SERVICE"]
    assert facebook.calls == [("connect_page", "selection-1", "page-1")]


