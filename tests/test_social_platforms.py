from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from social_platforms import (
    EnvCredentialResolver,
    FacebookPageAdapter,
    HttpResponse,
    build_x_compose_url,
    default_adapter_registry,
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


def test_x_compose_url_is_public_manual_intent_only() -> None:
    url = build_x_compose_url("FINAL: Home 21, Visitor 14.")
    parsed = urlparse(url)
    assert parsed.scheme == "https"
    assert parsed.netloc == "x.com"
    assert parsed.path == "/intent/post"
    assert parse_qs(parsed.query)["text"] == ["FINAL: Home 21, Visitor 14."]


def test_default_registry_contains_facebook_only() -> None:
    registry = default_adapter_registry(credential_resolver=lambda _ref: "token")
    assert set(registry) == {"facebook"}


def test_facebook_publish_uses_external_credential_and_page_photo(tmp_path: Path) -> None:
    calls = []

    def transport(method, url, headers, body):
        calls.append((method, url, headers, body))
        assert method == "POST"
        assert url.endswith("/v25.0/page-1/photos")
        assert headers["Authorization"] == "Bearer token"
        assert b'name="message"' in body
        assert b"Touchdown" in body
        assert b'name="source"' in body
        return HttpResponse(200, {}, b'{"post_id":"post-1"}')

    adapter = FacebookPageAdapter(
        credential_resolver=lambda _ref: "token",
        transport=transport,
    )
    result = adapter.publish(
        {
            "credential_ref": "FB_TOKEN",
            "page_id": "page-1",
            "api_version": "v25.0",
        },
        text="Touchdown",
        image_path=image_file(tmp_path),
    )
    assert result.code == "PUBLISHED"
    assert result.post_id == "post-1"
    assert len(calls) == 1


def test_facebook_publish_requires_external_credential(tmp_path: Path) -> None:
    adapter = FacebookPageAdapter(credential_resolver=lambda _ref: "")
    result = adapter.publish(
        {"credential_ref": "FB_TOKEN", "page_id": "page-1"},
        text="Final",
        image_path=image_file(tmp_path),
    )
    assert result.code == "CREDENTIAL_UNAVAILABLE"


def test_facebook_publish_requires_page_id(tmp_path: Path) -> None:
    adapter = FacebookPageAdapter(credential_resolver=lambda _ref: "token")
    result = adapter.publish(
        {"credential_ref": "FB_TOKEN"},
        text="Final",
        image_path=image_file(tmp_path),
    )
    assert result.code == "PAGE_ID_REQUIRED"


def test_facebook_429_is_retryable(tmp_path: Path) -> None:
    adapter = FacebookPageAdapter(
        credential_resolver=lambda _ref: "token",
        transport=lambda *_args: HttpResponse(
            429,
            {"Retry-After": "45"},
            json.dumps({"error": {"message": "rate limited"}}).encode(),
        ),
    )
    result = adapter.publish(
        {"credential_ref": "FB_TOKEN", "page_id": "page-1"},
        text="Final",
        image_path=image_file(tmp_path),
    )
    assert result.code == "POST_FAILED"
    assert result.retryable is True
    assert result.retry_after == 45


def test_facebook_delete_uses_graph_endpoint() -> None:
    calls = []

    def transport(method, url, headers, body):
        calls.append((method, url, headers, body))
        return HttpResponse(200, {}, b'{"success":true}')

    adapter = FacebookPageAdapter(
        credential_resolver=lambda _ref: "token",
        transport=transport,
    )
    result = adapter.delete(
        {"credential_ref": "FB_TOKEN", "api_version": "v25.0"},
        post_id="post-1",
    )
    assert result.code == "DELETED"
    assert calls[0][0] == "DELETE"
    assert calls[0][1].endswith("/v25.0/post-1")
