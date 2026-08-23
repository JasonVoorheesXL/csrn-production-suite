from __future__ import annotations

from dataclasses import dataclass, field
from functools import wraps
from io import BytesIO
from pathlib import Path
from typing import Any, Callable

import pytest
from flask import Flask, jsonify, request

from routes.support_routes import (
    SupportRoutesDependencies,
    create_support_blueprint,
)


@dataclass(frozen=True)
class StubResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)


class StubSupportMediaService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.upload_result = StubResult(
            "OK",
            {
                "headshot": "/roster-headshots/player-1.png",
                "player": {"id": "player-1", "headshot": "/roster-headshots/player-1.png"},
            },
        )
        self.connection_result = StubResult(
            "OK",
            {
                "connection": {
                    "port": 5050,
                    "addresses": ["http://127.0.0.1:5050"],
                }
            },
        )
        self.qr_result = StubResult(
            "OK",
            {
                "svg": "<svg>ready</svg>",
                "mimetype": "image/svg+xml",
                "headers": {"Cache-Control": "no-store"},
            },
        )

    def upload_headshot(
        self,
        roster_id: str,
        player_id: str,
        *,
        original_filename: str,
        raw: bytes,
    ) -> StubResult:
        self.calls.append(
            (
                "upload_headshot",
                {
                    "roster_id": roster_id,
                    "player_id": player_id,
                    "original_filename": original_filename,
                    "raw": raw,
                },
            )
        )
        return self.upload_result

    def connection_info(self, port: int) -> StubResult:
        self.calls.append(("connection_info", port))
        return self.connection_result

    def qr_svg(self, url: str) -> StubResult:
        self.calls.append(("qr_svg", url))
        return self.qr_result


@pytest.fixture
def support_client(tmp_path: Path):
    service = StubSupportMediaService()

    def require_auth(view: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(view)
        def protected(*args: Any, **kwargs: Any):
            if request.headers.get("X-Test-Auth") != "yes":
                return jsonify({"error": "AUTH_REQUIRED"}), 401
            return view(*args, **kwargs)

        return protected

    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="support-route-test")
    app.register_blueprint(
        create_support_blueprint(
            SupportRoutesDependencies(
                require_auth=require_auth,
                get_support_media_service=lambda: service,
                get_headshots_dir=lambda: tmp_path,
                connection_port=5050,
            )
        )
    )
    with app.test_client() as client:
        yield client, app, service, tmp_path


def auth_headers() -> dict[str, str]:
    return {"X-Test-Auth": "yes"}


def test_support_blueprint_registers_preserved_urls(support_client) -> None:
    _, app, _, _ = support_client
    rules = {
        (rule.rule, tuple(sorted(rule.methods - {"HEAD", "OPTIONS"})))
        for rule in app.url_map.iter_rules()
    }
    assert ("/roster-headshots/<filename>", ("GET",)) in rules
    assert (
        "/api/rosters/<roster_id>/players/<player_id>/headshot",
        ("POST",),
    ) in rules
    assert ("/api/connection-info", ("GET",)) in rules
    assert ("/api/connection-qr", ("GET",)) in rules


def test_roster_headshot_file_remains_public(support_client) -> None:
    client, _, _, headshots_dir = support_client
    (headshots_dir / "player.png").write_bytes(b"image-bytes")
    response = client.get("/roster-headshots/player.png")
    assert response.status_code == 200
    assert response.data == b"image-bytes"


def test_protected_support_route_requires_authentication(support_client) -> None:
    client, _, service, _ = support_client
    response = client.get("/api/connection-info")
    assert response.status_code == 401
    assert response.get_json() == {"error": "AUTH_REQUIRED"}
    assert service.calls == []


def test_headshot_upload_requires_file(support_client) -> None:
    client, _, service, _ = support_client
    response = client.post(
        "/api/rosters/roster-1/players/player-1/headshot",
        data={},
        headers=auth_headers(),
    )
    assert response.status_code == 400
    assert response.get_json() == {"error": "HEADSHOT_FILE_REQUIRED"}
    assert service.calls == []


