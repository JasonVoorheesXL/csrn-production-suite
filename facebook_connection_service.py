from __future__ import annotations

import copy
import ctypes
import json
import os
import re
import secrets
import time
from ctypes import wintypes
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Mapping
from urllib.parse import urlencode, urlparse

from social_platforms import HttpResponse, Transport, urllib_transport


Clock = Callable[[], float]
SocialAccountSaver = Callable[[Mapping[str, Any]], Any]
SocialAccountRemover = Callable[[str, str], Any]
ProtectBytes = Callable[[bytes], bytes]
UnprotectBytes = Callable[[bytes], bytes]


@dataclass(frozen=True)
class FacebookConnectionResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.code in {
            "OK",
            "APP_CONFIGURED",
            "AUTHORIZATION_READY",
            "PAGE_CONNECTED",
            "CONNECTION_HEALTHY",
            "PAGE_DISCONNECTED",
            "APP_CONFIGURATION_REMOVED",
        }


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


def _dpapi_protect(payload: bytes) -> bytes:
    if os.name != "nt":
        raise RuntimeError("WINDOWS_DPAPI_REQUIRED")
    buffer = ctypes.create_string_buffer(payload)
    input_blob = _DataBlob(
        len(payload), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))
    )
    output_blob = _DataBlob()
    description = "CSRN Facebook Connection"
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    if not crypt32.CryptProtectData(
        ctypes.byref(input_blob),
        description,
        None,
        None,
        None,
        0,
        ctypes.byref(output_blob),
    ):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        kernel32.LocalFree(output_blob.pbData)


def _dpapi_unprotect(payload: bytes) -> bytes:
    if os.name != "nt":
        raise RuntimeError("WINDOWS_DPAPI_REQUIRED")
    buffer = ctypes.create_string_buffer(payload)
    input_blob = _DataBlob(
        len(payload), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))
    )
    output_blob = _DataBlob()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    if not crypt32.CryptUnprotectData(
        ctypes.byref(input_blob),
        None,
        None,
        None,
        None,
        0,
        ctypes.byref(output_blob),
    ):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        kernel32.LocalFree(output_blob.pbData)


