from __future__ import annotations

from dataclasses import dataclass, field
from functools import wraps
from pathlib import Path
from typing import Any, Callable

import pytest
from flask import Flask, jsonify, request

from routes.social_routes import SocialRoutesDependencies, create_social_blueprint


@dataclass(frozen=True)
class StubResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.code == "OK"


class StubService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.result = StubResult("OK", {"post": {"id": "social-1"}})

    def platform_status(self):
        self.calls.append(("status", None))
        return StubResult("OK", {"platforms": []})

    def list_posts(self, **filters):
        self.calls.append(("list", filters))
        return StubResult("OK", {"posts": []})

    def create_event_draft(self, payload):
        self.calls.append(("create", payload))
        return self.result

    def read(self, post_id):
        self.calls.append(("read", post_id))
        return self.result

    def update(self, post_id, payload):
        self.calls.append(("update", (post_id, payload)))
        return self.result

    def publish(self, post_id, payload):
        self.calls.append(("publish", (post_id, payload)))
        return self.result

    def retry(self, post_id, payload):
        self.calls.append(("retry", (post_id, payload)))
        return self.result

    def cancel(self, post_id):
        self.calls.append(("cancel", post_id))
        return self.result


@pytest.fixture
def social_client(tmp_path: Path):
    service = StubService()
    cards = tmp_path / "cards"
    cards.mkdir()
    (cards / "card.png").write_bytes(b"card")

    def require_auth(view: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(view)
        def protected(*args: Any, **kwargs: Any):
            if request.headers.get("X-Test-Auth") != "yes":
                return jsonify({"error": "AUTH_REQUIRED"}), 401
            return view(*args, **kwargs)

        return protected

    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="social-route-test")
    app.register_blueprint(
        create_social_blueprint(
            SocialRoutesDependencies(
                require_auth=require_auth,
                get_social_service=lambda: service,
                get_cards_dir=lambda: cards,
            )
        )
    )
    with app.test_client() as client:
        yield client, app, service


def auth_headers() -> dict[str, str]:
    return {"X-Test-Auth": "yes"}


def test_social_routes_register_preserved_contracts(social_client) -> None:
    _, app, _ = social_client
    rules = {
        (rule.rule, tuple(sorted(rule.methods - {"HEAD", "OPTIONS"})))
        for rule in app.url_map.iter_rules()
    }
    assert ("/api/social/status", ("GET",)) in rules
    assert ("/api/social/posts", ("GET",)) in rules
    assert ("/api/social/posts/event", ("POST",)) in rules
    assert ("/api/social/posts/<post_id>/publish", ("POST",)) in rules
    assert ("/social-cards/<filename>", ("GET",)) in rules


def test_social_routes_require_authentication(social_client) -> None:
    client, _, service = social_client
    response = client.get("/api/social/status")
    assert response.status_code == 401
    assert service.calls == []


def test_create_social_event_post_returns_created(social_client) -> None:
    client, _, service = social_client
    response = client.post(
        "/api/social/posts/event",
        json={"event_id": "event-1"},
        headers=auth_headers(),
    )
    assert response.status_code == 201
    assert response.get_json() == {"post": {"id": "social-1"}}
    assert service.calls == [("create", {"event_id": "event-1"})]


def test_create_social_event_post_maps_duplicate_conflict(social_client) -> None:
    client, _, service = social_client
    service.result = StubResult(
        "SOCIAL_DRAFT_EXISTS",
        {"post": {"id": "existing"}},
    )
    response = client.post(
        "/api/social/posts/event",
        json={"event_id": "event-1"},
        headers=auth_headers(),
    )
    assert response.status_code == 409
    assert response.get_json() == {
        "error": "SOCIAL_DRAFT_EXISTS",
        "post": {"id": "existing"},
    }


def test_publish_route_delegates_explicit_approval(social_client) -> None:
    client, _, service = social_client
    response = client.post(
        "/api/social/posts/social-1/publish",
        json={"confirm": True, "approved_by": "Jason"},
        headers=auth_headers(),
    )
    assert response.status_code == 200
    assert service.calls == [
        ("publish", ("social-1", {"approved_by": "Jason", "confirm": True}))
    ]


def test_social_card_file_is_authenticated_and_served(social_client) -> None:
    client, _, _ = social_client
    response = client.get("/social-cards/card.png", headers=auth_headers())
    assert response.status_code == 200
    assert response.data == b"card"
