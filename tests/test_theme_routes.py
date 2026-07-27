from __future__ import annotations

from types import SimpleNamespace

from flask import Flask

from routes.theme_routes import ThemeRoutesDependencies, create_theme_blueprint


class Themes:
    def __init__(self):
        self.calls = []
        self.result = SimpleNamespace(code="OK", data={"theme": {}}, ok=True)

    def catalog(self):
        self.calls.append(("catalog",))
        return self.result

    def status(self):
        self.calls.append(("status",))
        return self.result

    def public_state(self):
        self.calls.append(("public",))
        return self.result

    def css(self):
        self.calls.append(("css",))
        return SimpleNamespace(code="OK", data={"css": ":root{--test:1}"}, ok=True)

    def preview(self, preset_id, overrides=None):
        self.calls.append(("preview", preset_id, overrides))
        return self.result

    def activate(self, preset_id, overrides=None, *, confirmation=None):
        self.calls.append(("activate", preset_id, overrides, confirmation))
        return self.result

    def set_lock(self, locked, confirmation):
        self.calls.append(("lock", locked, confirmation))
        return self.result

    def reset_overrides(self, *, confirmation=None):
        self.calls.append(("reset", confirmation))
        return self.result

    def save_variant(self, name, preset_id, overrides=None):
        self.calls.append(("save_variant", name, preset_id, overrides))
        return self.result

    def activate_variant(self, name, *, confirmation=None):
        self.calls.append(("activate_variant", name, confirmation))
        return self.result

    def delete_variant(self, name, confirmation):
        self.calls.append(("delete_variant", name, confirmation))
        return self.result


def app_service():
    app = Flask("theme_routes_test", template_folder="../templates")
    app.config.update(TESTING=True)
    themes = Themes()

    def require_auth(func):
        setattr(func, "_csrn_requires_auth", True)
        return func

    app.register_blueprint(
        create_theme_blueprint(
            ThemeRoutesDependencies(
                require_auth=require_auth,
                get_theme_service=lambda: themes,
            )
        )
    )
    return app, themes


def test_css_route_is_public_and_no_store() -> None:
    app, themes = app_service()
    response = app.test_client().get("/themes/current.css")
    assert response.status_code == 200
    assert response.mimetype == "text/css"
    assert response.headers["Cache-Control"] == "no-store, max-age=0"
    assert b"--test" in response.data
    assert themes.calls == [("css",)]


def test_public_state_route_is_public() -> None:
    app, themes = app_service()
    assert app.test_client().get("/api/themes/public-state").status_code == 200
    assert themes.calls == [("public",)]


def test_catalog_and_status_routes_call_service() -> None:
    app, themes = app_service()
    client = app.test_client()
    assert client.get("/api/themes/catalog").status_code == 200
    assert client.get("/api/themes/status").status_code == 200
    assert themes.calls == [("catalog",), ("status",)]


def test_preview_forwards_payload() -> None:
    app, themes = app_service()
    payload = {"preset_id": "modern_network", "overrides": {"radius_px": 4}}
    assert app.test_client().post("/api/themes/preview", json=payload).status_code == 200
    assert themes.calls == [("preview", "modern_network", {"radius_px": 4})]


def test_activate_forwards_locked_confirmation() -> None:
    app, themes = app_service()
    payload = {
        "preset_id": "digital_neon",
        "overrides": {},
        "confirmation": "CHANGE LOCKED SEASON THEME",
    }
    assert app.test_client().post("/api/themes/activate", json=payload).status_code == 200
    assert themes.calls == [
        ("activate", "digital_neon", {}, "CHANGE LOCKED SEASON THEME")
    ]


def test_lock_forwards_exact_values() -> None:
    app, themes = app_service()
    payload = {"locked": True, "confirmation": "LOCK SEASON THEME"}
    assert app.test_client().post("/api/themes/lock", json=payload).status_code == 200
    assert themes.calls == [("lock", True, "LOCK SEASON THEME")]


def test_save_variant_forwards_payload() -> None:
    app, themes = app_service()
    payload = {
        "name": "Home",
        "preset_id": "collegiate_traditional",
        "overrides": {"primary_color": "#990000"},
    }
    assert app.test_client().post("/api/themes/variants", json=payload).status_code == 200
    assert themes.calls == [
        ("save_variant", "Home", "collegiate_traditional", {"primary_color": "#990000"})
    ]


def test_activate_and_delete_variant_routes() -> None:
    app, themes = app_service()
    client = app.test_client()
    assert client.post(
        "/api/themes/variants/Home/activate",
        json={"confirmation": "CHANGE LOCKED SEASON THEME"},
    ).status_code == 200
    assert client.delete(
        "/api/themes/variants/Home",
        json={"confirmation": "DELETE THEME VARIANT"},
    ).status_code == 200
    assert themes.calls == [
        ("activate_variant", "Home", "CHANGE LOCKED SEASON THEME"),
        ("delete_variant", "Home", "DELETE THEME VARIANT"),
    ]


def test_service_errors_map_to_http_statuses() -> None:
    app, themes = app_service()
    client = app.test_client()
    themes.result = SimpleNamespace(code="PRESET_NOT_FOUND", data={}, ok=False)
    assert client.post("/api/themes/preview", json={}).status_code == 404
    themes.result = SimpleNamespace(code="OVERRIDES_INVALID", data={"errors": ["bad"]}, ok=False)
    assert client.post("/api/themes/activate", json={}).status_code == 400
    themes.result = SimpleNamespace(code="LOCKED_THEME_CONFIRMATION_REQUIRED", data={}, ok=False)
    assert client.post("/api/themes/activate", json={}).status_code == 409


def test_only_css_and_public_state_are_unauthenticated() -> None:
    app, _ = app_service()
    public = {
        "theme_routes.current_theme_css",
        "theme_routes.public_theme_state",
    }
    endpoints = {
        rule.endpoint
        for rule in app.url_map.iter_rules()
        if rule.endpoint.startswith("theme_routes.")
    }
    assert public <= endpoints
    for endpoint in endpoints - public:
        assert getattr(app.view_functions[endpoint], "_csrn_requires_auth", False)
