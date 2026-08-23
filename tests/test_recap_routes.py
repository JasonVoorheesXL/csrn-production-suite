from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from flask import Flask

from routes.recap_routes import RecapRoutesDependencies, create_recap_blueprint


class Service:
    def __init__(self):
        self.calls = []
        self.result = SimpleNamespace(code="OK", data={"recaps": []}, ok=True)

    def status(self):
        self.calls.append(("status",))
        return self.result

    def generate(self, *, regenerate=False, article_style="local_sports"):
        self.calls.append(("generate", regenerate, article_style))
        return self.result

    def read(self, recap_id):
        self.calls.append(("read", recap_id))
        return self.result

    def update(self, recap_id, data):
        self.calls.append(("update", recap_id, data))
        return self.result

    def approve(self, recap_id, *, operator, confirmation):
        self.calls.append(("approve", recap_id, operator, confirmation))
        return self.result

    def grounding_report(self, recap_id):
        self.calls.append(("grounding", recap_id))
        return self.result

    def create_social_final_draft(self, recap_id):
        self.calls.append(("social", recap_id))
        return self.result

    def export_text(self, recap_id):
        self.calls.append(("export", recap_id))
        return SimpleNamespace(code="OK", data={"text": "Recap\n", "filename": "recap.txt"}, ok=True)

    def delete(self, recap_id, confirmation):
        self.calls.append(("delete", recap_id, confirmation))
        return self.result


def app_service():
    templates = str(Path(__file__).resolve().parents[1] / "templates")
    app = Flask("recap_routes_test", template_folder=templates)
    app.config.update(TESTING=True)
    service = Service()

    def require_auth(func):
        setattr(func, "_csrn_requires_auth", True)
        return func

    app.register_blueprint(
        create_recap_blueprint(
            RecapRoutesDependencies(
                require_auth=require_auth,
                get_recap_service=lambda: service,
            )
        )
    )
    return app, service


def test_manager_page_renders() -> None:
    app, _ = app_service()
    response = app.test_client().get("/recaps")
    assert response.status_code == 200
    assert b"Grounded Game Recap" in response.data


def test_generate_forwards_regenerate_flag() -> None:
    app, service = app_service()
    response = app.test_client().post(
        "/api/recaps/generate",
        json={"regenerate": True, "article_style": "straight_news"},
    )
    assert response.status_code == 200
    assert service.calls == [("generate", True, "straight_news")]


def test_update_forwards_editable_fields() -> None:
    app, service = app_service()
    payload = {"headline": "Updated", "body": "Body"}
    response = app.test_client().patch("/api/recaps/RECAP-1", json=payload)
    assert response.status_code == 200
    assert service.calls == [("update", "RECAP-1", payload)]


def test_approve_forwards_exact_confirmation() -> None:
    app, service = app_service()
    payload = {"operator": "Jason", "confirmation": "APPROVE GROUNDED RECAP"}
    response = app.test_client().post("/api/recaps/RECAP-1/approve", json=payload)
    assert response.status_code == 200
    assert service.calls == [("approve", "RECAP-1", "Jason", "APPROVE GROUNDED RECAP")]


def test_grounding_and_social_routes_forward() -> None:
    app, service = app_service()
    client = app.test_client()
    assert client.get("/api/recaps/RECAP-1/grounding").status_code == 200
    assert client.post("/api/recaps/RECAP-1/social-draft", json={}).status_code == 200
    assert service.calls == [("grounding", "RECAP-1"), ("social", "RECAP-1")]


def test_export_returns_attachment() -> None:
    app, service = app_service()
    response = app.test_client().get("/api/recaps/RECAP-1/export.txt")
    assert response.status_code == 200
    assert response.mimetype.startswith("text/plain")
    assert "attachment" in response.headers["Content-Disposition"]
    assert service.calls == [("export", "RECAP-1")]


def test_conflict_maps_to_409() -> None:
    app, service = app_service()
    service.result = SimpleNamespace(code="RECAP_STALE", data={}, ok=False)
    response = app.test_client().post(
        "/api/recaps/RECAP-1/approve",
        json={"confirmation": "APPROVE GROUNDED RECAP"},
    )
    assert response.status_code == 409
    assert response.get_json()["error"] == "RECAP_STALE"


def test_all_recap_routes_are_authenticated() -> None:
    app, _ = app_service()
    endpoints = [rule.endpoint for rule in app.url_map.iter_rules() if rule.endpoint.startswith("recap_routes.")]
    assert endpoints
    assert all(getattr(app.view_functions[name], "_csrn_requires_auth", False) for name in endpoints)


