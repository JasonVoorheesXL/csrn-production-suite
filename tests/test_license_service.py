"""Round 15 -- license foundation.

The Ed25519 primitives are vendored (RFC 8032 Section 6 reference), so the
one place "hand-rolled" needs a correctness check is here: every RFC 8032
Section 7.1 test vector must reproduce exactly.
"""

from __future__ import annotations

import base64

import pytest

import license_service as ls
from entitlement_service import EntitlementService
from product_paths import PRODUCT_ID, resolve_product_paths


# --------------------------------------------------------------------------
# RFC 8032 Section 7.1 official test vectors (Ed25519, pure -- no ctx / ph).
# secret = 32-byte seed, public = 32 bytes, signature = 64 bytes.
# --------------------------------------------------------------------------
RFC8032_VECTORS = [
    dict(
        name="TEST 1 (empty message)",
        secret="9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60",
        public="d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a",
        message="",
        signature=(
            "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e0652249015"
            "55fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"
        ),
    ),
    dict(
        name="TEST 2 (1-byte message)",
        secret="4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb",
        public="3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c",
        message="72",
        signature=(
            "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da"
            "085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00"
        ),
    ),
    dict(
        name="TEST 3 (2-byte message)",
        secret="c5aa8df43f9f837bedb7442f31dcb7b166d38535076f094b85ce3a2e0b4458f7",
        public="fc51cd8e6218a1a38da47ed00230f0580816ed13ba3303ac5deb911548908025",
        message="af82",
        signature=(
            "6291d657deec24024827e69c3abe01a30ce548a284743a445e3680d7db5ac3ac"
            "18ff9b538d16f290ae67f760984dc6594a7c15e9716ed28dc027beceea1ec40a"
        ),
    ),
    dict(
        name="TEST SHA(abc) (64-byte message)",
        secret="833fe62409237b9d62ec77587520911e9a759cec1d19755b7da901b96dca3d42",
        public="ec172b93ad5e563bf4932c70e1245034c35467ef2efd4d64ebf819683467e2bf",
        message=(
            "ddaf35a193617abacc417349ae20413112e6fa4e89a97ea20a9eeee64b55d39a"
            "2192992a274fc1a836ba3c23a3feebbd454d4423643ce80e2a9ac94fa54ca49f"
        ),
        signature=(
            "dc2a4459e7369633a52b1bf277839a00201009a3efbf3ecb69bea2186c26b589"
            "09351fc9ac90b3ecfdfbc7c66431e0303dca179c138ac17ad9bef1177331a704"
        ),
    ),
]


@pytest.mark.parametrize("vector", RFC8032_VECTORS, ids=lambda v: v["name"])
def test_vendored_ed25519_matches_rfc8032_vectors(vector) -> None:
    secret = bytes.fromhex(vector["secret"])
    public = bytes.fromhex(vector["public"])
    message = bytes.fromhex(vector["message"])
    signature = bytes.fromhex(vector["signature"])

    assert ls.ed25519_publickey(secret) == public
    assert ls.ed25519_sign(secret, message) == signature
    assert ls.ed25519_verify(public, message, signature) is True


@pytest.mark.parametrize("vector", RFC8032_VECTORS, ids=lambda v: v["name"])
def test_vendored_ed25519_rejects_tampering(vector) -> None:
    public = bytes.fromhex(vector["public"])
    message = bytes.fromhex(vector["message"])
    signature = bytearray(bytes.fromhex(vector["signature"]))

    good = bytes(signature)
    assert ls.ed25519_verify(public, message + b"\x00", good) is False
    signature[0] ^= 0x01
    assert ls.ed25519_verify(public, message, bytes(signature)) is False
    assert ls.ed25519_verify(public, message, b"\x00" * 64) is False
    assert ls.ed25519_verify(b"\x11" * 32, message, good) is False


# --------------------------------------------------------------------------
# CSRN license layer
# --------------------------------------------------------------------------

