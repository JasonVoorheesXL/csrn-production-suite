from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from facebook_connection_service import (
    FacebookConnectionService,
    FacebookCredentialVault,
)
from social_platforms import HttpResponse


@dataclass
class StubResult:
    code: str = "ACCOUNT_SAVED"

    @property
    def ok(self):
        return self.code in {"ACCOUNT_SAVED", "ACCOUNT_REMOVED"}


def _protect(value: bytes) -> bytes:
    return b"protected:" + bytes(byte ^ 0xA5 for byte in value)


def _unprotect(value: bytes) -> bytes:
    assert value.startswith(b"protected:")
    return bytes(byte ^ 0xA5 for byte in value[len(b"protected:") :])


def _json(status: int, payload: dict) -> HttpResponse:
    return HttpResponse(status, {"Content-Type": "application/json"}, json.dumps(payload).encode())


def test_oauth_page_selection_secure_storage_and_connection_test(tmp_path: Path):
    saved = []
    removed = []
    calls = []

    def transport(method, url, headers, body):
        calls.append((method, url, dict(headers), body))
        form = body.decode("utf-8") if body else ""
        if "oauth/access_token" in url and "fb_exchange_token" not in form:
            assert method == "POST"
            assert "client_secret=" in form
            return _json(200, {"access_token": "short-user-token"})
        if "oauth/access_token" in url and "fb_exchange_token" in form:
            assert method == "POST"
            return _json(200, {"access_token": "long-user-token", "expires_in": 5000})
        if "/me/accounts" in url:
            assert headers["Authorization"] == "Bearer long-user-token"
            return _json(
                200,
                {
                    "data": [
                        {
                            "id": "123456789",
                            "name": "Caledonia Sports Radio Network",
                            "link": "https://facebook.com/CaledoniaSRN",
                            "access_token": "page-token-secret",
                            "tasks": ["PROFILE_PLUS_CREATE_CONTENT"],
                            "picture": {"data": {"url": "https://example.invalid/page.jpg"}},
                        }
                    ]
                },
            )
        if "/123456789?" in url:
            assert headers["Authorization"] == "Bearer page-token-secret"
            return _json(
                200,
                {
                    "id": "123456789",
                    "name": "Caledonia Sports Radio Network",
                    "link": "https://facebook.com/CaledoniaSRN",
                    "picture": {"data": {"url": "https://example.invalid/page.jpg"}},
                },
            )
        raise AssertionError(url)

    vault_path = tmp_path / "facebook_credentials.dat"
    vault = FacebookCredentialVault(vault_path, protect=_protect, unprotect=_unprotect)
    service = FacebookConnectionService(
        settings_file=tmp_path / "facebook_connection.json",
        vault=vault,
        save_social_account=lambda payload: saved.append(dict(payload)) or StubResult(),
        remove_social_account=lambda account_id, confirmation: removed.append((account_id, confirmation)) or StubResult("ACCOUNT_REMOVED"),
        transport=transport,
        clock=lambda: 1000,
    )

    configured = service.configure_app(
        {
            "app_id": "123456789012345",
            "app_secret": "0123456789abcdef0123456789abcdef",
            "api_version": "v25.0",
            "redirect_uri": "https://example.test/api/social/facebook/callback",
        }
    )
    assert configured.ok
    assert b"0123456789abcdef" not in vault_path.read_bytes()
    assert service.status().data["facebook"]["app_secret_stored"] is True

    auth = service.authorization_url("state-token-12345678901234567890")
    assert auth.ok
    assert "pages_manage_posts" in auth.data["authorization_url"]
    assert "client_secret" not in auth.data["authorization_url"]

    completed = service.complete_authorization(
        code="authorization-code",
        received_state="state-token-12345678901234567890",
    )
    assert completed.ok
    assert completed.data["pages"][0]["id"] == "123456789"
    assert "access_token" not in completed.data["pages"][0]

    connected = service.connect_page(completed.data["selection_id"], "123456789")
    assert connected.ok
    assert saved[0]["credential_ref"] == vault.PAGE_TOKEN_REFERENCE
    assert saved[0]["page_id"] == "123456789"
    assert b"page-token-secret" not in vault_path.read_bytes()
    assert vault.resolve(vault.PAGE_TOKEN_REFERENCE) == "page-token-secret"

    tested = service.test_connection()
    assert tested.ok
    assert tested.data["facebook"]["page"]["last_test_status"] == "HEALTHY"

    disconnected = service.disconnect("DISCONNECT FACEBOOK PAGE")
    assert disconnected.ok
    assert removed == [("facebook-page", "REMOVE SOCIAL ACCOUNT")]
    assert vault.resolve(vault.PAGE_TOKEN_REFERENCE) == ""


