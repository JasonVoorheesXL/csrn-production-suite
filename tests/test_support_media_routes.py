from __future__ import annotations

import io

import pytest

import app as app_module
from support_media_service import SupportMediaResult


if not hasattr(app_module, "get_support_media_service"):
    pytest.skip(
        "SupportMediaService routes are not integrated yet.",
        allow_module_level=True,
    )


class StubSupportMediaService:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []
        self.upload_result = SupportMediaResult(
            "OK",
            {
                "headshot": "/roster-headshots/roster-1__player-1.png",
                "player": {"id": "player-1", "headshot": "/roster-headshots/roster-1__player-1.png"},
            },
        )
        self.info_result = SupportMediaResult(
            "OK",
            {
                "connection": {
                    "port": 5050,
                    "addresses": [
                        {"ip": "192.168.1.25", "url": "http://192.168.1.25:5050"}
                    ],
                    "localhost": "http://127.0.0.1:5050",
                    "guidance": "USB tethering guidance",
                }
            },
        )
        self.qr_result = SupportMediaResult(
            "OK",
            {
                "svg": b"<svg>qr</svg>",
                "mimetype": "image/svg+xml",
                "headers": {"Cache-Control": "no-store"},
            },
        )

    def upload_headshot(self, roster_id, player_id, *, original_filename, raw):
        self.calls.append(
            (
                "upload",
                {
                    "roster_id": roster_id,
                    "player_id": player_id,
                    "original_filename": original_filename,
                    "raw": raw,
                },
            )
        )
        return self.upload_result

    def connection_info(self, port=5050):
        self.calls.append(("connection", port))
        return self.info_result

    def qr_svg(self, url):
        self.calls.append(("qr", url))
        return self.qr_result


@pytest.fixture
def support_client(monkeypatch: pytest.MonkeyPatch):
    service = StubSupportMediaService()
    monkeypatch.setattr(app_module, "SUPPORT_MEDIA_SERVICE", service, raising=False)
    monkeypatch.setattr(app_module, "pin_is_configured", lambda: True)
    monkeypatch.setitem(app_module.app.config, "TESTING", True)
    monkeypatch.setitem(app_module.app.config, "SECRET_KEY", "support-media-route-test")
    with app_module.app.test_client() as client:
        with client.session_transaction() as active_session:
            active_session["authenticated"] = True
        yield client, service


def upload_request(client):
    return client.post(
        "/api/rosters/roster-1/players/player-1/headshot",
        data={"headshot": (io.BytesIO(b"image-bytes"), "portrait.png")},
        content_type="multipart/form-data",
    )


def test_headshot_route_requires_file(support_client) -> None:
    client, service = support_client
    response = client.post(
        "/api/rosters/roster-1/players/player-1/headshot",
        data={},
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    assert response.get_json() == {"error": "HEADSHOT_FILE_REQUIRED"}
    assert service.calls == []


def test_headshot_route_maps_validation_error(support_client) -> None:
    client, service = support_client
    service.upload_result = SupportMediaResult("UNSUPPORTED_IMAGE_TYPE", {})
    response = upload_request(client)
    assert response.status_code == 400
    assert response.get_json() == {"error": "UNSUPPORTED_IMAGE_TYPE"}


def test_headshot_route_maps_missing_roster(support_client) -> None:
    client, service = support_client
    service.upload_result = SupportMediaResult("ROSTER_NOT_FOUND", {})
    response = upload_request(client)
    assert response.status_code == 404
    assert response.get_json() == {"error": "ROSTER_NOT_FOUND"}


def test_headshot_route_maps_storage_failure(support_client) -> None:
    client, service = support_client
    service.upload_result = SupportMediaResult(
        "HEADSHOT_STORAGE_FAILED",
        {"message": "disk blocked"},
    )
    response = upload_request(client)
    assert response.status_code == 500
    assert response.get_json() == {
        "error": "HEADSHOT_STORAGE_FAILED",
        "message": "disk blocked",
    }


def test_headshot_route_delegates_successfully(support_client) -> None:
    client, service = support_client
    response = upload_request(client)
    assert response.status_code == 200
    assert response.get_json()["player"]["id"] == "player-1"
    call = service.calls[0]
    assert call[0] == "upload"
    assert call[1]["roster_id"] == "roster-1"
    assert call[1]["player_id"] == "player-1"
    assert call[1]["original_filename"] == "portrait.png"
    assert call[1]["raw"] == b"image-bytes"


def test_connection_info_route_delegates(support_client) -> None:
    client, service = support_client
    response = client.get("/api/connection-info")
    assert response.status_code == 200
    assert response.get_json()["port"] == 5050
    assert service.calls == [("connection", 5050)]


def test_connection_qr_route_maps_invalid_url(support_client) -> None:
    client, service = support_client
    service.qr_result = SupportMediaResult("INVALID_URL", {})
    response = client.get("/api/connection-qr?url=file:///tmp/test")
    assert response.status_code == 400
    assert response.get_json() == {"error": "INVALID_URL"}


def test_connection_qr_route_maps_generation_failure(support_client) -> None:
    client, service = support_client
    service.qr_result = SupportMediaResult(
        "QR_GENERATION_FAILED",
        {"message": "renderer failed"},
    )
    response = client.get("/api/connection-qr?url=http://192.168.1.25:5050")
    assert response.status_code == 500
    assert response.get_json() == {
        "error": "QR_GENERATION_FAILED",
        "message": "renderer failed",
    }


def test_connection_qr_route_returns_svg(support_client) -> None:
    client, service = support_client
    response = client.get("/api/connection-qr?url=http://192.168.1.25:5050")
    assert response.status_code == 200
    assert response.mimetype == "image/svg+xml"
    assert response.data == b"<svg>qr</svg>"
    assert response.headers["Cache-Control"] == "no-store"
    assert service.calls == [("qr", "http://192.168.1.25:5050")]