# An ephemeral test keypair -- NOT the production key.
_TEST_SEED = bytes(range(32))
_TEST_PUB_HEX = ls.ed25519_publickey(_TEST_SEED).hex()


def _payload(**overrides):
    base = dict(
        product_id=PRODUCT_ID,
        license_id="lic-round15-001",
        status="active",
        customer="Caledonia Sports Radio Network",
        issued_at=1_700_000_000,
        expires_at=0,
        features=["captions", "core_broadcast"],
        sports=["football"],
    )
    base.update(overrides)
    return base


def test_sign_then_verify_round_trips_with_the_embedded_key() -> None:
    signed = ls.sign_license(_payload(), _TEST_SEED)
    ok, reason = ls.verify_license(signed, public_key_hex=_TEST_PUB_HEX)
    assert ok is True
    assert reason == ""


def test_verify_survives_entitlement_style_normalisation() -> None:
    # EntitlementService stamps installed_at / signature_verified and can
    # re-sort features; none of that is signed, so verification still holds.
    signed = ls.sign_license(_payload(features=["core_broadcast", "captions"]), _TEST_SEED)
    normalised = {
        **signed,
        "features": ["captions", "core_broadcast"],
        "sports": ["football"],
        "installed_at": 1_700_000_500,
        "signature_verified": True,
        "installation_id": "abc123",
        "note": "comped alpha year 1",
    }
    ok, _ = ls.verify_license(normalised, public_key_hex=_TEST_PUB_HEX)
    assert ok is True


def test_verify_rejects_a_tampered_field() -> None:
    signed = ls.sign_license(_payload(customer="Caledonia"), _TEST_SEED)
    signed["customer"] = "Someone Else"
    ok, reason = ls.verify_license(signed, public_key_hex=_TEST_PUB_HEX)
    assert ok is False
    assert reason == "LICENSE_SIGNATURE_INVALID"


def test_verify_rejects_expiry_extension() -> None:
    signed = ls.sign_license(_payload(expires_at=1_800_000_000), _TEST_SEED)
    signed["expires_at"] = 4_000_000_000
    ok, _ = ls.verify_license(signed, public_key_hex=_TEST_PUB_HEX)
    assert ok is False


def test_verify_reports_missing_and_malformed_signatures() -> None:
    body = {k: v for k, v in ls.sign_license(_payload(), _TEST_SEED).items() if k != "signature"}
    assert ls.verify_license(body, public_key_hex=_TEST_PUB_HEX) == (False, "LICENSE_SIGNATURE_MISSING")
    assert ls.verify_license({**body, "signature": "not base64!!"}, public_key_hex=_TEST_PUB_HEX)[1] == "LICENSE_SIGNATURE_MALFORMED"
    short = base64.b64encode(b"too short").decode()
    assert ls.verify_license({**body, "signature": short}, public_key_hex=_TEST_PUB_HEX)[1] == "LICENSE_SIGNATURE_WRONG_LENGTH"
    assert ls.verify_license("nope", public_key_hex=_TEST_PUB_HEX) == (False, "LICENSE_NOT_AN_OBJECT")


def test_all_zero_key_is_the_documented_fail_closed_placeholder() -> None:
    # The all-zero sentinel still fails closed if it were ever re-embedded or
    # passed explicitly. (The shipped LICENSE_PUBLIC_KEY_HEX is a real key --
    # see test_embedded_public_key_* below.)
    zero = "0" * 64
    assert ls.license_public_key_configured(zero) is False
    signed = ls.sign_license(_payload(), _TEST_SEED)
    assert ls.verify_license(signed, public_key_hex=zero) == (
        False,
        "LICENSE_PUBLIC_KEY_NOT_CONFIGURED",
    )


# --- Round 16: the owner's real embedded public key ---------------------

# Public half only; the private key never leaves the owner's machine.
_OWNER_PUBLIC_KEY_HEX = "fd748ce76657e3339844bdd4046240ee5a22ac34eb0962647c84f66918b9f2fe"


