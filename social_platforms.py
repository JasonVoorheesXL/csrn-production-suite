from __future__ import annotations

import json
import mimetypes
import os
import secrets
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol
from urllib.parse import urlencode


CredentialResolver = Callable[[str], str]


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: Mapping[str, str] = field(default_factory=dict)
    body: bytes = b""


Transport = Callable[[str, str, Mapping[str, str], bytes | None], HttpResponse]


@dataclass(frozen=True)
class PlatformResult:
    code: str
    post_id: str = ""
    url: str = ""
    retryable: bool = False
    retry_after: int = 0
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.code in {"PUBLISHED", "DELETED"}


class SocialPlatformAdapter(Protocol):
    platform: str

    def publish(
        self,
        account: Mapping[str, Any],
        *,
        text: str,
        image_path: Path,
    ) -> PlatformResult: ...

    def delete(self, account: Mapping[str, Any], *, post_id: str) -> PlatformResult: ...


class EnvCredentialResolver:
    """Resolve supported automatic-publisher credentials from the environment.

    CSRN persists only the configured reference name. The current automatic
    publisher is Facebook Page. A commercial OAuth/account-connection provider
    can replace this resolver without changing the queue or recap engine.
    """

    def __call__(self, reference: str) -> str:
        reference = str(reference or "").strip()
        return os.environ.get(reference, "") if reference else ""


def build_x_compose_url(text: str) -> str:
    """Return the public X composer URL used by the assisted-manual workflow.

    This helper does not authenticate, call an API, upload media, or publish.
    The operator remains responsible for attaching the generated card and
    submitting the post in X.
    """

    return "https://x.com/intent/post?" + urlencode({"text": str(text or "")})


def urllib_transport(
    method: str,
    url: str,
    headers: Mapping[str, str],
    body: bytes | None,
) -> HttpResponse:
    request = urllib.request.Request(
        url,
        data=body,
        headers=dict(headers),
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return HttpResponse(
                int(getattr(response, "status", 200)),
                dict(response.headers.items()),
                response.read(),
            )
    except urllib.error.HTTPError as exc:
        return HttpResponse(
            int(exc.code),
            dict(exc.headers.items()) if exc.headers else {},
            exc.read(),
        )
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return HttpResponse(0, {}, str(exc).encode("utf-8", errors="replace"))


def _json_body(response: HttpResponse) -> dict[str, Any]:
    try:
        payload = json.loads(response.body.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _retry_after(headers: Mapping[str, str]) -> int:
    for key, value in headers.items():
        if str(key).casefold() == "retry-after":
            try:
                return max(0, int(float(value)))
            except (TypeError, ValueError):
                return 0
    return 0


def _failure(response: HttpResponse, *, prefix: str) -> PlatformResult:
    payload = _json_body(response)
    status = int(response.status or 0)
    retryable = status == 0 or status == 429 or status >= 500
    safe_details = {
        "http_status": status,
        "error": payload.get("error")
        or payload.get("errors")
        or payload.get("title")
        or "",
    }
    return PlatformResult(
        f"{prefix}_FAILED",
        retryable=retryable,
        retry_after=_retry_after(response.headers),
        details=safe_details,
    )


class FacebookPageAdapter:
    platform = "facebook"

    def __init__(
        self,
        *,
        credential_resolver: CredentialResolver | None = None,
        transport: Transport = urllib_transport,
    ) -> None:
        self._credentials = credential_resolver or EnvCredentialResolver()
        self._transport = transport

    @staticmethod
    def _multipart(fields: Mapping[str, str], image_path: Path) -> tuple[bytes, str]:
        boundary = f"----CSRN{secrets.token_hex(12)}"
        chunks: list[bytes] = []
        for name, value in fields.items():
            chunks.extend(
                [
                    f"--{boundary}\r\n".encode(),
                    f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                    str(value).encode("utf-8"),
                    b"\r\n",
                ]
            )
        mime = mimetypes.guess_type(image_path.name)[0] or "image/png"
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="source"; filename="{image_path.name}"\r\n'.encode(),
                f"Content-Type: {mime}\r\n\r\n".encode(),
                image_path.read_bytes(),
                b"\r\n",
                f"--{boundary}--\r\n".encode(),
            ]
        )
        return b"".join(chunks), boundary

    def publish(
        self,
        account: Mapping[str, Any],
        *,
        text: str,
        image_path: Path,
    ) -> PlatformResult:
        token = self._credentials(str(account.get("credential_ref", "")))
        if not token:
            return PlatformResult("CREDENTIAL_UNAVAILABLE")
        page_id = str(account.get("page_id", "")).strip()
        if not page_id:
            return PlatformResult("PAGE_ID_REQUIRED")
        image_path = Path(image_path)
        if not image_path.is_file():
            return PlatformResult("IMAGE_NOT_FOUND")

        base = str(account.get("api_base") or "https://graph.facebook.com").rstrip("/")
        version = str(account.get("api_version") or "v25.0").strip("/")
        body, boundary = self._multipart(
            {"message": text, "published": "true"},
            image_path,
        )
        response = self._transport(
            "POST",
            f"{base}/{version}/{page_id}/photos",
            {
                "Authorization": f"Bearer {token}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "User-Agent": "CSRN-Production-Suite/1.13",
            },
            body,
        )
        if response.status not in {200, 201}:
            return _failure(response, prefix="POST")
        payload = _json_body(response)
        post_id = str(payload.get("post_id") or payload.get("id") or "")
        return PlatformResult(
            "PUBLISHED",
            post_id=post_id,
            url=str(account.get("page_url", "")),
        )

    def delete(self, account: Mapping[str, Any], *, post_id: str) -> PlatformResult:
        token = self._credentials(str(account.get("credential_ref", "")))
        if not token:
            return PlatformResult("CREDENTIAL_UNAVAILABLE")
        post_id = str(post_id or "").strip()
        if not post_id:
            return PlatformResult("POST_ID_REQUIRED")
        base = str(account.get("api_base") or "https://graph.facebook.com").rstrip("/")
        version = str(account.get("api_version") or "v25.0").strip("/")
        response = self._transport(
            "DELETE",
            f"{base}/{version}/{post_id}",
            {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "User-Agent": "CSRN-Production-Suite/1.13",
            },
            None,
        )
        if response.status not in {200, 204}:
            return _failure(response, prefix="DELETE")
        return PlatformResult("DELETED", post_id=post_id)


def default_adapter_registry(
    *,
    credential_resolver: CredentialResolver | None = None,
    transport: Transport = urllib_transport,
) -> dict[str, SocialPlatformAdapter]:
    resolver = credential_resolver or EnvCredentialResolver()
    return {
        "facebook": FacebookPageAdapter(
            credential_resolver=resolver,
            transport=transport,
        ),
    }
