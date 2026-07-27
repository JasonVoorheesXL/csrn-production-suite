from __future__ import annotations

import base64
import ctypes
import json
import os
from ctypes import wintypes
from pathlib import Path
from threading import Lock
from typing import Protocol


class CredentialVaultError(RuntimeError):
    pass


class CredentialVault(Protocol):
    @property
    def available(self) -> bool: ...

    def put(self, reference: str, value: str) -> None: ...

    def get(self, reference: str) -> str: ...

    def delete(self, reference: str) -> None: ...

    def references(self) -> list[str]: ...


class MemoryCredentialVault:
    """Test-only vault. Production wiring uses WindowsDpapiVault."""

    def __init__(self) -> None:
        self._values: dict[str, str] = {}

    @property
    def available(self) -> bool:
        return True

    def put(self, reference: str, value: str) -> None:
        reference = _normalize_reference(reference)
        if not value:
            raise CredentialVaultError("Credential value is empty.")
        self._values[reference] = str(value)

    def get(self, reference: str) -> str:
        return self._values.get(_normalize_reference(reference), "")

    def delete(self, reference: str) -> None:
        self._values.pop(_normalize_reference(reference), None)

    def references(self) -> list[str]:
        return sorted(self._values)


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _normalize_reference(reference: str) -> str:
    value = str(reference or "").strip()
    if not value or len(value) > 160:
        raise CredentialVaultError("Credential reference is invalid.")
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789:._-")
    if any(character not in allowed for character in value):
        raise CredentialVaultError("Credential reference contains unsupported characters.")
    return value


class WindowsDpapiVault:
    """Per-user encrypted credential storage using Windows DPAPI.

    Only encrypted blobs and reference names are written to disk. The Windows user
    profile that protected a value is required to decrypt it.
    """

    def __init__(self, state_file: Path, *, entropy: bytes = b"CSRN-PRODUCTION-SUITE-V1") -> None:
        self.state_file = Path(state_file)
        self._entropy = bytes(entropy)
        self._lock = Lock()
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

    @property
    def available(self) -> bool:
        return os.name == "nt" and hasattr(ctypes, "windll")

    @staticmethod
    def _blob(data: bytes) -> tuple[_DataBlob, ctypes.Array[ctypes.c_char]]:
        buffer = ctypes.create_string_buffer(data)
        blob = _DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
        return blob, buffer

    def _protect(self, value: str) -> str:
        if not self.available:
            raise CredentialVaultError("Protected credential storage is available only on Windows.")
        raw = value.encode("utf-8")
        incoming, incoming_buffer = self._blob(raw)
        entropy, entropy_buffer = self._blob(self._entropy)
        outgoing = _DataBlob()
        result = ctypes.windll.crypt32.CryptProtectData(
            ctypes.byref(incoming),
            "CSRN credential",
            ctypes.byref(entropy),
            None,
            None,
            0,
            ctypes.byref(outgoing),
        )
        _ = incoming_buffer, entropy_buffer
        if not result:
            raise CredentialVaultError("Windows could not protect the credential.")
        try:
            encrypted = ctypes.string_at(outgoing.pbData, outgoing.cbData)
            return base64.b64encode(encrypted).decode("ascii")
        finally:
            ctypes.windll.kernel32.LocalFree(outgoing.pbData)

    def _unprotect(self, encoded: str) -> str:
        if not self.available:
            raise CredentialVaultError("Protected credential storage is available only on Windows.")
        try:
            raw = base64.b64decode(encoded.encode("ascii"), validate=True)
        except (ValueError, UnicodeError) as exc:
            raise CredentialVaultError("Stored credential is corrupted.") from exc
        incoming, incoming_buffer = self._blob(raw)
        entropy, entropy_buffer = self._blob(self._entropy)
        outgoing = _DataBlob()
        result = ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(incoming),
            None,
            ctypes.byref(entropy),
            None,
            None,
            0,
            ctypes.byref(outgoing),
        )
        _ = incoming_buffer, entropy_buffer
        if not result:
            raise CredentialVaultError("Windows could not decrypt the credential for this user.")
        try:
            return ctypes.string_at(outgoing.pbData, outgoing.cbData).decode("utf-8")
        finally:
            ctypes.windll.kernel32.LocalFree(outgoing.pbData)

    def _load(self) -> dict[str, str]:
        try:
            payload = json.loads(self.state_file.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return {}
        values = payload.get("credentials", {}) if isinstance(payload, dict) else {}
        return {str(key): str(value) for key, value in values.items()} if isinstance(values, dict) else {}

    def _write(self, values: dict[str, str]) -> None:
        temporary = self.state_file.with_name(f".{self.state_file.name}.tmp")
        temporary.write_text(
            json.dumps({"schema": 1, "credentials": values}, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        temporary.replace(self.state_file)

    def put(self, reference: str, value: str) -> None:
        reference = _normalize_reference(reference)
        value = str(value or "")
        if not value:
            raise CredentialVaultError("Credential value is empty.")
        with self._lock:
            values = self._load()
            values[reference] = self._protect(value)
            self._write(values)

    def get(self, reference: str) -> str:
        reference = _normalize_reference(reference)
        with self._lock:
            encoded = self._load().get(reference, "")
        return self._unprotect(encoded) if encoded else ""

    def delete(self, reference: str) -> None:
        reference = _normalize_reference(reference)
        with self._lock:
            values = self._load()
            if reference in values:
                values.pop(reference, None)
                self._write(values)

    def references(self) -> list[str]:
        with self._lock:
            return sorted(self._load())


class VaultCredentialResolver:
    """Resolve `vault:<reference>` values without exposing stored credentials."""

    def __init__(self, vault: CredentialVault, *, environment_fallback: bool = True) -> None:
        self.vault = vault
        self.environment_fallback = bool(environment_fallback)

    def __call__(self, reference: str) -> str:
        reference = str(reference or "").strip()
        if reference.startswith("vault:"):
            try:
                return self.vault.get(reference[6:])
            except CredentialVaultError:
                return ""
        return os.environ.get(reference, "") if self.environment_fallback and reference else ""