def test_embedded_public_key_is_the_owner_real_key_not_the_placeholder() -> None:
    assert ls.LICENSE_PUBLIC_KEY_HEX == _OWNER_PUBLIC_KEY_HEX
    assert ls.LICENSE_PUBLIC_KEY_HEX != "0" * 64
    assert ls.license_public_key_configured() is True  # module global
    # it is a decodable Ed25519 point, so real licenses can verify against it
    assert ls._point_decompress(bytes.fromhex(ls.LICENSE_PUBLIC_KEY_HEX)) is not None


def test_runtime_verification_uses_the_embedded_key_not_just_sig_presence() -> None:
    # A license signed by a DIFFERENT keypair must be rejected as an invalid
    # SIGNATURE (not "no key" and not "no signature") -- proving verify_license
    # actually checks against the embedded key.
    other_seed = bytes(range(100, 132))
    forged = ls.sign_license(_payload(customer="Impostor"), other_seed)
    assert "signature" in forged and len(forged["signature"]) > 40  # a signature IS present
    ok, reason = ls.verify_license(forged)  # module global = the owner's key
    assert ok is False
    assert reason == "LICENSE_SIGNATURE_INVALID"


def test_verify_pipeline_accepts_a_license_from_the_matching_private_key() -> None:
    # We do not have the owner's private key (by design), so this proves the
    # sign->verify pipeline end to end with a stand-in keypair: whatever key
    # verify_license is pointed at, a license signed by THAT key's private
    # half validates. The owner runs the same check with the real private key
    # + tools/issue_license.py against LICENSE_PUBLIC_KEY_HEX.
    seed = bytes(range(7, 39))
    pub_hex = ls.ed25519_publickey(seed).hex()
    signed = ls.sign_license(_payload(customer="Matching Key School"), seed)
    assert ls.verify_license(signed, public_key_hex=pub_hex) == (True, "")
    # ...and that exact file is rejected against the owner's embedded key.
    assert ls.verify_license(signed)[0] is False


# --------------------------------------------------------------------------
# Integration with EntitlementService (the single source of truth)
# --------------------------------------------------------------------------


def _installed_service(tmp_path, *, now=1_700_000_100):
    paths = resolve_product_paths(
        tmp_path / "app",
        env={"CSRN_RUNTIME_ROOT": str(tmp_path / "runtime")},
        frozen=False,
    )
    return EntitlementService(
        paths=paths,
        verifier=lambda p: ls.verify_license(p, public_key_hex=_TEST_PUB_HEX),
        clock=lambda: now,
        environment={},
    )


def test_signed_license_installs_and_grants_football_broadcast(tmp_path) -> None:
    service = _installed_service(tmp_path)
    signed = ls.sign_license(
        _payload(features=sorted(EntitlementService.CORE_FEATURES), sports=["football"]),
        _TEST_SEED,
    )
    result = service.install_license(signed)
    assert result.ok, result.code

    status = service.status().data["licensing"]
    assert status["valid"] is True
    assert status["license"]["customer"] == "Caledonia Sports Radio Network"
    assert service.allows("core_broadcast", sport="football") is True
    assert service.allows("captions", sport="football") is True


def test_forged_license_dropped_on_disk_is_rejected_by_status(tmp_path) -> None:
    # Task B: install_license() verifies once; a hand-edited file must still
    # be caught by status() re-verifying the on-disk signature.
    import json

    service = _installed_service(tmp_path)
    signed = ls.sign_license(_payload(features=["core_broadcast"]), _TEST_SEED)
    assert service.install_license(signed).ok
    assert service.status().data["licensing"]["valid"] is True

    record = json.loads(service.paths.license_file.read_text(encoding="utf-8"))
    record["expires_at"] = 9_999_999_999
    record["customer"] = "Pirate School"
    service.paths.license_file.write_text(json.dumps(record), encoding="utf-8")

    # A fresh service instance (no cached verification) reads the tampered file.
    fresh = _installed_service(tmp_path)
    assert fresh.status().data["licensing"]["valid"] is False
