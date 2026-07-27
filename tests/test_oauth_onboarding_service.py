from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from credential_vault import MemoryCredentialVault
from oauth_onboarding_service import HttpResponse, OAuthOnboardingService


class Configured:
    ok = True
    code = "ACCOUNT_CONFIGURED"


def build_service(tmp_path: Path, *, environment=None, transport=None):
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
        clock=lambda: 1000,
    )
    return service, accounts


def test_status_reports_provider_and_vault_readiness(tmp_path: Path) -> None:
    service, _ = build_service(tmp_path, environment={"CSRN_X_CLIENT_ID": "client"})
    result = service.status()
    assert result.ok
    providers = {row["id"]: row for row in result.data["providers"]}
    assert providers["x"]["provider_configured"] is True
    assert providers["x"]["vault_available"] is True
    assert providers["facebook"]["provider_configured"] is False


def test_x_start_builds_pkce_authorization_url_and_persists_no_token(tmp_path: Path) -> None:
    service, _ = build_service(tmp_path, environment={"CSRN_X_CLIENT_ID": "client-123"})
    result = service.start("x", "http://127.0.0.1:5050/setup/oauth/x/callback")
    assert result.code == "AUTHORIZATION_READY"
    parsed = urlparse(result.data["authorize_url"])
    query = parse_qs(parsed.query)
    assert parsed.netloc == "x.com"
    assert query["client_id"] == ["client-123"]
    assert query["code_challenge_method"] == ["S256"]
    assert "offline.access" in query["scope"][0]
    assert "media.write" in query["scope"][0]
    state = json.loads((tmp_path / "oauth.json").read_text(encoding="utf-8"))
    assert "access_token" not in json.dumps(state)
    assert "refresh_token" not in json.dumps(state)


def test_start_rejects_unconfigured_provider_application(tmp_path: Path) -> None:
    service, _ = build_service(tmp_path)
    assert service.start("x", "http://127.0.0.1:5050/setup/oauth/x/callback").code == "PROVIDER_APPLICATION_NOT_CONFIGURED"
    assert service.start("facebook", "http://127.0.0.1:5050/setup/oauth/facebook/callback").code == "PROVIDER_APPLICATION_NOT_CONFIGURED"


def test_start_rejects_remote_callback_urls(tmp_path: Path) -> None:
    service, _ = build_service(tmp_path, environment={"CSRN_X_CLIENT_ID": "client"})
    assert service.start("x", "https://example.com/callback").code == "CALLBACK_URL_INVALID"


def test_x_completion_stores_tokens_only_in_vault_and_configures_social_account(tmp_path: Path) -> None:
    calls = []

    def transport(method, url, headers, body):
        calls.append((method, url, headers, body))
        if url.endswith("/oauth2/token"):
            return HttpResponse(200, {}, json.dumps({"access_token": "access-secret", "refresh_token": "refresh-secret", "scope": "tweet.write users.read"}).encode())
        if url.endswith("/users/me"):
            return HttpResponse(200, {}, json.dumps({"data": {"id": "77", "username": "demoaccount", "name": "Demo Account"}}).encode())
        return HttpResponse(404, {}, b"")

    service, accounts = build_service(tmp_path, environment={"CSRN_X_CLIENT_ID": "client"}, transport=transport)
    started = service.start("x", "http://127.0.0.1:5050/setup/oauth/x/callback")
    state_token = parse_qs(urlparse(started.data["authorize_url"]).query)["state"][0]
    result = service.complete("x", state_token=state_token, code="authorization-code")
    assert result.code == "CONNECTED"
    assert accounts[0]["platform"] == "x"
    assert accounts[0]["credential_ref"] == "vault:oauth:x:77"
    assert accounts[0]["auto_publish"] is False
    persisted = (tmp_path / "oauth.json").read_text(encoding="utf-8")
    assert "access-secret" not in persisted
    assert "refresh-secret" not in persisted
    assert service.vault.get("oauth:x:77") == "access-secret"
    assert service.vault.get("oauth:x:77:refresh") == "refresh-secret"


