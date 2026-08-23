from __future__ import annotations

from flask import Flask

from routes.page_routes import PageRoutesDependencies, create_page_blueprint


def build_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(
            __import__("pathlib").Path(__file__).resolve().parents[1] / "templates"
        ),
    )
    app.config.update(TESTING=True, SECRET_KEY="page-route-test")
    app.register_blueprint(
        create_page_blueprint(
            PageRoutesDependencies(
                application_identity=lambda: {
                    "product": "CSRN Production Suite",
                    "version": "Version Test",
                    "build": "BUILD-TEST",
                }
            )
        )
    )
    return app


def test_page_blueprint_registers_preserved_urls() -> None:
    app = build_app()
    rules = {
        (rule.rule, tuple(sorted(rule.methods - {"HEAD", "OPTIONS"})))
        for rule in app.url_map.iter_rules()
    }
    assert ("/", ("GET",)) in rules
    assert ("/overlay", ("GET",)) in rules


def test_control_panel_renders_application_identity() -> None:
    app = build_app()
    with app.test_client() as client:
        response = client.get("/")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "CSRN Production Suite" in body
    assert "Version Test" in body
    assert "BUILD-TEST" in body


def test_overlay_page_remains_public() -> None:
    app = build_app()
    with app.test_client() as client:
        response = client.get("/overlay")
    assert response.status_code == 200
    assert "<!doctype html>" in response.get_data(as_text=True).lower()


