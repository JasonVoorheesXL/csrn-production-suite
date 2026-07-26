from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest
from flask import Flask

from caption_service import CaptionServiceResult
from routes.caption_routes import CaptionRoutesDependencies, create_caption_blueprint


@dataclass
class StubCaptionService:
    profile_payload: Any = None
    segment_payload: Any = None
    visibility_value: Any = None
    correction: tuple[str, Any] | None = None
    calls: list[str] = field(default_factory=list)

    def status(self):
        self.calls.append("status")
        return CaptionServiceResult("OK", {"profile": {}, "state": {}})

    def public_state(self):
        self.calls.append("public_state")
        return CaptionServiceResult("OK", {"visible": True, "segments": []})

    def update_profile(self, payload):
        self.profile_payload = payload
        if payload is None:
            return CaptionServiceResult("PROFILE_REQUIRED")
        if payload.get("invalid"):
            return CaptionServiceResult("INVALID_PROFILE", {"message": "invalid"})
        return CaptionServiceResult("OK", {"profile": payload, "state": {}})

    def ingest_segment(self, payload):
        self.segment_payload = payload
        code = (payload or {}).get("result", "OK") if isinstance(payload, dict) else "SEGMENT_REQUIRED"
        if code == "OK":
            return CaptionServiceResult("OK", {"segment": payload, "state": {}})
        return CaptionServiceResult(code, {"minimum_confidence": 0.72} if code == "LOW_CONFIDENCE" else {})

    def set_visibility(self, visible):
        self.visibility_value = visible
        if not isinstance(visible, bool):
            return CaptionServiceResult("VISIBLE_MUST_BE_BOOLEAN")
        return CaptionServiceResult("OK", {"profile": {}, "state": {"visible": visible}})

    def clear(self):
        self.calls.append("clear")
        return CaptionServiceResult("OK", {"state": {"current": []}})

    def correct_segment(self, segment_id, text):
        self.correction = (segment_id, text)
        if not text:
            return CaptionServiceResult("TEXT_REQUIRED")
        if segment_id == "missing":
            return CaptionServiceResult("SEGMENT_NOT_FOUND")
        return CaptionServiceResult("OK", {"segment": {"id": segment_id, "text": text}})

    def transcript(self, broadcast_id):
        return CaptionServiceResult("OK", {"broadcast_id": broadcast_id, "segments": []})

    def export_srt(self, broadcast_id):
        return CaptionServiceResult("OK", {"content": f"SRT {broadcast_id}", "mimetype": "application/x-subrip"})

    def export_vtt(self, broadcast_id):
        return CaptionServiceResult("OK", {"content": f"VTT {broadcast_id}", "mimetype": "text/vtt"})


@pytest.fixture
def caption_client():
    app = Flask(__name__, template_folder="../templates")
    service = StubCaptionService()

    def require_auth(function):
        function._auth_required = True
        return function

    app.register_blueprint(
        create_caption_blueprint(
            CaptionRoutesDependencies(
                require_auth=require_auth,
                get_caption_service=lambda: service,
            )
        )
    )
    app.config["TESTING"] = True
    return app.test_client(), service


def test_public_overlay_page(caption_client) -> None:
    client, _ = caption_client
    response = client.get("/captions")
    assert response.status_code == 200
    assert b"CSRN Captions" in response.data


def test_public_overlay_state(caption_client) -> None:
    client, service = caption_client
    response = client.get("/api/captions/overlay-state")
    assert response.status_code == 200
    assert response.get_json()["visible"] is True
    assert service.calls == ["public_state"]


def test_status_route(caption_client) -> None:
    client, _ = caption_client
    assert client.get("/api/captions/status").status_code == 200


def test_profile_route(caption_client) -> None:
    client, service = caption_client
    response = client.put("/api/captions/profile", json={"enabled": True})
    assert response.status_code == 200
    assert service.profile_payload == {"enabled": True}


def test_profile_route_rejects_invalid(caption_client) -> None:
    client, _ = caption_client
    response = client.put("/api/captions/profile", json={"invalid": True})
    assert response.status_code == 400
    assert response.get_json()["error"] == "INVALID_PROFILE"


def test_ingest_route_created(caption_client) -> None:
    client, service = caption_client
    response = client.post("/api/captions/segments", json={"channel": 1, "text": "Hello"})
    assert response.status_code == 201
    assert service.segment_payload["channel"] == 1


def test_ingest_route_low_confidence_is_accepted_for_filtering(caption_client) -> None:
    client, _ = caption_client
    response = client.post("/api/captions/segments", json={"result": "LOW_CONFIDENCE"})
    assert response.status_code == 202


def test_ingest_route_disabled_channel_conflict(caption_client) -> None:
    client, _ = caption_client
    response = client.post("/api/captions/segments", json={"result": "CHANNEL_DISABLED"})
    assert response.status_code == 409


def test_visibility_route(caption_client) -> None:
    client, service = caption_client
    response = client.post("/api/captions/visibility", json={"visible": False})
    assert response.status_code == 200
    assert service.visibility_value is False


def test_visibility_route_requires_boolean(caption_client) -> None:
    client, _ = caption_client
    assert client.post("/api/captions/visibility", json={"visible": "yes"}).status_code == 400


def test_clear_route(caption_client) -> None:
    client, service = caption_client
    assert client.post("/api/captions/clear").status_code == 200
    assert "clear" in service.calls


def test_correction_route(caption_client) -> None:
    client, service = caption_client
    response = client.patch("/api/captions/segments/seg-1", json={"text": "Corrected"})
    assert response.status_code == 200
    assert service.correction == ("seg-1", "Corrected")


def test_correction_route_not_found(caption_client) -> None:
    client, _ = caption_client
    assert client.patch("/api/captions/segments/missing", json={"text": "Corrected"}).status_code == 404


def test_transcript_json_route(caption_client) -> None:
    client, _ = caption_client
    response = client.get("/api/captions/transcripts/game-1")
    assert response.status_code == 200
    assert response.get_json()["broadcast_id"] == "game-1"


def test_transcript_export_routes(caption_client) -> None:
    client, _ = caption_client
    srt = client.get("/api/captions/transcripts/game-1.srt")
    vtt = client.get("/api/captions/transcripts/game-1.vtt")
    assert srt.status_code == 200
    assert b"SRT game-1" in srt.data
    assert vtt.status_code == 200
    assert b"VTT game-1" in vtt.data
