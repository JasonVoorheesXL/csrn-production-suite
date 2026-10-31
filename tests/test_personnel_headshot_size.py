"""Audit round 4 (2026-10-31): personnel headshots are shrunk on upload the
same way roster headshots have been since 2026-08-25, so a camera original
never lands on disk at full size.
"""
from __future__ import annotations

import io
from functools import wraps
from types import SimpleNamespace
from typing import Any

import pytest
from flask import Flask
from PIL import Image

from routes.personnel_routes import PersonnelRoutesDependencies, create_personnel_blueprint
from support_media_service import SupportMediaService


def _jpeg(width: int, height: int) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (200, 30, 50)).save(buffer, format="JPEG", quality=95)
    return buffer.getvalue()


def test_shrink_headshot_bytes() -> None:
    big = _jpeg(3000, 4000)
    shrunk = SupportMediaService.shrink_headshot_bytes(big, ".jpg")
    assert shrunk is not None and len(shrunk) < len(big)
    assert max(Image.open(io.BytesIO(shrunk)).size) == SupportMediaService.MAX_HEADSHOT_DIMENSION
    small = _jpeg(600, 800)
    assert SupportMediaService.shrink_headshot_bytes(small, ".jpg") == small
    assert SupportMediaService.shrink_headshot_bytes(b"not an image", ".jpg") is None


@pytest.fixture
def client(tmp_path):
    def require_auth(func):
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any):
            return func(*args, **kwargs)

        return wrapper

    attached: dict[str, str] = {}
    service = SimpleNamespace(
        attach_headshot=lambda pid, path: (
            attached.update({pid: path}) or SimpleNamespace(code="OK", data={"path": path})
        )
    )
    app = Flask(__name__)
    app.config.update(TESTING=True)
    app.register_blueprint(
        create_personnel_blueprint(
            PersonnelRoutesDependencies(
                require_auth=require_auth,
                get_personnel_service=lambda: service,
                get_headshots_dir=lambda: tmp_path,
                normalize_personnel_id=lambda value: value,
                shrink_headshot=SupportMediaService.shrink_headshot_bytes,
            )
        )
    )
    with app.test_client() as test_client:
        yield test_client, tmp_path


def test_upload_stores_a_camera_original_at_headshot_size(client) -> None:
    test_client, folder = client
    response = test_client.post(
        "/api/personnel/coach-smith/headshot",
        data={"file": (io.BytesIO(_jpeg(4000, 6000)), "coach.jpg")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 200
    stored = Image.open(folder / "coach-smith.jpg")
    assert max(stored.size) == SupportMediaService.MAX_HEADSHOT_DIMENSION


def test_upload_refuses_a_file_that_is_not_an_image(client) -> None:
    test_client, folder = client
    response = test_client.post(
        "/api/personnel/coach-smith/headshot",
        data={"file": (io.BytesIO(b"plain text"), "coach.png")},
        content_type="multipart/form-data",
    )
    assert response.status_code == 400
    assert response.get_json()["error"] == "INVALID_IMAGE"
    assert not any(folder.iterdir())


def test_app_wires_the_shrink() -> None:
    import app as app_module

    source = open(app_module.__file__, encoding="utf-8").read()
    assert "shrink_headshot=SupportMediaService.shrink_headshot_bytes," in source
