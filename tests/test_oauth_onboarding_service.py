from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from credential_vault import MemoryCredentialVault
from oauth_onboarding_service import HttpResponse, OAuthOnboardingService


class Configured:
    ok = True
    code = "ACCOUNT_CONFIGURED"


def build_service(tmp_path: Path, *, environment=None, transport=None, clock=None):
    accounts: list[dict] = []

    def configure(payload):
        accounts.append(dict(payload))
        return Configured()

    service = OAuthOnboardingService(
        state_file=tmp_path / "oauth.json",
        vault=MemoryCredentialVault(),
        configure_social_account=configure,
        environment=environment or {},
        transport=transport or (lambda *args: HttpResponse(500, {}, b"")),
        clock=clock or (lambda: 1000),
    )
    return service, accounts


def facebook_transport(method, url, headers, body):
    if url.endswith("/exchange/facebook"):
        return HttpResponse(
            200,
            {},
            json.dumps(
                {
                    "page_access_token": "page-secret",
                    "page_id": "99",
                    "page_name": "Demo Sports",
                }
            ).encode(),
        )
    if url.endswith("/me"):
        return HttpResponse(200, {}, json.dumps({"id": "99", "name": "Demo Sports"}).encode())
    return HttpResponse(404, {}, b"")


def connect_facebook(service: OAuthOnboardingService):
    started = service.start("facebook", "http://127.0.0.1:5050/setup/oauth/facebook/callback")
    state_token = parse_qs(urlparse(started.data["authorize_url"]).query)["state"][0]
    return service.complete("facebook", state_token=state_token, code="broker-code")


def test_status_reports_only_facebook_as_connectable_provider(tmp_path: Path) -> None:
    service, _ = build_service(tmp_path, environment={"CSRN_META_OAUTH_BROKER_URL": "https://oauth.possumfrog.example"})
    result = service.status()
    assert result.ok
    assert [row["id"] for row in result.data["providers"]] == ["facebook"]
    assert result.data["providers"][0]["provider_configured"] is True
    assert result.data["providers"][0]["vault_available"] is True


def test_x_oauth_start_is_intentionally_unsupported(tmp_path: Path) -> None:
    service, _ = build_service(tmp_path, environment={"CSRN_X_CLIENT_ID": "unused"})
    assert service.start("x", "http://127.0.0.1:5050/setup/oauth/x/callback").code == "PROVIDER_UNSUPPORTED"


def test_x_oauth_completion_is_intentionally_unsupported(tmp_path: Path) -> None:
    service, _ = build_service(tmp_path)
    assert service.complete("x", state_token="state", code="code").code == "PROVIDER_UNSUPPORTED"


def test_facebook_start_requires_configured_broker(tmp_path: Path) -> None:
    service, _ = build_service(tmp_path)
    result = service.start("facebook", "http://127.0.0.1:5050/setup/oauth/facebook/callback")
    assert result.code == "PROVIDER_APPLICATION_NOT_CONFIGURED"


def test_facebook_start_rejects_remote_callback_urls(tmp_path: Path) -> None:
    service, _ = build_service(tmp_path, environment={"CSRN_META_OAUTH_BROKER_URL": "https://oauth.possumfrog.example"})
    assert service.start("facebook", "https://example.com/callback").code == "CALLBACK_URL_INVALID"


def test_facebook_start_uses_configured_broker_without_meta_secret(tmp_path: Path) -> None:
    service, _ = build_service(tmp_path, environment={"CSRN_META_OAUTH_BROKER_URL": "https://oauth.possumfrog.example"})
    result = service.start("facebook", "http://127.0.0.1:5050/setup/oauth/facebook/callback")
    assert result.code == "AUTHORIZATION_READY"
    assert result.data["authorize_url"].startswith("https://oauth.possumfrog.example/authorize/facebook?")
    assert "app_secret" not in result.data["authorize_url"]


def test_facebook_completion_stores_page_token_only_in_vault(tmp_path: Path) -> None:
    service, accounts = build_service(
        tmp_path,
        environment={"CSRN_META_OAUTH_BROKER_URL": "https://oauth.possumfrog.example"},
        transport=facebook_transport,
    )
    result = connect_facebook(service)
    assert result.code == "CONNECTED"
    assert accounts[0]["platform"] == "facebook"
    assert accounts[0]["page_id"] == "99"
    assert accounts[0]["auto_publish"] is False
    persisted = (tmp_path / "oauth.json").read_text(encoding="utf-8")
    assert "page-secret" not in persisted
    assert service.vault.get("oauth:facebook:99") == "page-secret"


def test_facebook_disconnect_requires_confirmation_and_removes_secret(tmp_path: Path) -> None:
    service, _ = build_service(
        tmp_path,
        environment={"CSRN_META_OAUTH_BROKER_URL": "https://oauth.possumfrog.example"},
        transport=facebook_transport,
    )
    connect_facebook(service)
    assert service.disconnect("facebook", "wrong").code == "DISCONNECT_CONFIRMATION_REQUIRED"
    assert service.disconnect("facebook", "DISCONNECT SOCIAL ACCOUNT").code == "DISCONNECTED"
    assert service.vault.get("oauth:facebook:99") == ""


def test_facebook_connection_test_updates_safe_health_metadata(tmp_path: Path) -> None:
    service, _ = build_service(
        tmp_path,
        environment={"CSRN_META_OAUTH_BROKER_URL": "https://oauth.possumfrog.example"},
        transport=facebook_transport,
    )
    connect_facebook(service)
    result = service.test_connection("facebook")
    assert result.code == "CONNECTION_TESTED"
    provider = service.status().data["providers"][0]
    assert provider["last_test_ok"] is True