def test_invalid_state_never_calls_provider(tmp_path: Path):
    vault = FacebookCredentialVault(tmp_path / "vault.dat", protect=_protect, unprotect=_unprotect)
    service = FacebookConnectionService(
        settings_file=tmp_path / "settings.json",
        vault=vault,
        save_social_account=lambda payload: StubResult(),
        remove_social_account=lambda account_id, confirmation: StubResult("ACCOUNT_REMOVED"),
        transport=lambda *args: (_ for _ in ()).throw(AssertionError("provider called")),
    )
    service.configure_app(
        {
            "app_id": "123456789012345",
            "app_secret": "0123456789abcdef0123456789abcdef",
            "redirect_uri": "https://example.test/api/social/facebook/callback",
        }
    )
    service.authorization_url("expected-state-token-1234567890")
    result = service.complete_authorization(
        code="code", received_state="wrong"
    )
    assert result.code == "FACEBOOK_OAUTH_STATE_INVALID"


def test_status_never_returns_secrets(tmp_path: Path):
    vault = FacebookCredentialVault(tmp_path / "vault.dat", protect=_protect, unprotect=_unprotect)
    vault.set("app_secret", "0123456789abcdef0123456789abcdef")
    vault.set("page_access_token", "page-token-secret")
    service = FacebookConnectionService(
        settings_file=tmp_path / "settings.json",
        vault=vault,
        save_social_account=lambda payload: StubResult(),
        remove_social_account=lambda account_id, confirmation: StubResult("ACCOUNT_REMOVED"),
    )
    service.settings_file.write_text(
        json.dumps(
            {
                "app_id": "123456789012345",
                "page": {"id": "123", "name": "Page"},
            }
        ),
        encoding="utf-8",
    )
    payload = json.dumps(service.status().data)
    assert "page-token-secret" not in payload
    assert "0123456789abcdef" not in payload


def test_redirect_uri_requires_https_and_exact_callback_path(tmp_path: Path):
    vault = FacebookCredentialVault(tmp_path / "vault.dat", protect=_protect, unprotect=_unprotect)
    service = FacebookConnectionService(
        settings_file=tmp_path / "settings.json",
        vault=vault,
        save_social_account=lambda payload: StubResult(),
        remove_social_account=lambda account_id, confirmation: StubResult("ACCOUNT_REMOVED"),
    )
    base = {
        "app_id": "123456789012345",
        "app_secret": "0123456789abcdef0123456789abcdef",
    }
    assert service.configure_app({**base, "redirect_uri": "http://127.0.0.1:5050/api/social/facebook/callback"}).code == "FACEBOOK_REDIRECT_URI_INVALID"
    assert service.configure_app({**base, "redirect_uri": "https://example.test/wrong"}).code == "FACEBOOK_REDIRECT_URI_INVALID"
    ok = service.configure_app({**base, "redirect_uri": "https://example.test/api/social/facebook/callback"})
    assert ok.ok
    assert service.status().data["facebook"]["redirect_uri"] == "https://example.test/api/social/facebook/callback"


def test_existing_secret_can_be_retained_when_only_https_callback_changes(tmp_path: Path):
    vault = FacebookCredentialVault(tmp_path / "vault.dat", protect=_protect, unprotect=_unprotect)
    service = FacebookConnectionService(
        settings_file=tmp_path / "settings.json",
        vault=vault,
        save_social_account=lambda payload: StubResult(),
        remove_social_account=lambda account_id, confirmation: StubResult("ACCOUNT_REMOVED"),
    )
    first = service.configure_app(
        {
            "app_id": "123456789012345",
            "app_secret": "0123456789abcdef0123456789abcdef",
            "redirect_uri": "https://first.example/api/social/facebook/callback",
        }
    )
    assert first.ok
    second = service.configure_app(
        {
            "app_id": "123456789012345",
            "app_secret": "",
            "redirect_uri": "https://second.example/api/social/facebook/callback",
        }
    )
    assert second.ok
    assert vault.get("app_secret") == "0123456789abcdef0123456789abcdef"
    changed_app = service.configure_app(
        {
            "app_id": "999999999999999",
            "app_secret": "",
            "redirect_uri": "https://second.example/api/social/facebook/callback",
        }
    )
    assert changed_app.code == "FACEBOOK_APP_SECRET_INVALID"


