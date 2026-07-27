from __future__ import annotations

import json
from pathlib import Path

from social_platforms import (
    EnvCredentialResolver,
    FacebookPageAdapter,
    HttpResponse,
    XPlatformAdapter,
)


def image_file(tmp_path: Path, *, size: int = 32) -> Path:
    path = tmp_path / "card.png"
    path.write_bytes(b"x" * size)
    return path


def test_environment_credential_resolver_reads_only_named_reference(monkeypatch) -> None:
    monkeypatch.setenv("CSRN_TEST_TOKEN", "secret-value")
    resolver = EnvCredentialResolver()
    assert resolver("CSRN_TEST_TOKEN") == "secret-value"
    assert resolver("") == ""


def test_x_publish_uploads_media_then_creates_post(tmp_path: Path) -> None:
    calls = []

    def transport(method, url, headers, body):
        calls.append((method, url, headers, body))
        if url.endswith("/2/media/upload"):
            payload = json.loads(body)
            assert payload["media_category"] == "tweet_image"
            assert payload["media"]
            return HttpResponse(201, {}, b'{"data":{"id":"media-1"}}')
        assert url.endswith("/2/tweets")
        assert json.loads(body)["media"]["media_ids"] == ["media-1"]
        return HttpResponse(201, {}, b'{"data":{"id":"post-1"}}')

    adapter = XPlatformAdapter(
        credential_resolver=lambda _ref: "token",
        transport=transport,
    )
    result = adapter.publish(
        {"credential_ref": "X_TOKEN", "username": "school"},
        text="Touchdown",
        image_path=image_file(tmp_path),
    )
    assert result.code == "PUBLISHED"
    assert result.post_id == "post-1"
    assert result.url.endswith("/school/status/post-1")
    assert len(calls) == 2
    assert all(call[2]["Authorization"] == "Bearer token" for call in calls)


def test_x_publish_requires_external_credential(tmp_path: Path) -> None:
    adapter = XPlatformAdapter(credential_resolver=lambda _ref: "")
    result = adapter.publish(
        {"credential_ref": "MISSING"},
        text="Touchdown",
        image_path=image_file(tmp_path),
    )
    assert result.code == "CREDENTIAL_UNAVAILABLE"


def test_x_publish_rejects_missing_image(tmp_path: Path) -> None:
    adapter = XPlatformAdapter(credential_resolver=lambda _ref: "token")
    result = adapter.publish(
        {"credential_ref": "X_TOKEN"},
        text="Touchdown",
        image_path=tmp_path / "missing.png",
    )
    assert result.code == "IMAGE_NOT_FOUND"


def test_x_publish_rejects_image_larger_than_five_megabytes(tmp_path: Path) -> None:
    path = image_file(tmp_path, size=(5 * 1024 * 1024) + 1)
    adapter = XPlatformAdapter(credential_resolver=lambda _ref: "token")
    assert adapter.publish({"credential_ref": "X_TOKEN"}, text="x", image_path=path).code == "IMAGE_TOO_LARGE"


def test_x_rate_limit_is_retryable(tmp_path: Path) -> None:
    adapter = XPlatformAdapter(
        credential_resolver=lambda _ref: "token",
        transport=lambda *_args: HttpResponse(429, {"Retry-After": "12"}, b'{"title":"Too Many Requests"}'),
    )
    result = adapter.publish(
        {"credential_ref": "X_TOKEN"},
        text="Touchdown",
        image_path=image_file(tmp_path),
    )
    assert result.code == "MEDIA_UPLOAD_FAILED"
    assert result.retryable is True
    assert result.retry_after == 12


def test_x_delete_uses_user_access_token() -> None:
    calls = []

    def transport(method, url, headers, body):
        calls.append((method, url, headers, body))
        return HttpResponse(200, {}, b'{"data":{"deleted":true}}')

    adapter = XPlatformAdapter(credential_resolver=lambda _ref: "token", transport=transport)
    result = adapter.delete({"credential_ref": "X_TOKEN"}, post_id="123")
    assert result.code == "DELETED"
    assert calls[0][0] == "DELETE"
    assert calls[0][1].endswith("/2/tweets/123")


def test_facebook_publish_uses_page_photo_endpoint(tmp_path: Path) -> None:
    calls = []

    def transport(method, url, headers, body):
        calls.append((method, url, headers, body))
        assert b'name="message"' in body
        assert b"Touchdown" in body
        assert b'name="source"' in body
        return HttpResponse(200, {}, b'{"id":"photo-1","post_id":"page_99"}')

    adapter = FacebookPageAdapter(
        credential_resolver=lambda _ref: "page-token",
        transport=transport,
    )
    result = adapter.publish(
        {
            "credential_ref": "FB_TOKEN",
            "page_id": "page",
            "api_version": "v25.0",
        },
        text="Touchdown",
        image_path=image_file(tmp_path),
    )
    assert result.code == "PUBLISHED"
    assert result.post_id == "page_99"
    assert calls[0][1].endswith("/v25.0/page/photos")
    assert calls[0][2]["Authorization"] == "Bearer page-token"


def test_facebook_requires_page_id(tmp_path: Path) -> None:
    adapter = FacebookPageAdapter(credential_resolver=lambda _ref: "token")
    result = adapter.publish(
        {"credential_ref": "FB_TOKEN"},
        text="Touchdown",
        image_path=image_file(tmp_path),
    )
    assert result.code == "PAGE_ID_REQUIRED"


def test_facebook_server_error_is_retryable(tmp_path: Path) -> None:
    adapter = FacebookPageAdapter(
        credential_resolver=lambda _ref: "token",
        transport=lambda *_args: HttpResponse(503, {}, b'{"error":{"message":"temporary"}}'),
    )
    result = adapter.publish(
        {"credential_ref": "FB_TOKEN", "page_id": "page"},
        text="Touchdown",
        image_path=image_file(tmp_path),
    )
    assert result.code == "POST_FAILED"
    assert result.retryable is True


def test_facebook_delete_uses_configured_graph_version() -> None:
    calls = []

    def transport(method, url, headers, body):
        calls.append((method, url, headers, body))
        return HttpResponse(200, {}, b'{"success":true}')

    adapter = FacebookPageAdapter(credential_resolver=lambda _ref: "token", transport=transport)
    result = adapter.delete(
        {"credential_ref": "FB_TOKEN", "api_version": "v25.0"},
        post_id="page_1",
    )
    assert result.code == "DELETED"
    assert calls[0][1].endswith("/v25.0/page_1")


def test_platform_results_never_echo_credential(tmp_path: Path) -> None:
    secret = "do-not-return"
    adapter = XPlatformAdapter(
        credential_resolver=lambda _ref: secret,
        transport=lambda *_args: HttpResponse(401, {}, b'{"title":"Unauthorized"}'),
    )
    result = adapter.publish(
        {"credential_ref": "X_TOKEN"},
        text="Touchdown",
        image_path=image_file(tmp_path),
    )
    assert secret not in repr(result)
