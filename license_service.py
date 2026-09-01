"""Offline license signature verification for CSRN Production Suite.

Round 15 (license foundation). Design decisions:

* **Vendored pure-Python Ed25519** (RFC 8032 Section 6 reference
  implementation, public domain) -- no ``cryptography`` / ``pynacl`` /
  native crypto dependency is added to the PyInstaller bundle. The threat
  model is a *soft social deterrent*, not a hard control: a signed JSON
  file, validated entirely offline against an embedded public key, with
  manual owner-only issuance. No machine locking. No phone-home.
* **Feeds EntitlementService** via its existing ``verifier`` slot
  (``Callable[[dict], tuple[bool, str]]``). There is no second, parallel
  "is this app licensed" gate -- ``EntitlementService.status()`` /
  ``allows()`` / ``install_license()`` remain the single source of truth.

The PRIVATE signing key lives ONLY with the owner -- never committed to
this repo, never bundled into any build. ``tools/issue_license.py``
(owner-run, never shipped) is the only code that touches it.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from typing import Any, Mapping


# ===========================================================================
# Vendored Ed25519 -- RFC 8032 Section 6 "Ed25519 Python illustration".
# Public domain. Verified against the RFC 8032 Section 7.1 test vectors in
# tests/test_license_service.py. Do not edit the maths below by hand.
# ===========================================================================

_p = 2 ** 255 - 19
_q = 2 ** 252 + 27742317777372353535851937790883648493  # group order


def _sha512(data: bytes) -> bytes:
    return hashlib.sha512(data).digest()


def _sha512_modq(data: bytes) -> int:
    return int.from_bytes(_sha512(data), "little") % _q


# Points are (X, Y, Z, T) in extended homogeneous coordinates:
# x = X/Z, y = Y/Z, x*y = T/Z.

def _point_add(P, Q):
    A = (P[1] - P[0]) * (Q[1] - Q[0]) % _p
    B = (P[1] + P[0]) * (Q[1] + Q[0]) % _p
    C = 2 * P[3] * Q[3] * _d % _p
    D = 2 * P[2] * Q[2] % _p
    E, F, G, H = B - A, D - C, D + C, B + A
    return (E * F % _p, G * H % _p, F * G % _p, E * H % _p)


def _point_mul(s: int, P):
    Q = (0, 1, 1, 0)  # neutral element
    while s > 0:
        if s & 1:
            Q = _point_add(Q, P)
        P = _point_add(P, P)
        s >>= 1
    return Q


def _point_equal(P, Q) -> bool:
    if (P[0] * Q[2] - Q[0] * P[2]) % _p != 0:
        return False
    if (P[1] * Q[2] - Q[1] * P[2]) % _p != 0:
        return False
    return True


_d = -121665 * pow(121666, _p - 2, _p) % _p
_modp_sqrt_m1 = pow(2, (_p - 1) // 4, _p)


def _recover_x(y: int, sign: int):
    if y >= _p:
        return None
    x2 = (y * y - 1) * pow(_d * y * y + 1, _p - 2, _p) % _p
    if x2 == 0:
        if sign:
            return None
        return 0
    x = pow(x2, (_p + 3) // 8, _p)
    if (x * x - x2) % _p != 0:
        x = x * _modp_sqrt_m1 % _p
    if (x * x - x2) % _p != 0:
        return None
    if (x & 1) != sign:
        x = _p - x
    return x


_g_y = 4 * pow(5, _p - 2, _p) % _p
_g_x = _recover_x(_g_y, 0)
_G = (_g_x, _g_y, 1, _g_x * _g_y % _p)


def _point_compress(P) -> bytes:
    zinv = pow(P[2], _p - 2, _p)
    x = P[0] * zinv % _p
    y = P[1] * zinv % _p
    return int.to_bytes(y | ((x & 1) << 255), 32, "little")


def _point_decompress(s: bytes):
    if len(s) != 32:
        raise ValueError("Invalid input length for decompression")
    y = int.from_bytes(s, "little")
    sign = y >> 255
    y &= (1 << 255) - 1
    x = _recover_x(y, sign)
    if x is None:
        return None
    return (x, y, 1, x * y % _p)


def _secret_expand(secret: bytes):
    if len(secret) != 32:
        raise ValueError("Bad size of private key")
    h = _sha512(secret)
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8
    a |= (1 << 254)
    return (a, h[32:])


def ed25519_publickey(secret: bytes) -> bytes:
    """Derive the 32-byte Ed25519 public key from a 32-byte seed."""
    a, _ = _secret_expand(secret)
    return _point_compress(_point_mul(a, _G))


def ed25519_sign(secret: bytes, msg: bytes) -> bytes:
    """Produce a 64-byte Ed25519 signature over ``msg`` with a 32-byte seed."""
    a, prefix = _secret_expand(secret)
    A = _point_compress(_point_mul(a, _G))
    r = _sha512_modq(prefix + msg)
    R = _point_mul(r, _G)
    Rs = _point_compress(R)
    h = _sha512_modq(Rs + A + msg)
    s = (r + h * a) % _q
    return Rs + int.to_bytes(s, 32, "little")


def ed25519_verify(public: bytes, msg: bytes, signature: bytes) -> bool:
    """Return True iff ``signature`` is a valid Ed25519 signature of ``msg``."""
    if len(public) != 32 or len(signature) != 64:
        return False
    try:
        A = _point_decompress(public)
    except ValueError:
        return False
    if not A:
        return False
    Rs = signature[:32]
    try:
        R = _point_decompress(Rs)
    except ValueError:
        return False
    if not R:
        return False
    s = int.from_bytes(signature[32:], "little")
    if s >= _q:
        return False
    h = _sha512_modq(Rs + public + msg)
    sB = _point_mul(s, _G)
    hA = _point_mul(h, A)
    return _point_equal(sB, _point_add(R, hA))


# ===========================================================================
# CSRN license layer
# ===========================================================================

# Embedded PUBLIC verification key (Ed25519, 32 bytes, hex). This is the
# public half only -- safe to commit and to bundle. The matching PRIVATE key
# is the owner's alone and must never appear in this repo or any build; it is
# used only by tools/issue_license.py on the owner's own machine.
#
# An all-zero value here is the "not configured" placeholder and makes
# verify_license() fail closed. The real key below was supplied by the owner
# (Round 16); regenerate with `tools/issue_license.py --genkey` and rotate
# this constant if the private key is ever lost or compromised.
LICENSE_PUBLIC_KEY_HEX = "fd748ce76657e3339844bdd4046240ee5a22ac34eb0962647c84f66918b9f2fe"

SIGNATURE_FIELD = "signature"

# Exactly the fields the signature covers. Extra keys a payload may carry
# (installed_at, signature_verified, installation_id, provider, note, ...)
# are NOT signed and NOT part of the canonical message, so EntitlementService
# normalising / stamping the stored record does not break re-verification.
SIGNED_FIELDS = (
    "product_id",
    "license_id",
    "status",
    "customer",
    "issued_at",
    "expires_at",
    "features",
    "sports",
)


def _canonical_message(payload: Mapping[str, Any]) -> bytes:
    """Deterministic bytes the signature is computed over."""
    body: dict[str, Any] = {}
    for field in SIGNED_FIELDS:
        value = payload.get(field)
        if field in ("features", "sports"):
            value = sorted(str(item) for item in (value or []))
        body[field] = value
    return json.dumps(
        body, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def sign_license(payload: Mapping[str, Any], secret_key: bytes) -> dict[str, Any]:
    """Return ``payload`` (signed fields only) plus a base64 ``signature``.

    Used exclusively by tools/issue_license.py with the owner's private key.
    """
    body = {field: payload.get(field) for field in SIGNED_FIELDS}
    body["features"] = sorted(str(item) for item in (body.get("features") or []))
    body["sports"] = sorted(str(item) for item in (body.get("sports") or []))
    signature = ed25519_sign(secret_key, _canonical_message(body))
    return {**body, SIGNATURE_FIELD: base64.b64encode(signature).decode("ascii")}


def verify_license(
    payload: Any, *, public_key_hex: str | None = None
) -> tuple[bool, str]:
    """EntitlementService ``verifier``: ``(payload) -> (ok, reason)``.

    Verifies only the Ed25519 signature over :data:`SIGNED_FIELDS`. Expiry
    and status are enforced by EntitlementService.status(), unchanged.
    """
    if not isinstance(payload, Mapping):
        return False, "LICENSE_NOT_AN_OBJECT"

    raw_signature = str(payload.get(SIGNATURE_FIELD, "")).strip()
    if not raw_signature:
        return False, "LICENSE_SIGNATURE_MISSING"
    try:
        signature = base64.b64decode(raw_signature, validate=True)
    except (ValueError, binascii.Error):
        return False, "LICENSE_SIGNATURE_MALFORMED"
    if len(signature) != 64:
        return False, "LICENSE_SIGNATURE_WRONG_LENGTH"

    key_hex = (public_key_hex or LICENSE_PUBLIC_KEY_HEX).strip()
    try:
        public_key = bytes.fromhex(key_hex)
    except ValueError:
        return False, "LICENSE_PUBLIC_KEY_INVALID"
    if len(public_key) != 32 or public_key == b"\x00" * 32:
        return False, "LICENSE_PUBLIC_KEY_NOT_CONFIGURED"

    try:
        ok = ed25519_verify(public_key, _canonical_message(payload), signature)
    except Exception:  # noqa: BLE001 -- any maths failure is a bad signature
        return False, "LICENSE_SIGNATURE_INVALID"
    return (True, "") if ok else (False, "LICENSE_SIGNATURE_INVALID")


def license_public_key_configured(public_key_hex: str | None = None) -> bool:
    """True once the owner has embedded a real (non-placeholder) public key."""
    key_hex = (public_key_hex or LICENSE_PUBLIC_KEY_HEX).strip()
    try:
        key = bytes.fromhex(key_hex)
    except ValueError:
        return False
    return len(key) == 32 and key != b"\x00" * 32
