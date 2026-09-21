from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock
from typing import Any, Callable, Mapping

from credential_vault import CredentialVault, CredentialVaultError, VaultCredentialResolver


@dataclass(frozen=True)
class OAuthResult:
    code: str
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.code in {
            "OK",
            "AUTHORIZATION_READY",
            "CONNECTED",
            "CONNECTION_TESTED",
            "DISCONNECTED",
            "PAGE_SELECTED",
        }


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: Mapping[str, str] = field(default_factory=dict)
    body: bytes = b""


Transport = Callable[[str, str, Mapping[str, str], bytes | None], HttpResponse]
ConfigureAccount = Callable[[dict[str, Any]], Any]
Clock = Callable[[], float]


def urllib_transport(method: str, url: str, headers: Mapping[str, str], body: bytes | None) -> HttpResponse:
    request = urllib.request.Request(url, data=body, headers=dict(headers), method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return HttpResponse(int(getattr(response, "status", 200)), dict(response.headers.items()), response.read())
    except urllib.error.HTTPError as exc:
        return HttpResponse(int(exc.code), dict(exc.headers.items()) if exc.headers else {}, exc.read())
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return HttpResponse(0, {}, str(exc).encode("utf-8", errors="replace"))


def _json(response: HttpResponse) -> dict[str, Any]:
    try:
        payload = json.loads(response.body.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


class OAuthOnboardingService:
    """Consumer-style account connection boundary for X and Facebook Pages.

    X uses OAuth 2.0 Authorization Code with PKCE. Facebook uses a configured
    PossumFrog OAuth broker so Meta application secrets are never distributed in
    the desktop client.
    """

    X_SCOPES = ("tweet.read", "tweet.write", "users.read", "media.write", "offline.access")
    MAX_PENDING_AGE = 15 * 60

    def __init__(
        self,
        *,
        state_file: Path,
        vault: CredentialVault,
        configure_social_account: ConfigureAccount,
        transport: Transport = urllib_transport,
        clock: Clock = time.time,
        environment: Mapping[str, str] | None = None,
    ) -> None:
        self.state_file = Path(state_file)
        self.vault = vault
        self.configure_social_account = configure_social_account
        self.transport = transport
        self.clock = clock
        self.environment = environment if environment is not None else os.environ
        self._lock = Lock()
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

    def credential_resolver(self) -> VaultCredentialResolver:
        return VaultCredentialResolver(self.vault)

    @staticmethod
    def _default_state() -> dict[str, Any]:
        return {"schema": 1, "connections": {}, "pending": {}, "updated_at": 0}

    def _load(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.state_file.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            payload = self._default_state()
        if not isinstance(payload, dict):
            payload = self._default_state()
        payload.setdefault("connections", {})
        payload.setdefault("pending", {})
        return payload

    def _write(self, payload: dict[str, Any]) -> None:
        payload["updated_at"] = int(self.clock())
        temporary = self.state_file.with_name(f".{self.state_file.name}.tmp")
        temporary.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        temporary.replace(self.state_file)

    def _provider_config(self, provider: str) -> dict[str, str]:
        if provider == "x":
            return {
                "client_id": str(self.environment.get("CSRN_X_CLIENT_ID", "")).strip(),
                "authorize_url": "https://x.com/i/oauth2/authorize",
                "token_url": "https://api.x.com/2/oauth2/token",
                "identity_url": "https://api.x.com/2/users/me",
            }
        if provider == "facebook":
            broker = str(self.environment.get("CSRN_META_OAUTH_BROKER_URL", "")).strip().rstrip("/")
            return {"broker_url": broker}
        return {}

    def status(self) -> OAuthResult:
        with self._lock:
            state = self._load()
        now = int(self.clock())
        providers = []
        for provider, label in (("x", "X"), ("facebook", "Facebook Page")):
            config = self._provider_config(provider)
            configured = bool(config.get("client_id")) if provider == "x" else bool(config.get("broker_url"))
            connection = state["connections"].get(provider, {})
            providers.append(
                {
                    "id": provider,
                    "label": label,
                    "provider_configured": configured,
                    "vault_available": bool(self.vault.available),
                    "connected": bool(connection.get("connected")),
                    "display_name": str(connection.get("display_name", "")),
                    "username": str(connection.get("username", "")),
                    "page_id": str(connection.get("page_id", "")),
                    "last_tested_at": int(connection.get("last_tested_at", 0) or 0),
                    "last_test_ok": bool(connection.get("last_test_ok", False)),
                    "action_required": not configured or not self.vault.available,
                    "updated_at": int(connection.get("updated_at", 0) or 0),
                }
            )
        return OAuthResult("OK", {"providers": providers, "checked_at": now})

    def start(self, provider: str, callback_url: str) -> OAuthResult:
        provider = str(provider or "").strip().lower()
        callback_url = str(callback_url or "").strip()
        if provider not in {"x", "facebook"}:
            return OAuthResult("PROVIDER_UNSUPPORTED")
        if not callback_url.startswith(("http://127.0.0.1:", "http://localhost:")):
            return OAuthResult("CALLBACK_URL_INVALID")
        if not self.vault.available:
            return OAuthResult("PROTECTED_STORAGE_UNAVAILABLE")
        config = self._provider_config(provider)
        state_token = secrets.token_urlsafe(32)
        pending: dict[str, Any] = {
            "provider": provider,
            "callback_url": callback_url,
            "created_at": int(self.clock()),
        }
        if provider == "x":
            client_id = config.get("client_id", "")
            if not client_id:
                return OAuthResult("PROVIDER_APPLICATION_NOT_CONFIGURED")
            verifier = _b64url(secrets.token_bytes(48))
            challenge = _b64url(hashlib.sha256(verifier.encode("ascii")).digest())
            pending["code_verifier"] = verifier
            query = urllib.parse.urlencode(
                {
                    "response_type": "code",
                    "client_id": client_id,
                    "redirect_uri": callback_url,
                    "scope": " ".join(self.X_SCOPES),
                    "state": state_token,
                    "code_challenge": challenge,
                    "code_challenge_method": "S256",
                }
            )
            authorize_url = f"{config['authorize_url']}?{query}"
        else:
            broker = config.get("broker_url", "")
            if not broker:
                return OAuthResult("PROVIDER_APPLICATION_NOT_CONFIGURED")
            authorize_url = f"{broker}/authorize/facebook?{urllib.parse.urlencode({'state': state_token, 'redirect_uri': callback_url})}"
        with self._lock:
            state = self._load()
            state["pending"] = {state_token: pending}
            self._write(state)
        return OAuthResult("AUTHORIZATION_READY", {"provider": provider, "authorize_url": authorize_url})

    def complete(self, provider: str, *, state_token: str, code: str) -> OAuthResult:
        provider = str(provider or "").strip().lower()
        state_token = str(state_token or "").strip()
        code = str(code or "").strip()
        if provider not in {"x", "facebook"}:
            return OAuthResult("PROVIDER_UNSUPPORTED")
        with self._lock:
            state = self._load()
            pending = state["pending"].get(state_token)
        if not isinstance(pending, dict) or pending.get("provider") != provider:
            return OAuthResult("OAUTH_STATE_INVALID")
        if int(self.clock()) - int(pending.get("created_at", 0) or 0) > self.MAX_PENDING_AGE:
            return OAuthResult("OAUTH_STATE_EXPIRED")
        if not code:
            return OAuthResult("AUTHORIZATION_CODE_REQUIRED")
        result = self._complete_x(pending, code) if provider == "x" else self._complete_facebook(pending, code)
        if not result.ok:
            return result
        connection = dict(result.data["connection"])
        with self._lock:
            state = self._load()
            state["pending"].pop(state_token, None)
            state["connections"][provider] = connection
            self._write(state)
        account_payload = dict(result.data["account"])
        configured = self.configure_social_account(account_payload)
        if hasattr(configured, "ok") and not configured.ok:
            return OAuthResult("SOCIAL_ACCOUNT_CONFIGURATION_FAILED", {"provider": provider, "error": getattr(configured, "code", "UNKNOWN")})
        return OAuthResult("CONNECTED", {"provider": provider, "connection": self._public_connection(connection)})

    def _complete_x(self, pending: Mapping[str, Any], code: str) -> OAuthResult:
        config = self._provider_config("x")
        body = urllib.parse.urlencode(
            {
                "code": code,
                "grant_type": "authorization_code",
                "client_id": config.get("client_id", ""),
                "redirect_uri": str(pending.get("callback_url", "")),
                "code_verifier": str(pending.get("code_verifier", "")),
            }
        ).encode("utf-8")
        token_response = self.transport("POST", config["token_url"], {"Content-Type": "application/x-www-form-urlencoded", "User-Agent": "CSRN-Production-Suite/1.13"}, body)
        token_payload = _json(token_response)
        if token_response.status not in {200, 201}:
            return OAuthResult("TOKEN_EXCHANGE_FAILED", {"http_status": token_response.status})
        access_token = str(token_payload.get("access_token", ""))
        if not access_token:
            return OAuthResult("ACCESS_TOKEN_MISSING")
        identity_response = self.transport("GET", config["identity_url"], {"Authorization": f"Bearer {access_token}", "User-Agent": "CSRN-Production-Suite/1.13"}, None)
        identity = (_json(identity_response).get("data") or {}) if identity_response.status == 200 else {}
        user_id = str(identity.get("id", "")) or secrets.token_hex(6)
        username = str(identity.get("username", ""))
        display_name = str(identity.get("name", "")) or username or "Connected X account"
        reference = f"oauth:x:{user_id}"
        try:
            self.vault.put(reference, access_token)
            refresh = str(token_payload.get("refresh_token", ""))
            if refresh:
                self.vault.put(f"{reference}:refresh", refresh)
        except CredentialVaultError:
            return OAuthResult("CREDENTIAL_STORAGE_FAILED")
        now = int(self.clock())
        connection = {
            "connected": True,
            "provider": "x",
            "account_id": user_id,
            "display_name": display_name,
            "username": username,
            "credential_ref": f"vault:{reference}",
            "refresh_ref": f"vault:{reference}:refresh" if token_payload.get("refresh_token") else "",
            "scope": str(token_payload.get("scope", "")),
            "updated_at": now,
            "last_tested_at": now,
            "last_test_ok": identity_response.status == 200,
        }
        account = {
            "id": f"x-{user_id}",
            "platform": "x",
            "display_name": display_name,
            "credential_ref": f"vault:{reference}",
            "username": username,
            "enabled": True,
            "auto_publish": False,
        }
        return OAuthResult("CONNECTED", {"connection": connection, "account": account})

    def _complete_facebook(self, pending: Mapping[str, Any], code: str) -> OAuthResult:
        broker = self._provider_config("facebook").get("broker_url", "")
        body = json.dumps({"code": code, "redirect_uri": pending.get("callback_url", "")}).encode("utf-8")
        response = self.transport("POST", f"{broker}/exchange/facebook", {"Content-Type": "application/json", "User-Agent": "CSRN-Production-Suite/1.13"}, body)
        payload = _json(response)
        if response.status not in {200, 201}:
            return OAuthResult("TOKEN_EXCHANGE_FAILED", {"http_status": response.status})
        token = str(payload.get("page_access_token", ""))
        page_id = str(payload.get("page_id", ""))
        if not token or not page_id:
            return OAuthResult("FACEBOOK_PAGE_SELECTION_REQUIRED", {"pages": payload.get("pages", [])})
        display_name = str(payload.get("page_name", "")) or "Connected Facebook Page"
        reference = f"oauth:facebook:{page_id}"
        try:
            self.vault.put(reference, token)
        except CredentialVaultError:
            return OAuthResult("CREDENTIAL_STORAGE_FAILED")
        now = int(self.clock())
        connection = {
            "connected": True,
            "provider": "facebook",
            "account_id": page_id,
            "page_id": page_id,
            "display_name": display_name,
            "credential_ref": f"vault:{reference}",
            "updated_at": now,
            "last_tested_at": now,
            "last_test_ok": True,
        }
        account = {
            "id": f"facebook-{page_id}",
            "platform": "facebook",
            "display_name": display_name,
            "credential_ref": f"vault:{reference}",
            "page_id": page_id,
            "enabled": True,
            "auto_publish": False,
        }
        return OAuthResult("CONNECTED", {"connection": connection, "account": account})

    @staticmethod
    def _public_connection(connection: Mapping[str, Any]) -> dict[str, Any]:
        return {
            key: value
            for key, value in connection.items()
            if key not in {"credential_ref", "refresh_ref", "scope"}
        }

    def test_connection(self, provider: str) -> OAuthResult:
        provider = str(provider or "").strip().lower()
        with self._lock:
            state = self._load()
            connection = dict(state["connections"].get(provider, {}))
        if not connection.get("connected"):
            return OAuthResult("CONNECTION_NOT_FOUND")
        resolver = self.credential_resolver()
        token = resolver(str(connection.get("credential_ref", "")))
        if not token:
            return OAuthResult("CREDENTIAL_UNAVAILABLE")
        if provider == "x":
            response = self.transport("GET", "https://api.x.com/2/users/me", {"Authorization": f"Bearer {token}", "User-Agent": "CSRN-Production-Suite/1.13"}, None)
            ok = response.status == 200
        elif provider == "facebook":
            page_id = urllib.parse.quote(str(connection.get("page_id", "")), safe="")
            response = self.transport("GET", f"https://graph.facebook.com/v25.0/{page_id}?fields=id,name", {"Authorization": f"Bearer {token}", "User-Agent": "CSRN-Production-Suite/1.13"}, None)
            ok = response.status == 200
        else:
            return OAuthResult("PROVIDER_UNSUPPORTED")
        with self._lock:
            state = self._load()
            state["connections"][provider]["last_tested_at"] = int(self.clock())
            state["connections"][provider]["last_test_ok"] = ok
            self._write(state)
        return OAuthResult("CONNECTION_TESTED" if ok else "CONNECTION_TEST_FAILED", {"provider": provider, "ok": ok, "http_status": response.status})

    def disconnect(self, provider: str, confirmation: str) -> OAuthResult:
        provider = str(provider or "").strip().lower()
        if confirmation != "DISCONNECT SOCIAL ACCOUNT":
            return OAuthResult("DISCONNECT_CONFIRMATION_REQUIRED", {"required_confirmation": "DISCONNECT SOCIAL ACCOUNT"})
        with self._lock:
            state = self._load()
            connection = state["connections"].pop(provider, None)
            if not connection:
                return OAuthResult("CONNECTION_NOT_FOUND")
            self._write(state)
        for key in ("credential_ref", "refresh_ref"):
            reference = str(connection.get(key, ""))
            if reference.startswith("vault:"):
                try:
                    self.vault.delete(reference[6:])
                except CredentialVaultError:
                    pass
        return OAuthResult("DISCONNECTED", {"provider": provider})
