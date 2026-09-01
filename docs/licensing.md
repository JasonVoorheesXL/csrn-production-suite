# CSRN Licensing (Round 15 -- license enforcement foundation)

An **offline, server-free** license gate. A signed JSON file, validated
entirely against a public key embedded in the app. **No machine locking,
no phone-home.** Issuance is **manual only, owner-run** -- there is no
store, payment processor, or self-serve component.

The threat model is a **soft social deterrent**, not a hard control: a
shared or copied install still visibly says who it is really licensed to
(the settings screen shows "Licensed to: &lt;org&gt;"), and broadcast
controls are held behind a "license required" screen until a valid file
is installed.

## Pieces

| File | Role | Ships? |
|---|---|---|
| `license_service.py` | Vendored Ed25519 (RFC 8032 §6 reference, public domain) + `verify_license()`; embeds the **public** key `LICENSE_PUBLIC_KEY_HEX` | yes |
| `entitlement_service.py` | Single source of truth (`status()` / `allows()` / `install_license()`); its `verifier` slot is `license_service.verify_license` | yes |
| `app.py` `_install_license_gate` | In an installed build with no valid license: `/` → `templates/license_required.html`, broadcast APIs → `402 LICENSE_REQUIRED`; health / licensing / diagnostics / static / overlay stay open | yes |
| `tools/issue_license.py` | Owner CLI that signs license files with the **private** key | **never** |
| the private key (`*.hex`) | The owner's alone | **never** (gitignored) |

## What the signature covers

Exactly these fields, canonically serialised (`license_service.SIGNED_FIELDS`):

```
product_id, license_id, status, customer, issued_at, expires_at, features, sports
```

`features`/`sports` are sorted before signing. Anything else a license file
carries -- `note`, and the `installed_at` / `signature_verified` /
`installation_id` that `EntitlementService` stamps on the stored record --
is **not signed** and does not affect verification.

## One-time setup: generate the keypair

```bash
.venv/Scripts/python.exe tools/issue_license.py --genkey --out-key ~/csrn_license_key.hex
```

This prints the **public** key. Paste it into `license_service.py`:

```python
LICENSE_PUBLIC_KEY_HEX = "35f6...<64 hex chars>..."
```

Until a real key is embedded, `LICENSE_PUBLIC_KEY_HEX` is an all-zero
placeholder and `verify_license()` fails closed
(`LICENSE_PUBLIC_KEY_NOT_CONFIGURED`) -- an installed build without a
configured key stays in the "license required" state; a source checkout is
unaffected (see "The existing Caledonia install" below).

### Keeping the private key safe

- It lives **only** with the owner -- never in this repo (`*.hex` and
  `license-*.json` are gitignored), never in a PyInstaller bundle.
- Back it up **offline** (encrypted USB / paper). If it is lost, existing
  licenses keep working but no new ones can be issued -- you would generate
  a new keypair, re-embed the new public key, and re-issue.
- If it **leaks**, anyone can mint CSRN licenses. Rotate: new keypair, new
  embedded public key, ship an update, re-issue customers.

## Issuing a license

```bash
.venv/Scripts/python.exe tools/issue_license.py \
    --key ~/csrn_license_key.hex \
    --org "TruHous Media" \
    --sports football,hockey \
    --expires 2027-08-31 \
    --note "free alpha year 1"
```

Writes a single `license-<org-slug>.json`. Hand it to the customer by any
means (email, USB, ...). They install it with
`POST /api/licensing/install` (the file contents as the JSON body) or by
dropping it at the path you tell them; the "license required" screen clears
on reload once the signature and expiry check out.

- `--expires never` (or omit) → no expiry (`expires_at: 0`).
- `--features` defaults to every feature scope; pass a comma-separated
  subset to restrict.
- `--note` is **owner recordkeeping only** (comped vs. paid, support
  ticket, ...). It is written into the file but is **not signed** and is
  **not read by the app** -- it plays no role in enforcement.

## What happens on expiry

`EntitlementService.status()` compares `expires_at` to now. Past expiry:
`valid: false`, `reason: "EXPIRED"`, the gate re-engages (control screen +
`402` on broadcast APIs). Health, diagnostics, licensing and the OBS
overlay stay reachable. Re-issue with a later `--expires` and reinstall --
no reinstall of the app itself.

A hand-edited license file (e.g. `expires_at` pushed out by hand) is
caught: `status()` re-verifies the on-disk signature (cached by file
mtime), and the edit invalidates it.

## The existing Caledonia install

Caledonia runs from the **source checkout**
(`installed_mode == False`), so it is already granted everything by
`EntitlementService._development_license()` and **never reaches the gate**.
No runtime auto-seed is added -- it would be redundant, and a runtime seed
could not hold the private key to produce a valid signature anyway.

If/when Caledonia moves to a **frozen/installed build**, issue it a
no-expiry license once, the same as any customer:

```bash
.venv/Scripts/python.exe tools/issue_license.py \
    --key ~/csrn_license_key.hex \
    --org "Caledonia Sports Radio Network" \
    --sports football --expires never \
    --note "owner install -- grandfathered"
```

(`--org` should match the Identity Profile `organization.name` so the
badge reads correctly.)

## Round 16 (pywebview shell) note

The gate is **not dev-only** -- it must survive PyInstaller packaging. The
frozen build:

- includes `license_service.py` (pure Python, no extra dependency -- the
  Ed25519 is vendored on purpose so nothing native is added to the bundle);
- **excludes** `tools/issue_license.py` (like `run_core_foundation.py` --
  add it to the `.spec` `excludes`);
- must ship with a **real** `LICENSE_PUBLIC_KEY_HEX` embedded (not the
  placeholder), or every installed launch shows "license required";
- resolves the license file at `ProductPaths.license_file`
  (`%LOCALAPPDATA%\PossumFrog\CSRN Production Suite\Licensing\license.json`),
  which already works under `installed_mode`.
