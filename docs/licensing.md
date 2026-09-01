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

This prints the **public** key (64 hex chars). Paste that value -- and only
that value, the public half is safe to commit and to bundle -- into
`license_service.py`:

```python
LICENSE_PUBLIC_KEY_HEX = "fd748ce7...<64 hex chars>..."
```

**As of Round 16 the real owner-supplied key is embedded**
(`fd748ce76657e3339844bdd4046240ee5a22ac34eb0962647c84f66918b9f2fe`).
`verify_license()` verifies every license against *that* key: a license
signed by any other keypair is rejected with `LICENSE_SIGNATURE_INVALID`
(not merely "signature present"). The all-zero string is still recognised
as the "not configured" placeholder and fails closed
(`LICENSE_PUBLIC_KEY_NOT_CONFIGURED`) if it is ever re-embedded.

To rotate the key (private key lost / compromised): `--genkey` a new pair,
replace `LICENSE_PUBLIC_KEY_HEX`, ship an app update, re-issue customers.

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

## Round 16 -- pywebview shell + license, merged

`round16-pywebview-license-handoff-20260831` merged the pywebview shell
(`round15-pywebview-shell-20260831`, commits 15A-15G) with the license
foundation (`round15-license-foundation-20260831`). The only file both
branches touched was `app.py`, in disjoint regions -- clean merge.

**How the two coexist.** `_install_license_gate(app)` runs at `app.py`
import scope (right after `_install_internal_tools_gate(app)`), so it is
installed no matter which entry point loads `app`:

- `python app.py` -> `__main__` -> `run_command_center()` (dev / `.bat`);
- `csrn_desktop.py --serve-only` -> `run_server_only()` -> `import app` ->
  `app.run_command_center()` (frozen build's re-exec, Round 15D);
- the pywebview shell's child process, same path as above.

In every case `serve(app, ...)` serves the already-gated app. A frozen
build resolves `ProductPaths.installed_mode = True` (`sys.frozen`), so
`_installed_build()` is True and the gate enforces: no valid license ->
`GET /` shows `templates/license_required.html`, broadcast APIs `402`,
while health / licensing / diagnostics / static / overlay stay reachable.
(`tests/test_license_frozen_gate.py`.)

**Packaging (`.spec`, Round 16 Task B).**

- `license_service.py` + `entitlement_service.py` are pinned as
  `hiddenimports` (license_service is a function-local import inside
  `app.get_entitlement_service()`).
- `tools.issue_license` / `issue_license` are in `excludes` -- the
  owner-only signer never ships. Nothing in the app import graph reaches
  it; `test_license_frozen_gate.py` asserts no signer / private-key token
  (`sign_license(`, `ed25519_sign(`, `CSRN_LICENSE_PRIVATE_KEY`,
  `--genkey`, `secret_expand`) appears in any shipped module. The app is
  verify-only and never holds a private key.
- The **real public key is embedded** (see "one-time setup" above), so an
  installed launch does not sit on the "license required" screen once a
  valid license is present.
- License file lives at `ProductPaths.license_file`
  (`%LOCALAPPDATA%\PossumFrog\CSRN Production Suite\Licensing\license.json`).

**Still deferred (unchanged):**

- **15E** first-run onboarding wizard -- its own future round.
- Windows-box **build verification** of the `.spec` / `.iss` -- PyInstaller
  is not installed in the dev environment; a real onedir build must
  confirm the ctranslate2 / onnxruntime imports and that
  `/api/diagnostics` 404s / `/api/health` 200s from the frozen exe.
- **Code signing** -- no Authenticode cert this round; unsigned artefacts
  must not be presented as signed releases.

**Owner's remaining one-time check:** issue a license with the real
private key on your own machine
(`tools/issue_license.py --key <your key> --org "..." --sports football
--expires never`) and confirm it validates against the embedded
`LICENSE_PUBLIC_KEY_HEX` -- the one link the test suite can't close here
because it (correctly) has no private key.
