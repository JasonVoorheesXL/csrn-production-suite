from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from flask import Flask

from routes.commercial_ux_routes import CommercialUxDependencies, create_commercial_ux_blueprint


@dataclass
class Result:
    code: str = "OK"
    data: dict | None = None

    @property
    def ok(self) -> bool:
        return self.code in {"OK", "AUTHORIZATION_READY", "CONNECTED", "CONNECTION_TESTED", "DISCONNECTED", "THEME_ACTIVATED"}

    def __post_init__(self):
        if self.data is None:
            self.data = {}


class Ux:
    def status(self):
        return Result(data={"setup": {"percent": 50}})

    def options(self):
        return Result(data={"themes": []})


class OAuth:
    def __init__(self):
        self.calls = []

    def start(self, provider, callback_url):
        self.calls.append(("start", provider, callback_url))
        return Result("AUTHORIZATION_READY", {"authorize_url": "https://provider.example/authorize"})

    def complete(self, provider, *, state_token, code):
        self.calls.append(("complete", provider, state_token, code))
        return Result("CONNECTED", {"provider": provider})

    def test_connection(self, provider):
        return Result("CONNECTION_TESTED", {"provider": provider, "ok": True})

    def disconnect(self, provider, confirmation):
        self.calls.append(("disconnect", provider, confirmation))
        return Result("DISCONNECTED", {"provider": provider})


class Theme:
    def activate(self, preset_id, overrides=None, *, confirmation=None):
        return Result("THEME_ACTIVATED", {"theme": {"id": preset_id}})


def build_app():
    oauth = OAuth()
    root = Path(__file__).resolve().parents[1]
    app = Flask(__name__, template_folder=str(root / "templates"), static_folder=str(root / "static"))

    def require_auth(view):
        view._csrn_requires_auth = True
        return view

    app.register_blueprint(
        create_commercial_ux_blueprint(
            CommercialUxDependencies(
                require_auth=require_auth,
                get_ux_service=lambda: Ux(),
                get_oauth_service=lambda: oauth,
                get_theme_service=lambda: Theme(),
            )
        )
    )
    app.testing = True
    return app, oauth


def test_setup_page_is_reachable_without_hidden_url_knowledge() -> None:
    app, _ = build_app()
    response = app.test_client().get("/setup")
    assert response.status_code == 200
    assert b"Setup & Integrations" in response.data
    assert b"Back to Command Center" in response.data


def test_setup_status_and_options_routes_return_guided_data() -> None:
    app, _ = build_app()
    client = app.test_client()
    assert client.get("/api/setup/status").get_json()["setup"]["percent"] == 50
    assert client.get("/api/setup/options").get_json()["themes"] == []


def test_oauth_start_uses_local_callback_route() -> None:
    app, oauth = build_app()
    response = app.test_client().post("/api/setup/oauth/x/start", json={})
    assert response.status_code == 200
    assert response.get_json()["authorize_url"].startswith("https://")
    assert oauth.calls[0][0:2] == ("start", "x")
    assert oauth.calls[0][2].endswith("/setup/oauth/x/callback")


def test_oauth_callback_redirects_to_setup_hub() -> None:
    app, oauth = build_app()
    response = app.test_client().get("/setup/oauth/x/callback?state=s&code=c")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/setup?connected=x")
    assert oauth.calls[-1] == ("complete", "x", "s", "c")


def test_connection_test_and_disconnect_routes() -> None:
    app, oauth = build_app()
    client = app.test_client()
    assert client.post("/api/setup/oauth/x/test", json={}).get_json()["ok"] is True
    response = client.post("/api/setup/oauth/x/disconnect", json={"confirmation": "DISCONNECT SOCIAL ACCOUNT"})
    assert response.status_code == 200
    assert oauth.calls[-1] == ("disconnect", "x", "DISCONNECT SOCIAL ACCOUNT")


def test_theme_selector_route_uses_controlled_preset_id() -> None:
    app, _ = build_app()
    response = app.test_client().post("/api/setup/theme", json={"preset_id": "modern_network"})
    assert response.status_code == 200
    assert response.get_json()["theme"]["id"] == "modern_network"


def test_all_setup_routes_are_authenticated_by_design() -> None:
    app, _ = build_app()
    setup_rules = [rule for rule in app.url_map.iter_rules() if rule.endpoint.startswith("commercial_ux_routes.")]
    assert len(setup_rules) >= 8
    for rule in setup_rules:
        assert getattr(app.view_functions[rule.endpoint], "_csrn_requires_auth", False)
