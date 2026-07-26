from __future__ import annotations

import base64
import json
import mimetypes
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


Transport = Callable[[str, str, Mapping[str, str], bytes | None, float], tuple[int, dict[str, Any]]]


@dataclass(frozen=True)
class PublishResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.code == "OK"


def default_transport(
    method: str,
    url: str,
    headers: Mapping[str, str],
    body: bytes | None,
    timeout: float,
) -> tuple[int, dict[str, Any]]:
    request = Request(
        url=url,
        data=body,
        headers=dict(headers),
        method=method.upper(),
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
            status = int(getattr(response, "status", 200))
    except HTTPError as exc:
        raw = exc.read()
        status = int(exc.code)
    except URLError as exc:
        raise RuntimeError(str(exc.reason)) from exc

    if not raw:
        return status, {}
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        payload = {"raw": raw.decode("utf-8", errors="replace")}
    return status, payload if isinstance(payload, dict) else {"data": payload}


class XPublisher:
    """Publish text and optional image media through the X API."""

    platform = "x"

    def __init__(
        self,
        *,
        access_token: str = "",
        transport: Transport = default_transport,
        api_base: str = "https://api.x.com",
        timeout: float = 20.0,
    ) -> None:
        self._access_token = str(access_token or "").strip()
        self._transport = transport
        self._api_base = str(api_base or "https://api.x.com").rstrip("/")
        self._timeout = max(1.0, float(timeout))

    @property
    def configured(self) -> bool:
        return bool(self._access_token)

    def status(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "configured": self.configured,
            "supports_text": True,
            "supports_image": True,
        }

    def _request_json(self, path: str, payload: dict[str, Any]) -> PublishResult:
        if not self.configured:
            return PublishResult("PLATFORM_NOT_CONFIGURED", {"platform": self.platform})
        try:
            status, response = self._transport(
                "POST",
                f"{self._api_base}{path}",
                {
                    "Authorization": f"Bearer {self._access_token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json.dumps(payload).encode("utf-8"),
                self._timeout,
            )
        except Exception as exc:
            return PublishResult(
                "PUBLISH_TRANSPORT_ERROR",
                {"platform": self.platform, "message": str(exc)},
            )
        if status < 200 or status >= 300:
            return PublishResult(
                "PUBLISH_REJECTED",
                {
                    "platform": self.platform,
                    "status": status,
                    "response": response,
                },
            )
        return PublishResult("OK", {"platform": self.platform, "response": response})

    def _upload_image(self, media_path: Path) -> PublishResult:
        try:
            media = Path(media_path).read_bytes()
        except OSError as exc:
            return PublishResult(
                "MEDIA_READ_FAILED",
                {"platform": self.platform, "message": str(exc)},
            )
        media_type = mimetypes.guess_type(str(media_path))[0] or "image/png"
        result = self._request_json(
            "/2/media/upload",
            {
                "media": base64.b64encode(media).decode("ascii"),
                "media_category": "tweet_image",
                "media_type": media_type,
                "shared": False,
            },
        )
        if not result.ok:
            return result
        response = result.data.get("response", {})
        data = response.get("data", {}) if isinstance(response, dict) else {}
        media_id = str(data.get("id") or data.get("media_id") or "")
        if not media_id:
            return PublishResult(
                "MEDIA_UPLOAD_INVALID_RESPONSE",
                {"platform": self.platform, "response": response},
            )
        return PublishResult("OK", {"platform": self.platform, "media_id": media_id})

    def publish(self, *, text: str, media_path: Path | None = None) -> PublishResult:
        payload: dict[str, Any] = {"text": str(text or "").strip()}
        if not payload["text"] and media_path is None:
            return PublishResult("POST_CONTENT_REQUIRED", {"platform": self.platform})
        if media_path is not None:
            upload = self._upload_image(Path(media_path))
            if not upload.ok:
                return upload
            payload["media"] = {"media_ids": [upload.data["media_id"]]}
        result = self._request_json("/2/tweets", payload)
        if not result.ok:
            return result
        response = result.data.get("response", {})
        data = response.get("data", {}) if isinstance(response, dict) else {}
        return PublishResult(
            "OK",
            {
                "platform": self.platform,
                "external_id": str(data.get("id", "")),
                "response": response,
            },
        )


class FacebookPagePublisher:
    """Publish text or an image post to a configured Facebook Page."""

    platform = "facebook"

    def __init__(
        self,
        *,
        page_id: str = "",
        page_access_token: str = "",
        transport: Transport = default_transport,
        api_base: str = "https://graph.facebook.com",
        timeout: float = 20.0,
    ) -> None:
        self._page_id = str(page_id or "").strip()
        self._access_token = str(page_access_token or "").strip()
        self._transport = transport
        self._api_base = str(api_base or "https://graph.facebook.com").rstrip("/")
        self._timeout = max(1.0, float(timeout))

    @property
    def configured(self) -> bool:
        return bool(self._page_id and self._access_token)

    def status(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "configured": self.configured,
            "supports_text": True,
            "supports_image": True,
            "page_id": self._page_id if self.configured else "",
        }

    def _send(
        self,
        path: str,
        *,
        content_type: str,
        body: bytes,
    ) -> PublishResult:
        if not self.configured:
            return PublishResult("PLATFORM_NOT_CONFIGURED", {"platform": self.platform})
        try:
            status, response = self._transport(
                "POST",
                f"{self._api_base}/{self._page_id}{path}",
                {
                    "Authorization": f"Bearer {self._access_token}",
                    "Content-Type": content_type,
                    "Accept": "application/json",
                },
                body,
                self._timeout,
            )
        except Exception as exc:
            return PublishResult(
                "PUBLISH_TRANSPORT_ERROR",
                {"platform": self.platform, "message": str(exc)},
            )
        if status < 200 or status >= 300:
            return PublishResult(
                "PUBLISH_REJECTED",
                {
                    "platform": self.platform,
                    "status": status,
                    "response": response,
                },
            )
        return PublishResult("OK", {"platform": self.platform, "response": response})

    @staticmethod
    def _multipart(text: str, media_path: Path) -> tuple[str, bytes]:
        boundary = f"----CSRN{uuid.uuid4().hex}"
        filename = media_path.name
        media_type = mimetypes.guess_type(filename)[0] or "image/png"
        file_bytes = media_path.read_bytes()
        chunks = [
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"caption\"\r\n\r\n{text}\r\n".encode("utf-8"),
            f"--{boundary}\r\nContent-Disposition: form-data; name=\"published\"\r\n\r\ntrue\r\n".encode("utf-8"),
            (
                f"--{boundary}\r\n"
                f"Content-Disposition: form-data; name=\"source\"; filename=\"{filename}\"\r\n"
                f"Content-Type: {media_type}\r\n\r\n"
            ).encode("utf-8"),
            file_bytes,
            f"\r\n--{boundary}--\r\n".encode("utf-8"),
        ]
        return f"multipart/form-data; boundary={boundary}", b"".join(chunks)

    def publish(self, *, text: str, media_path: Path | None = None) -> PublishResult:
        text = str(text or "").strip()
        if not text and media_path is None:
            return PublishResult("POST_CONTENT_REQUIRED", {"platform": self.platform})
        try:
            if media_path is not None:
                content_type, body = self._multipart(text, Path(media_path))
                result = self._send("/photos", content_type=content_type, body=body)
            else:
                body = urlencode({"message": text}).encode("utf-8")
                result = self._send(
                    "/feed",
                    content_type="application/x-www-form-urlencoded",
                    body=body,
                )
        except OSError as exc:
            return PublishResult(
                "MEDIA_READ_FAILED",
                {"platform": self.platform, "message": str(exc)},
            )
        if not result.ok:
            return result
        response = result.data.get("response", {})
        return PublishResult(
            "OK",
            {
                "platform": self.platform,
                "external_id": str(
                    response.get("post_id") or response.get("id") or ""
                ),
                "response": response,
            },
        )
