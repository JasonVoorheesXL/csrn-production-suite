"""Round 15 Task D -- the owner-only license issuer CLI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import license_service as ls
from entitlement_service import EntitlementService
from product_paths import resolve_product_paths
from tools import issue_license


def _genkey(tmp_path: Path) -> tuple[Path, str]:
    key_file = tmp_path / "key.hex"
    assert issue_license.main(["--genkey", "--out-key", str(key_file)]) == 0
    seed = bytes.fromhex(key_file.read_text(encoding="utf-8").strip())
    return key_file, ls.ed25519_publickey(seed).hex()


def test_genkey_writes_a_usable_32_byte_seed(tmp_path: Path) -> None:
    key_file, public_hex = _genkey(tmp_path)
    assert len(bytes.fromhex(key_file.read_text(encoding="utf-8").strip())) == 32
    assert len(bytes.fromhex(public_hex)) == 32
    assert ls.license_public_key_configured(public_hex) is True


def test_issue_produces_a_license_that_verifies_with_the_matching_key(tmp_path: Path) -> None:
    key_file, public_hex = _genkey(tmp_path)
    out = tmp_path / "license.json"
    rc = issue_license.main([
        "--key", str(key_file),
        "--org", "TruHous Media",
        "--sports", "football,hockey",
        "--expires", "2027-08-31",
        "--note", "free alpha year 1",
        "--out", str(out),
    ])
    assert rc == 0

    record = json.loads(out.read_text(encoding="utf-8"))
    assert record["customer"] == "TruHous Media"
    assert record["sports"] == ["football", "hockey"]
    assert record["expires_at"] > 0
    # --note is owner metadata: present in the file, NOT part of the signature.
    assert record["note"] == "free alpha year 1"
    ok, _ = ls.verify_license(record, public_key_hex=public_hex)
    assert ok is True
    # stripping the note does not change validity
    without_note = {k: v for k, v in record.items() if k != "note"}
    assert ls.verify_license(without_note, public_key_hex=public_hex)[0] is True


def test_issued_license_installs_through_entitlement_service(tmp_path: Path) -> None:
    key_file, public_hex = _genkey(tmp_path)
    out = tmp_path / "license.json"
    issue_license.main([
        "--key", str(key_file), "--org", "Example School",
        "--sports", "football", "--expires", "never", "--out", str(out),
    ])
    record = json.loads(out.read_text(encoding="utf-8"))
    assert record["expires_at"] == 0  # "never"

    paths = resolve_product_paths(
        tmp_path / "app",
        env={"CSRN_RUNTIME_ROOT": str(tmp_path / "runtime")},
        frozen=False,
    )
    service = EntitlementService(
        paths=paths,
        verifier=lambda p: ls.verify_license(p, public_key_hex=public_hex),
        clock=lambda: 1_800_000_000,
    )
    assert service.install_license(record).ok
    status = service.status().data["licensing"]
    assert status["valid"] is True
    assert status["license"]["customer"] == "Example School"
    assert service.allows("core_broadcast", sport="football") is True


def test_tampering_the_issued_file_breaks_verification(tmp_path: Path) -> None:
    key_file, public_hex = _genkey(tmp_path)
    out = tmp_path / "license.json"
    issue_license.main([
        "--key", str(key_file), "--org", "Real School",
        "--sports", "football", "--out", str(out),
    ])
    record = json.loads(out.read_text(encoding="utf-8"))
    record["customer"] = "Pirate School"
    assert ls.verify_license(record, public_key_hex=public_hex)[0] is False


def test_issue_rejects_unknown_feature_and_missing_sports(tmp_path: Path) -> None:
    key_file, _ = _genkey(tmp_path)
    with pytest.raises(SystemExit):
        issue_license.main([
            "--key", str(key_file), "--org", "X",
            "--sports", "football", "--features", "core_broadcast,teleport",
        ])
    with pytest.raises(SystemExit):
        issue_license.main(["--key", str(key_file), "--org", "X", "--sports", ""])


def test_issuer_file_is_marked_never_to_ship() -> None:
    src = Path(issue_license.__file__).read_text(encoding="utf-8")
    assert "DO NOT SHIP THIS FILE IN ANY BUILD" in src