def test_completion_rejects_invalid_or_expired_state(tmp_path: Path) -> None:
    service, _ = build_service(tmp_path, environment={"CSRN_X_CLIENT_ID": "client"})
    assert service.complete("x", state_token="bad", code="code").code == "OAUTH_STATE_INVALID"


def test_facebook_start_uses_configured_broker_not_meta_secret(tmp_path: Path) -> None:
    service, _ = build_service(tmp_path, environment={"CSRN_META_OAUTH_BROKER_URL": "https://oauth.possumfrog.example"})
    result = service.start("facebook", "http://127.0.0.1:5050/setup/oauth/facebook/callback")
    assert result.code == "AUTHORIZATION_READY"
    assert result.data["authorize_url"].startswith("https://oauth.possumfrog.example/authorize/facebook?")
    assert "app_secret" not in result.data["authorize_url"]


def test_facebook_broker_completion_configures_selected_page(tmp_path: Path) -> None:
    def transport(method, url, headers, body):
        assert url == "https://oauth.possumfrog.example/exchange/facebook"
        return HttpResponse(200, {}, json.dumps({"page_access_token": "page-secret", "page_id": "99", "page_name": "Demo Sports"}).encode())

    service, accounts = build_service(tmp_path, environment={"CSRN_META_OAUTH_BROKER_URL": "https://oauth.possumfrog.example"}, transport=transport)
    started = service.start("facebook", "http://127.0.0.1:5050/setup/oauth/facebook/callback")
    state_token = parse_qs(urlparse(started.data["authorize_url"]).query)["state"][0]
    result = service.complete("facebook", state_token=state_token, code="broker-code")
    assert result.code == "CONNECTED"
    assert accounts[0]["platform"] == "facebook"
    assert accounts[0]["page_id"] == "99"
    assert service.vault.get("oauth:facebook:99") == "page-secret"


def test_disconnect_requires_confirmation_and_removes_vault_credentials(tmp_path: Path) -> None:
    def transport(method, url, headers, body):
        if url.endswith("/oauth2/token"):
            return HttpResponse(200, {}, json.dumps({"access_token": "token"}).encode())
        return HttpResponse(200, {}, json.dumps({"data": {"id": "7", "username": "user"}}).encode())

    service, _ = build_service(tmp_path, environment={"CSRN_X_CLIENT_ID": "client"}, transport=transport)
    started = service.start("x", "http://127.0.0.1:5050/setup/oauth/x/callback")
    state_token = parse_qs(urlparse(started.data["authorize_url"]).query)["state"][0]
    service.complete("x", state_token=state_token, code="code")
    assert service.disconnect("x", "wrong").code == "DISCONNECT_CONFIRMATION_REQUIRED"
    assert service.disconnect("x", "DISCONNECT SOCIAL ACCOUNT").code == "DISCONNECTED"
    assert service.vault.get("oauth:x:7") == ""


def test_connection_test_updates_safe_health_metadata(tmp_path: Path) -> None:
    responses = []

    def transport(method, url, headers, body):
        responses.append(url)
        if url.endswith("/oauth2/token"):
            return HttpResponse(200, {}, json.dumps({"access_token": "token"}).encode())
        return HttpResponse(200, {}, json.dumps({"data": {"id": "7", "username": "user"}}).encode())

    service, _ = build_service(tmp_path, environment={"CSRN_X_CLIENT_ID": "client"}, transport=transport)
    started = service.start("x", "http://127.0.0.1:5050/setup/oauth/x/callback")
    state_token = parse_qs(urlparse(started.data["authorize_url"]).query)["state"][0]
    service.complete("x", state_token=state_token, code="code")
    result = service.test_connection("x")
    assert result.code == "CONNECTION_TESTED"
    status = service.status().data["providers"][0]
    assert status["last_test_ok"] is True
