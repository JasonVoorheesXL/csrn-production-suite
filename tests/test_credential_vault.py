from __future__ import annotations

import os

import pytest

from credential_vault import (
    CredentialVaultError,
    MemoryCredentialVault,
    VaultCredentialResolver,
    WindowsDpapiVault,
)


def test_memory_vault_round_trip_and_delete() -> None:
    vault = MemoryCredentialVault()
    vault.put("oauth:x:123", "secret")
    assert vault.get("oauth:x:123") == "secret"
    assert vault.references() == ["oauth:x:123"]
    vault.delete("oauth:x:123")
    assert vault.get("oauth:x:123") == ""


def test_vault_rejects_invalid_references() -> None:
    vault = MemoryCredentialVault()
    with pytest.raises(CredentialVaultError):
        vault.put("../token", "secret")
    with pytest.raises(CredentialVaultError):
        vault.get("")


def test_vault_rejects_empty_values() -> None:
    with pytest.raises(CredentialVaultError):
        MemoryCredentialVault().put("oauth:x:1", "")


def test_resolver_reads_vault_reference_without_exposing_storage() -> None:
    vault = MemoryCredentialVault()
    vault.put("oauth:x:1", "token")
    resolver = VaultCredentialResolver(vault, environment_fallback=False)
    assert resolver("vault:oauth:x:1") == "token"
    assert resolver("oauth:x:1") == ""


def test_resolver_can_use_existing_environment_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CSRN_TEST_TOKEN", "environment-token")
    resolver = VaultCredentialResolver(MemoryCredentialVault())
    assert resolver("CSRN_TEST_TOKEN") == "environment-token"


def test_windows_dpapi_vault_does_not_claim_availability_on_non_windows(tmp_path) -> None:
    vault = WindowsDpapiVault(tmp_path / "vault.json")
    if os.name != "nt":
        assert vault.available is False
        with pytest.raises(CredentialVaultError):
            vault.put("oauth:x:1", "token")


def test_reference_listing_never_contains_credential_values() -> None:
    vault = MemoryCredentialVault()
    vault.put("oauth:facebook:42", "highly-sensitive-token")
    assert "highly-sensitive-token" not in repr(vault.references())