class FacebookCredentialVault:
    """Windows-user-bound credential storage for the Meta app secret and Page token.

    The file contains only DPAPI-protected bytes. The decrypted values never enter
    normal configuration, social state, audit rows, route responses, or support
    bundles.
    """

    PAGE_TOKEN_REFERENCE = "CSRN_FACEBOOK_SECURE_PAGE_TOKEN"

    def __init__(
        self,
        path: Path,
        *,
        protect: ProtectBytes | None = None,
        unprotect: UnprotectBytes | None = None,
    ) -> None:
        self.path = Path(path)
        self._protect = protect or _dpapi_protect
        self._unprotect = unprotect or _dpapi_unprotect
        self._lock = Lock()

    def _read_unlocked(self) -> dict[str, str]:
        if not self.path.is_file():
            return {}
        raw = self.path.read_bytes()
        if not raw:
            return {}
        clear = self._unprotect(raw)
        payload = json.loads(clear.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("CREDENTIAL_VAULT_INVALID")
        return {
            str(key): str(value)
            for key, value in payload.items()
            if isinstance(key, str) and isinstance(value, str)
        }

    def _write_unlocked(self, values: Mapping[str, str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(dict(values), sort_keys=True).encode("utf-8")
        protected = self._protect(payload)
        temporary = self.path.with_name(f".{self.path.name}.tmp")
        temporary.write_bytes(protected)
        try:
            temporary.chmod(0o600)
        except OSError:
            pass
        temporary.replace(self.path)

    def set(self, key: str, value: str) -> None:
        with self._lock:
            values = self._read_unlocked()
            if value:
                values[str(key)] = str(value)
            else:
                values.pop(str(key), None)
            if values:
                self._write_unlocked(values)
            elif self.path.exists():
                self.path.unlink()

    def get(self, key: str) -> str:
        try:
            with self._lock:
                return self._read_unlocked().get(str(key), "")
        except (OSError, ValueError, UnicodeError, json.JSONDecodeError, RuntimeError):
            return ""

    def has(self, key: str) -> bool:
        return bool(self.get(key))

    def remove(self, *keys: str) -> None:
        with self._lock:
            values = self._read_unlocked()
            for key in keys:
                values.pop(str(key), None)
            if values:
                self._write_unlocked(values)
            elif self.path.exists():
                self.path.unlink()

    def resolve(self, reference: str) -> str:
        reference = str(reference or "").strip()
        if reference == self.PAGE_TOKEN_REFERENCE:
            return self.get("page_access_token")
        return os.environ.get(reference, "") if reference else ""

    def available(self, reference: str) -> bool:
        return bool(self.resolve(reference))


class FacebookConnectionService:
    SCHEMA = 1
    DEFAULT_API_VERSION = "v25.0"
    DEFAULT_REDIRECT_URI = ""
    CALLBACK_PATH = "/api/social/facebook/callback"
    REQUIRED_SCOPES = (
        "pages_show_list",
        "pages_manage_posts",
        "pages_read_engagement",
    )
    APP_ID = re.compile(r"^[0-9]{5,40}$")
    APP_SECRET = re.compile(r"^[A-Za-z0-9_-]{16,128}$")
    VERSION = re.compile(r"^v[0-9]{1,3}\.[0-9]{1,3}$")
    MAX_PENDING = 5
    PENDING_SECONDS = 15 * 60

    def __init__(
        self,
        *,
        settings_file: Path,
        vault: FacebookCredentialVault,
        save_social_account: SocialAccountSaver,
        remove_social_account: SocialAccountRemover,
        transport: Transport = urllib_transport,
        clock: Clock = time.time,
    ) -> None:
        self.settings_file = Path(settings_file)
        self.vault = vault
        self._save_social_account = save_social_account
        self._remove_social_account = remove_social_account
        self._transport = transport
        self._clock = clock
        self._lock = Lock()
        self._pending: dict[str, dict[str, Any]] = {}
        self._oauth_states: dict[str, int] = {}

    def _default(self) -> dict[str, Any]:
        return {
            "schema": self.SCHEMA,
            "app_id": "",
            "api_version": self.DEFAULT_API_VERSION,
            "redirect_uri": self.DEFAULT_REDIRECT_URI,
            "page": {},
            "last_error": "",
            "updated_at": 0,
        }

    def _load(self) -> dict[str, Any]:
        self.settings_file.parent.mkdir(parents=True, exist_ok=True)
        if not self.settings_file.is_file():
            return self._default()
        try:
            payload = json.loads(self.settings_file.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return self._default()
        if not isinstance(payload, dict):
            return self._default()
        state = self._default()
        state.update(payload)
        state["page"] = payload.get("page", {}) if isinstance(payload.get("page"), dict) else {}
        state["schema"] = self.SCHEMA
        return state

    def _write(self, state: Mapping[str, Any]) -> None:
        payload = copy.deepcopy(dict(state))
        payload["schema"] = self.SCHEMA
        payload["updated_at"] = int(self._clock())
        self.settings_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.settings_file.with_name(f".{self.settings_file.name}.tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(self.settings_file)

    @staticmethod
    def _json(response: HttpResponse) -> dict[str, Any]:
        try:
            payload = json.loads(response.body.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _safe_error(response: HttpResponse, fallback: str) -> dict[str, Any]:
        payload = FacebookConnectionService._json(response)
        error = payload.get("error") if isinstance(payload.get("error"), dict) else {}
        return {
            "message": str(error.get("message") or fallback)[:500],
            "type": str(error.get("type") or "")[:120],
            "code": error.get("code", ""),
            "http_status": int(response.status or 0),
        }

    @classmethod
    def _valid_redirect_uri(cls, redirect_uri: str) -> bool:
        parsed = urlparse(str(redirect_uri or "").strip())
        return bool(
            parsed.scheme.lower() == "https"
            and parsed.netloc
            and parsed.path == cls.CALLBACK_PATH
            and not parsed.params
            and not parsed.query
            and not parsed.fragment
        )

    def _request_json(
        self,
        method: str,
        url: str,
        *,
        token: str = "",
        body: bytes | None = None,
        content_type: str = "application/x-www-form-urlencoded",
    ) -> tuple[HttpResponse, dict[str, Any]]:
        headers = {
            "Accept": "application/json",
            "User-Agent": "CSRN-Production-Suite/1.13",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        if body is not None:
            headers["Content-Type"] = content_type
        response = self._transport(method, url, headers, body)
        return response, self._json(response)

    def status(self) -> FacebookConnectionResult:
        with self._lock:
            state = self._load()
        app_secret_available = self.vault.has("app_secret")
        page_token_available = self.vault.has("page_access_token")
        redirect_uri = str(state.get("redirect_uri") or self.DEFAULT_REDIRECT_URI)
        page = copy.deepcopy(state.get("page") or {})
        connected = bool(page.get("id") and page_token_available)
        return FacebookConnectionResult(
            "OK",
            {
                "facebook": {
                    "app_configured": bool(
                        state.get("app_id")
                        and app_secret_available
                        and self._valid_redirect_uri(redirect_uri)
                    ),
                    "app_id": str(state.get("app_id") or ""),
                    "app_secret_stored": app_secret_available,
                    "api_version": str(state.get("api_version") or self.DEFAULT_API_VERSION),
                    "redirect_uri": redirect_uri,
                    "required_scopes": list(self.REQUIRED_SCOPES),
                    "connected": connected,
                    "page": page,
                    "last_error": str(state.get("last_error") or ""),
                }
            },
        )

    def configure_app(self, incoming: Mapping[str, Any] | None) -> FacebookConnectionResult:
        data = dict(incoming or {})
        app_id = str(data.get("app_id") or "").strip()
        app_secret = str(data.get("app_secret") or "").strip()
        api_version = str(data.get("api_version") or self.DEFAULT_API_VERSION).strip()
        redirect_uri = str(data.get("redirect_uri") or self.DEFAULT_REDIRECT_URI).strip()
        if not self.APP_ID.fullmatch(app_id):
            return FacebookConnectionResult("FACEBOOK_APP_ID_INVALID")
        existing_secret = self.vault.has("app_secret")
        if app_secret:
            if not self.APP_SECRET.fullmatch(app_secret):
                return FacebookConnectionResult("FACEBOOK_APP_SECRET_INVALID")
        elif not existing_secret:
            return FacebookConnectionResult("FACEBOOK_APP_SECRET_INVALID")
        if not self.VERSION.fullmatch(api_version):
            return FacebookConnectionResult("FACEBOOK_API_VERSION_INVALID")
        if not self._valid_redirect_uri(redirect_uri):
            return FacebookConnectionResult(
                "FACEBOOK_REDIRECT_URI_INVALID",
                {
                    "message": "Use an HTTPS callback URL ending exactly in /api/social/facebook/callback.",
                    "required_path": self.CALLBACK_PATH,
                },
            )
        with self._lock:
            previous_state = self._load()
        previous_app_id = str(previous_state.get("app_id") or "")
        app_changed = bool(previous_app_id and previous_app_id != app_id)
        if not app_secret and previous_app_id != app_id:
            return FacebookConnectionResult("FACEBOOK_APP_SECRET_INVALID")
        try:
            if app_changed:
                self.vault.remove("page_access_token")
            if app_secret:
                self.vault.set("app_secret", app_secret)
        except (OSError, ValueError, RuntimeError) as exc:
            return FacebookConnectionResult(
                "FACEBOOK_SECURE_STORAGE_FAILED", {"message": str(exc)[:300]}
            )
        if app_changed:
            self._remove_social_account("facebook-page", "REMOVE SOCIAL ACCOUNT")
        with self._lock:
            state = self._load()
            if app_changed:
                state["page"] = {}
            state.update(
                {
                    "app_id": app_id,
                    "api_version": api_version,
                    "redirect_uri": redirect_uri,
                    "last_error": "",
                }
            )
            self._write(state)
        return FacebookConnectionResult("APP_CONFIGURED", {"facebook": self.status().data["facebook"]})

    def remove_app_configuration(self, confirmation: Any) -> FacebookConnectionResult:
        if str(confirmation or "") != "REMOVE FACEBOOK APP CONFIGURATION":
            return FacebookConnectionResult("FACEBOOK_APP_REMOVE_CONFIRMATION_REQUIRED")
        disconnect_result = self.disconnect("DISCONNECT FACEBOOK PAGE")
        if not disconnect_result.ok and disconnect_result.code != "FACEBOOK_PAGE_NOT_CONNECTED":
            return disconnect_result
        try:
            self.vault.remove("app_secret", "page_access_token")
        except (OSError, ValueError, RuntimeError) as exc:
            return FacebookConnectionResult(
                "FACEBOOK_SECURE_STORAGE_FAILED", {"message": str(exc)[:300]}
            )
        with self._lock:
            self._write(self._default())
            self._pending.clear()
            self._oauth_states.clear()
        return FacebookConnectionResult("APP_CONFIGURATION_REMOVED")

    def authorization_url(self, state_token: str) -> FacebookConnectionResult:
        state_token = str(state_token or "").strip()
        if len(state_token) < 24:
            return FacebookConnectionResult("FACEBOOK_OAUTH_STATE_INVALID")
        with self._lock:
            state = self._load()
        app_id = str(state.get("app_id") or "")
        api_version = str(state.get("api_version") or self.DEFAULT_API_VERSION)
        redirect_uri = str(state.get("redirect_uri") or self.DEFAULT_REDIRECT_URI)
        if not app_id or not self.vault.has("app_secret"):
            return FacebookConnectionResult("FACEBOOK_APP_NOT_CONFIGURED")
        if not self._valid_redirect_uri(redirect_uri):
            return FacebookConnectionResult(
                "FACEBOOK_REDIRECT_URI_INVALID",
                {
                    "message": "Save an HTTPS callback URL ending exactly in /api/social/facebook/callback."
                },
            )
        with self._lock:
            now = int(self._clock())
            self._purge_oauth_states(now)
            self._oauth_states[state_token] = now + self.PENDING_SECONDS
            while len(self._oauth_states) > self.MAX_PENDING:
                oldest = min(self._oauth_states, key=self._oauth_states.get)
                self._oauth_states.pop(oldest, None)
        params = {
            "client_id": app_id,
            "redirect_uri": redirect_uri,
            "state": state_token,
            "response_type": "code",
            "scope": ",".join(self.REQUIRED_SCOPES),
            "auth_type": "rerequest",
        }
        return FacebookConnectionResult(
            "AUTHORIZATION_READY",
            {"authorization_url": f"https://www.facebook.com/{api_version}/dialog/oauth?{urlencode(params)}"},
        )

    def complete_authorization(
        self,
        *,
        code: Any,
        received_state: Any,
        expected_state: Any = "",
    ) -> FacebookConnectionResult:
        code = str(code or "").strip()
        received_state = str(received_state or "").strip()
        expected_state = str(expected_state or "").strip()
        if not code:
            return FacebookConnectionResult("FACEBOOK_AUTHORIZATION_CODE_MISSING")
        if expected_state:
            state_valid = bool(received_state and secrets.compare_digest(received_state, expected_state))
        else:
            with self._lock:
                self._purge_oauth_states()
                state_valid = bool(received_state and self._oauth_states.pop(received_state, None))
        if not state_valid:
            return FacebookConnectionResult("FACEBOOK_OAUTH_STATE_INVALID")
        with self._lock:
            state = self._load()
        app_id = str(state.get("app_id") or "")
        app_secret = self.vault.get("app_secret")
        api_version = str(state.get("api_version") or self.DEFAULT_API_VERSION)
        redirect_uri = str(state.get("redirect_uri") or self.DEFAULT_REDIRECT_URI)
        if not app_id or not app_secret:
            return FacebookConnectionResult("FACEBOOK_APP_NOT_CONFIGURED")

        token_params = urlencode(
            {
                "client_id": app_id,
                "client_secret": app_secret,
                "redirect_uri": redirect_uri,
                "code": code,
            }
        )
        response, payload = self._request_json(
            "POST",
            f"https://graph.facebook.com/{api_version}/oauth/access_token",
            body=token_params.encode("utf-8"),
        )
        user_token = str(payload.get("access_token") or "")
        if response.status != 200 or not user_token:
            error = self._safe_error(response, "Facebook did not exchange the authorization code.")
            self._record_error(error["message"])
            return FacebookConnectionResult("FACEBOOK_CODE_EXCHANGE_FAILED", {"provider": error})

        exchange_params = urlencode(
            {
                "grant_type": "fb_exchange_token",
                "client_id": app_id,
                "client_secret": app_secret,
                "fb_exchange_token": user_token,
            }
        )
        long_response, long_payload = self._request_json(
            "POST",
            f"https://graph.facebook.com/{api_version}/oauth/access_token",
            body=exchange_params.encode("utf-8"),
        )
        token_warning = ""
        if long_response.status == 200 and long_payload.get("access_token"):
            user_token = str(long_payload["access_token"])
        else:
            token_warning = "Facebook returned a short-lived user authorization; reconnect may be required sooner."

        fields = "id,name,access_token,tasks,link,picture.type(square)"
        pages_response, pages_payload = self._request_json(
            "GET",
            f"https://graph.facebook.com/{api_version}/me/accounts?{urlencode({'fields': fields, 'limit': 100})}",
            token=user_token,
        )
        rows = pages_payload.get("data") if isinstance(pages_payload.get("data"), list) else []
        if pages_response.status != 200:
            error = self._safe_error(pages_response, "Facebook did not return managed Pages.")
            self._record_error(error["message"])
            return FacebookConnectionResult("FACEBOOK_PAGE_LIST_FAILED", {"provider": error})
        pages: list[dict[str, Any]] = []
        private_tokens: dict[str, str] = {}
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            page_id = str(row.get("id") or "").strip()
            page_token = str(row.get("access_token") or "").strip()
            if not page_id or not page_token:
                continue
            picture = row.get("picture") if isinstance(row.get("picture"), Mapping) else {}
            picture_data = picture.get("data") if isinstance(picture.get("data"), Mapping) else {}
            pages.append(
                {
                    "id": page_id,
                    "name": str(row.get("name") or page_id)[:160],
                    "link": str(row.get("link") or "")[:500],
                    "picture_url": str(picture_data.get("url") or "")[:1000],
                    "tasks": [str(item) for item in row.get("tasks", []) if isinstance(item, str)][:50],
                }
            )
            private_tokens[page_id] = page_token
        if not pages:
            self._record_error("No manageable Facebook Pages were returned for this account.")
            return FacebookConnectionResult(
                "FACEBOOK_NO_MANAGED_PAGES",
                {
                    "message": "Facebook did not return a Page with a usable Page access token. Confirm Page access and requested permissions."
                },
            )

        selection_id = secrets.token_urlsafe(24)
        with self._lock:
            now = int(self._clock())
            self._purge_pending(now)
            self._pending[selection_id] = {
                "created_at": now,
                "expires_at": now + self.PENDING_SECONDS,
                "pages": pages,
                "tokens": private_tokens,
            }
            while len(self._pending) > self.MAX_PENDING:
                oldest = min(self._pending, key=lambda key: self._pending[key]["created_at"])
                self._pending.pop(oldest, None)
        return FacebookConnectionResult(
            "OK",
            {
                "selection_id": selection_id,
                "pages": copy.deepcopy(pages),
                "warning": token_warning,
            },
        )


    def _purge_oauth_states(self, now: int | None = None) -> None:
        current = int(self._clock()) if now is None else int(now)
        for key in list(self._oauth_states):
            if int(self._oauth_states.get(key, 0)) <= current:
                self._oauth_states.pop(key, None)

    def _purge_pending(self, now: int | None = None) -> None:
        current = int(self._clock()) if now is None else int(now)
        for key in list(self._pending):
            if int(self._pending[key].get("expires_at", 0)) <= current:
                self._pending.pop(key, None)

    def pending_pages(self, selection_id: Any) -> FacebookConnectionResult:
        selection_id = str(selection_id or "").strip()
        with self._lock:
            self._purge_pending()
            pending = self._pending.get(selection_id)
            if not pending:
                return FacebookConnectionResult("FACEBOOK_PAGE_SELECTION_EXPIRED")
            pages = copy.deepcopy(pending.get("pages") or [])
        return FacebookConnectionResult("OK", {"selection_id": selection_id, "pages": pages})

    def connect_page(self, selection_id: Any, page_id: Any) -> FacebookConnectionResult:
        selection_id = str(selection_id or "").strip()
        page_id = str(page_id or "").strip()
        with self._lock:
            self._purge_pending()
            pending = self._pending.get(selection_id)
            if not pending:
                return FacebookConnectionResult("FACEBOOK_PAGE_SELECTION_EXPIRED")
            page = next((row for row in pending.get("pages", []) if str(row.get("id")) == page_id), None)
            page_token = str((pending.get("tokens") or {}).get(page_id, ""))
        if not page or not page_token:
            return FacebookConnectionResult("FACEBOOK_PAGE_SELECTION_INVALID")
        try:
            self.vault.set("page_access_token", page_token)
        except (OSError, ValueError, RuntimeError) as exc:
            return FacebookConnectionResult(
                "FACEBOOK_SECURE_STORAGE_FAILED", {"message": str(exc)[:300]}
            )
        with self._lock:
            state = self._load()
            state["page"] = {
                **copy.deepcopy(page),
                "connected_at": int(self._clock()),
                "last_tested_at": 0,
                "last_test_status": "NOT_TESTED",
            }
            state["last_error"] = ""
            self._write(state)
            self._pending.pop(selection_id, None)
        social_result = self._save_social_account(
            {
                "id": "facebook-page",
                "platform": "facebook",
                "display_name": str(page.get("name") or "Facebook Page"),
                "credential_ref": self.vault.PAGE_TOKEN_REFERENCE,
                "page_id": page_id,
                "page_url": str(page.get("link") or ""),
                "api_version": str(state.get("api_version") or self.DEFAULT_API_VERSION),
                "enabled": True,
                "auto_publish": False,
            }
        )
        if not getattr(social_result, "ok", False):
            self.vault.remove("page_access_token")
            return FacebookConnectionResult(
                "FACEBOOK_SOCIAL_ACCOUNT_SAVE_FAILED",
                {"error": getattr(social_result, "code", "UNKNOWN")},
            )
        return FacebookConnectionResult("PAGE_CONNECTED", {"facebook": self.status().data["facebook"]})

    def test_connection(self) -> FacebookConnectionResult:
        with self._lock:
            state = self._load()
        page = state.get("page") if isinstance(state.get("page"), dict) else {}
        page_id = str(page.get("id") or "")
        page_token = self.vault.get("page_access_token")
        if not page_id or not page_token:
            return FacebookConnectionResult("FACEBOOK_PAGE_NOT_CONNECTED")
        api_version = str(state.get("api_version") or self.DEFAULT_API_VERSION)
        fields = "id,name,link,picture.type(square)"
        response, payload = self._request_json(
            "GET",
            f"https://graph.facebook.com/{api_version}/{page_id}?{urlencode({'fields': fields})}",
            token=page_token,
        )
        if response.status != 200 or str(payload.get("id") or "") != page_id:
            error = self._safe_error(response, "Facebook could not validate the saved Page authorization.")
            with self._lock:
                state = self._load()
                state["last_error"] = error["message"]
                page = state.get("page") if isinstance(state.get("page"), dict) else {}
                page["last_tested_at"] = int(self._clock())
                page["last_test_status"] = "FAILED"
                state["page"] = page
                self._write(state)
            return FacebookConnectionResult("FACEBOOK_CONNECTION_TEST_FAILED", {"provider": error})
        picture = payload.get("picture") if isinstance(payload.get("picture"), Mapping) else {}
        picture_data = picture.get("data") if isinstance(picture.get("data"), Mapping) else {}
        with self._lock:
            state = self._load()
            page = state.get("page") if isinstance(state.get("page"), dict) else {}
            page.update(
                {
                    "id": page_id,
                    "name": str(payload.get("name") or page.get("name") or "Facebook Page")[:160],
                    "link": str(payload.get("link") or page.get("link") or "")[:500],
                    "picture_url": str(picture_data.get("url") or page.get("picture_url") or "")[:1000],
                    "last_tested_at": int(self._clock()),
                    "last_test_status": "HEALTHY",
                }
            )
            state["page"] = page
            state["last_error"] = ""
            self._write(state)
        return FacebookConnectionResult("CONNECTION_HEALTHY", {"facebook": self.status().data["facebook"]})

    def disconnect(self, confirmation: Any) -> FacebookConnectionResult:
        if str(confirmation or "") != "DISCONNECT FACEBOOK PAGE":
            return FacebookConnectionResult("FACEBOOK_DISCONNECT_CONFIRMATION_REQUIRED")
        with self._lock:
            state = self._load()
            connected = bool((state.get("page") or {}).get("id") or self.vault.has("page_access_token"))
        if not connected:
            return FacebookConnectionResult("FACEBOOK_PAGE_NOT_CONNECTED")
        try:
            self.vault.remove("page_access_token")
        except (OSError, ValueError, RuntimeError) as exc:
            return FacebookConnectionResult(
                "FACEBOOK_SECURE_STORAGE_FAILED", {"message": str(exc)[:300]}
            )
        social_result = self._remove_social_account("facebook-page", "REMOVE SOCIAL ACCOUNT")
        if not getattr(social_result, "ok", False) and getattr(social_result, "code", "") != "ACCOUNT_NOT_FOUND":
            return FacebookConnectionResult(
                "FACEBOOK_SOCIAL_ACCOUNT_REMOVE_FAILED",
                {"error": getattr(social_result, "code", "UNKNOWN")},
            )
        with self._lock:
            state = self._load()
            state["page"] = {}
            state["last_error"] = ""
            self._write(state)
        return FacebookConnectionResult("PAGE_DISCONNECTED", {"facebook": self.status().data["facebook"]})

    def _record_error(self, message: str) -> None:
        with self._lock:
            state = self._load()
            state["last_error"] = str(message or "")[:500]
            self._write(state)
