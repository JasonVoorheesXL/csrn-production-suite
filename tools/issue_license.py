"""Owner-only CSRN license issuer.  DO NOT SHIP THIS FILE IN ANY BUILD.

Generates a signed CSRN license file offline using the owner's Ed25519
private key. Issuance is manual only -- there is no store, no payment
processor, no activation server. Hand the resulting single JSON file to a
customer by whatever means you choose (email, USB, ...).

    # one time: make a keypair, then paste the printed public key into
    # license_service.LICENSE_PUBLIC_KEY_HEX and keep the private key safe
    .venv/Scripts/python.exe tools/issue_license.py --genkey --out-key ~/csrn_license_key.hex

    # issue a license
    .venv/Scripts/python.exe tools/issue_license.py \
        --key ~/csrn_license_key.hex \
        --org "TruHous Media" --sports football,hockey \
        --expires 2027-08-31 --note "free alpha year 1"

The PRIVATE key never belongs in this repo or in a build. See
docs/licensing.md.
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import license_service as ls  # noqa: E402
from entitlement_service import EntitlementService  # noqa: E402
from product_paths import PRODUCT_ID  # noqa: E402


def _load_seed(args) -> bytes:
    raw = ""
    if args.key_hex:
        raw = args.key_hex
    elif args.key:
        raw = Path(args.key).expanduser().read_text(encoding="utf-8")
    elif os.environ.get("CSRN_LICENSE_PRIVATE_KEY"):
        raw = os.environ["CSRN_LICENSE_PRIVATE_KEY"]
    else:
        raise SystemExit(
            "No private key. Pass --key <file>, --key-hex <hex>, or set "
            "CSRN_LICENSE_PRIVATE_KEY."
        )
    seed = bytes.fromhex("".join(raw.split()))
    if len(seed) != 32:
        raise SystemExit("Private key must be 32 bytes (64 hex characters).")
    return seed


def _parse_expiry(value: str) -> int:
    text = (value or "").strip().lower()
    if text in {"", "0", "never", "none"}:
        return 0
    try:
        day = datetime.strptime(text, "%Y-%m-%d").replace(
            hour=23, minute=59, second=59, tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise SystemExit("--expires must be YYYY-MM-DD, or 'never'.") from exc
    return int(day.timestamp())


def _parse_list(value: str) -> list[str]:
    return sorted({item.strip().lower() for item in (value or "").split(",") if item.strip()})


def do_genkey(args) -> int:
    seed = secrets.token_bytes(32)
    public_hex = ls.ed25519_publickey(seed).hex()
    out_key = Path(args.out_key).expanduser() if args.out_key else ROOT / "csrn_license_private_key.hex"
    if out_key.exists() and not args.force:
        raise SystemExit(f"{out_key} exists. Use --force to overwrite (careful).")
    out_key.write_text(seed.hex() + "\n", encoding="utf-8")
    try:
        os.chmod(out_key, 0o600)
    except OSError:
        pass
    print("Ed25519 keypair generated.\n")
    print(f"  PRIVATE key -> {out_key}")
    print("    Keep this OUT of version control and every build. Back it up")
    print("    offline. If it leaks, anyone can mint CSRN licenses.\n")
    print("  PUBLIC key (paste into license_service.LICENSE_PUBLIC_KEY_HEX):")
    print(f"    {public_hex}")
    return 0


def do_issue(args) -> int:
    seed = _load_seed(args)
    features = (
        _parse_list(args.features)
        if args.features
        else sorted(EntitlementService.CORE_FEATURES)
    )
    unknown = sorted(set(features) - EntitlementService.CORE_FEATURES)
    if unknown:
        raise SystemExit(f"Unknown feature(s): {', '.join(unknown)}")
    sports = _parse_list(args.sports)
    if not sports:
        raise SystemExit("--sports is required (comma-separated, e.g. football,hockey).")

    payload = {
        "product_id": PRODUCT_ID,
        "license_id": args.license_id or f"csrn-{secrets.token_hex(6)}",
        "status": "active",
        "customer": args.org.strip(),
        "issued_at": int(time.time()),
        "expires_at": _parse_expiry(args.expires),
        "features": features,
        "sports": sports,
    }
    signed = ls.sign_license(payload, seed)
    if args.note:
        # Owner recordkeeping only -- NOT signed, NOT read by the app.
        signed["note"] = args.note

    slug = "".join(c if c.isalnum() else "-" for c in args.org.strip().lower()).strip("-") or "customer"
    out = Path(args.out).expanduser() if args.out else ROOT / f"license-{slug}.json"
    out.write_text(json.dumps(signed, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    ok, reason = ls.verify_license(signed, public_key_hex=ls.ed25519_publickey(seed).hex())
    if not ok:
        raise SystemExit(f"Internal error: issued license did not self-verify ({reason}).")

    expiry = "never" if payload["expires_at"] == 0 else datetime.fromtimestamp(
        payload["expires_at"], tz=timezone.utc
    ).strftime("%Y-%m-%d")
    print(f"License written -> {out}")
    print(f"  customer : {payload['customer']}")
    print(f"  sports   : {', '.join(sports)}")
    print(f"  features : {', '.join(features)}")
    print(f"  expires  : {expiry}")
    print(f"  id       : {payload['license_id']}")
    if args.note:
        print(f"  note     : {args.note}  (owner metadata only)")
    return 0


def do_verify(args) -> int:
    """Sanity-check a license file the way the running app does before it
    goes out to a customer. Exit 0 iff it validates."""

    path = Path(args.verify).expanduser()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SystemExit(f"Could not read {path}: {exc}")

    # Which key to check against:
    #   default          -> license_service.LICENSE_PUBLIC_KEY_HEX (what the
    #                        shipped app verifies against);
    #   --key/--key-hex   -> the public half of that private key;
    #   --public-key-hex  -> an explicit public key.
    if args.public_key_hex:
        public_hex = args.public_key_hex.strip()
        key_src = "explicit --public-key-hex"
    elif args.key or args.key_hex:
        public_hex = ls.ed25519_publickey(_load_seed(args)).hex()
        key_src = "public half of the supplied private key"
    else:
        public_hex = ls.LICENSE_PUBLIC_KEY_HEX
        key_src = "embedded license_service.LICENSE_PUBLIC_KEY_HEX"

    ok, reason = ls.verify_license(payload, public_key_hex=public_hex)

    expires_at = int(payload.get("expires_at", 0) or 0)
    now = int(time.time())
    expired = bool(expires_at and expires_at <= now)
    expiry = (
        "never"
        if expires_at == 0
        else datetime.fromtimestamp(expires_at, tz=timezone.utc).strftime("%Y-%m-%d")
        + (" (EXPIRED)" if expired else "")
    )

    print(f"file       : {path}")
    print(f"checked vs : {key_src}")
    print(f"           : {public_hex}")
    print(f"customer   : {payload.get('customer', '')}")
    print(f"product_id : {payload.get('product_id', '')}")
    print(f"license_id : {payload.get('license_id', '')}")
    print(f"status     : {payload.get('status', '')}")
    print(f"sports     : {', '.join(payload.get('sports', []))}")
    print(f"features   : {', '.join(payload.get('features', []))}")
    print(f"expires    : {expiry}")
    if payload.get("note"):
        print(f"note       : {payload['note']}  (owner metadata only)")
    print()

    if ok and not expired:
        print("RESULT     : PASS -- signature valid, not expired.")
        return 0
    if ok and expired:
        print("RESULT     : FAIL -- signature valid but the license is EXPIRED.")
        return 1
    print(f"RESULT     : FAIL -- {reason}")
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Issue a signed CSRN license (owner only).")
    parser.add_argument("--genkey", action="store_true", help="Generate a new Ed25519 keypair.")
    parser.add_argument("--out-key", help="Where --genkey writes the private key (hex).")
    parser.add_argument("--force", action="store_true", help="Overwrite an existing key file.")

    parser.add_argument(
        "--verify",
        help="Sanity-check an existing license file (vs the embedded public "
        "key, or --key/--public-key-hex). Prints PASS/FAIL.",
    )
    parser.add_argument("--public-key-hex", help="Verify against this explicit public key (hex).")

    parser.add_argument("--org", help="Customer / organization name (the 'Licensed to' value).")
    parser.add_argument("--sports", help="Comma-separated licensed sports, e.g. football,hockey.")
    parser.add_argument("--features", help="Comma-separated feature scopes (default: all).")
    parser.add_argument("--expires", default="never", help="YYYY-MM-DD, or 'never'.")
    parser.add_argument("--note", help="Optional owner-only metadata (comped vs paid, ...). Not enforced.")
    parser.add_argument("--license-id", help="Explicit license id (default: generated).")
    parser.add_argument("--key", help="Private key file (32-byte seed as hex).")
    parser.add_argument("--key-hex", help="Private key seed as hex (avoid on shared shells).")
    parser.add_argument("--out", help="Output license file path.")
    args = parser.parse_args(argv)

    if args.genkey:
        return do_genkey(args)
    if args.verify:
        return do_verify(args)
    if not args.org:
        parser.error("need --org (issue), --genkey, or --verify <file>")
    return do_issue(args)


if __name__ == "__main__":
    raise SystemExit(main())
