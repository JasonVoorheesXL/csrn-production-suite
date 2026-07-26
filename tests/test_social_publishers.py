from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from social_publishers import FacebookPagePublisher, XPublisher


class RecordingTransport:
    def __init__(self, responses: list[tuple[int, dict[str, Any]]]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[str, str, dict[str, str], bytes | None, float]] = []

    def __call__(
        self,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout: float,
    ) -> tuple[int, dict[str, Any]]:
        self.calls.append((method, url, dict(headers), body, timeout))
        return self.responses.pop(0)


def test_x_publisher_reports_missing_configuration() -> None:
    result = XPublisher().publish(text="Touchdown")
    assert result.code == "PLATFORM_NOT_CONFIGURED"
    assert result.data["platform"] == "x"


def test_x_publisher_uploads_image_then_creates_post(tmp_path: Path) -> None:
    image = tmp_path / "card.png"
    image.write_bytes(b"png-bytes")
    transport = RecordingTransport(
        [
            (200, {"data": {"id": "media-1"}}),
            (201, {"data": {"id": "post-1", "text": "Touchdown"}}),
        ]
    )
    publisher = XPublisher(access_token="token", transport=transport)
    result = publisher.publish(text="Touchdown", media_path=image)
    assert result.ok is True
    assert result.data["external_id"] == "post-1"
    assert [call[1] for call in transport.calls] == [
        "https://api.x.com/2/media/upload",
        "https://api.x.com/2/tweets",
    ]
    assert b'"media_ids": ["media-1"]' in transport.calls[1][3]


def test_facebook_publisher_posts_text_to_page_feed() -> None:
    transport = RecordingTransport([(200, {"id": "page-post-1"})])
    publisher = FacebookPagePublisher(
        page_id="page-1",
        page_access_token="token",
        transport=transport,
    )
    result = publisher.publish(text="Final score")
    assert result.ok is True
    assert result.data["external_id"] == "page-post-1"
    assert transport.calls[0][1] == "https://graph.facebook.com/page-1/feed"
    assert transport.calls[0][2]["Content-Type"] == "application/x-www-form-urlencoded"
    assert transport.calls[0][3] == b"message=Final+score"


def test_facebook_publisher_posts_image_to_page_photos(tmp_path: Path) -> None:
    image = tmp_path / "card.png"
    image.write_bytes(b"image-data")
    transport = RecordingTransport([(200, {"post_id": "photo-post-1"})])
    publisher = FacebookPagePublisher(
        page_id="page-1",
        page_access_token="token",
        transport=transport,
    )
    result = publisher.publish(text="Turnover", media_path=image)
    assert result.ok is True
    assert result.data["external_id"] == "photo-post-1"
    method, url, headers, body, _ = transport.calls[0]
    assert method == "POST"
    assert url == "https://graph.facebook.com/page-1/photos"
    assert headers["Content-Type"].startswith("multipart/form-data; boundary=")
    assert b'name="caption"' in body
    assert b"Turnover" in body
    assert b"image-data" in body