def test_headshot_upload_maps_validation_error(support_client) -> None:
    client, _, service, _ = support_client
    service.upload_result = StubResult("INVALID_IMAGE")
    response = client.post(
        "/api/rosters/roster-1/players/player-1/headshot",
        data={"headshot": (BytesIO(b"bad"), "bad.png")},
        headers=auth_headers(),
    )
    assert response.status_code == 400
    assert response.get_json() == {"error": "INVALID_IMAGE"}


def test_headshot_upload_maps_missing_record(support_client) -> None:
    client, _, service, _ = support_client
    service.upload_result = StubResult("PLAYER_NOT_FOUND")
    response = client.post(
        "/api/rosters/roster-1/players/missing/headshot",
        data={"headshot": (BytesIO(b"png"), "player.png")},
        headers=auth_headers(),
    )
    assert response.status_code == 404
    assert response.get_json() == {"error": "PLAYER_NOT_FOUND"}


def test_headshot_upload_maps_storage_failure(support_client) -> None:
    client, _, service, _ = support_client
    service.upload_result = StubResult(
        "HEADSHOT_STORAGE_FAILED",
        {"message": "disk full"},
    )
    response = client.post(
        "/api/rosters/roster-1/players/player-1/headshot",
        data={"headshot": (BytesIO(b"png"), "player.png")},
        headers=auth_headers(),
    )
    assert response.status_code == 500
    assert response.get_json() == {
        "error": "HEADSHOT_STORAGE_FAILED",
        "message": "disk full",
    }


def test_headshot_upload_preserves_success_payload(support_client) -> None:
    client, _, service, _ = support_client
    response = client.post(
        "/api/rosters/roster-1/players/player-1/headshot",
        data={"headshot": (BytesIO(b"png"), "player.png")},
        headers=auth_headers(),
    )
    assert response.status_code == 200
    assert response.get_json() == {
        "headshot": "/roster-headshots/player-1.png",
        "player": {
            "id": "player-1",
            "headshot": "/roster-headshots/player-1.png",
        },
    }
    assert service.calls == [
        (
            "upload_headshot",
            {
                "roster_id": "roster-1",
                "player_id": "player-1",
                "original_filename": "player.png",
                "raw": b"png",
            },
        )
    ]


def test_connection_info_delegates_configured_port(support_client) -> None:
    client, _, service, _ = support_client
    response = client.get("/api/connection-info", headers=auth_headers())
    assert response.status_code == 200
    assert response.get_json() == {
        "port": 5050,
        "addresses": ["http://127.0.0.1:5050"],
    }
    assert service.calls == [("connection_info", 5050)]


def test_connection_qr_maps_invalid_url(support_client) -> None:
    client, _, service, _ = support_client
    service.qr_result = StubResult("INVALID_URL")
    response = client.get(
        "/api/connection-qr?url=bad",
        headers=auth_headers(),
    )
    assert response.status_code == 400
    assert response.get_json() == {"error": "INVALID_URL"}
    assert service.calls == [("qr_svg", "bad")]


def test_connection_qr_maps_generation_failure(support_client) -> None:
    client, _, service, _ = support_client
    service.qr_result = StubResult(
        "QR_GENERATION_FAILED",
        {"message": "encoder unavailable"},
    )
    response = client.get(
        "/api/connection-qr?url=http://127.0.0.1:5050",
        headers=auth_headers(),
    )
    assert response.status_code == 500
    assert response.get_json() == {
        "error": "QR_GENERATION_FAILED",
        "message": "encoder unavailable",
    }


def test_connection_qr_preserves_svg_response(support_client) -> None:
    client, _, service, _ = support_client
    url = "http://127.0.0.1:5050"
    response = client.get(
        f"/api/connection-qr?url={url}",
        headers=auth_headers(),
    )
    assert response.status_code == 200
    assert response.get_data(as_text=True) == "<svg>ready</svg>"
    assert response.mimetype == "image/svg+xml"
    assert response.headers["Cache-Control"] == "no-store"
    assert service.calls == [("qr_svg", url)]


