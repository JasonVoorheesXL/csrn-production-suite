# Phase 6.7 — Installer, Updates, and Licensing Foundation

Phase 6.7 establishes the commercial delivery boundary without weakening the game-day application or pretending that a client-only license secret is secure.

## Stable customer data

Source checkouts retain the existing repository-local layout. Installed or frozen builds use a stable per-user runtime root:

```text
%LOCALAPPDATA%\PossumFrog\CSRN Production Suite
```

The runtime root contains customer data, state, security material, logs, exports, update plans, licensing state, and support bundles. The installer binary directory is replaceable and may be removed without deleting customer data.

Advanced deployments may set:

- `CSRN_RUNTIME_ROOT`
- `CSRN_DATA_ROOT`
- `CSRN_INSTALLED=1`

Legacy colocated data is copied only after the exact confirmation phrase:

```text
MIGRATE LEGACY CSRN DATA
```

Existing destination files are never overwritten by that migration.

## Windows packaging

The repository includes:

- `packaging/windows/CSRNProductionSuite.spec` for a PyInstaller onedir build;
- `packaging/windows/csrn-production-suite.iss` for a per-user Inno Setup installer;
- `tools/build_release_package.py` for a deterministic ZIP package and SHA-256 file manifest.

The installer definition preserves the external runtime root during uninstall. Code-signing configuration is intentionally external to the repository. Unsigned test builds must not be represented as signed production releases.

## Update safety

Every update package contains `release.json` with:

- product identifier;
- semantic version;
- build identifier;
- file size and SHA-256 for every payload file.

The application validates product identity, version ordering, safe relative paths, file sizes, and file hashes. Downgrades are blocked by default.

Preparing an update requires:

```text
PREPARE CSRN UPDATE
```

Preparation creates a pre-update safety snapshot and writes a pending update plan. The running Flask process never replaces its own binaries. A stopped, external updater is required for the actual replacement.

## Licensing and entitlements

The product identifier is:

```text
possumfrog.csrn-production-suite
```

Source checkouts receive a development-only entitlement so development and Caledonia testing remain functional. Installed builds begin unlicensed.

The entitlement record supports feature and sport scopes, including:

- core broadcast;
- captions;
- weather;
- graphics and statistics;
- graphics themes;
- social publishing;
- grounded game recaps.

A production license payload is accepted only through a configured provider verifier. No shared signing secret is embedded in the client. Phase 6.7 does not implement a payment processor or hosted activation server; it creates the secure provider boundary those systems must use.

Removing an installed license requires:

```text
REMOVE CSRN LICENSE
```

## Support bundles

Customer-safe support bundles include deployment status and a bounded set of diagnostic JSON and log files. Passwords, PIN hashes, secret keys, API keys, tokens, signatures, and client secrets are redacted. Security files, player headshots, sponsor media, recordings, and full customer archives are excluded by default.

Create a deployment report:

```cmd
python tools\deployment_report.py
```

Create a support bundle:

```cmd
python tools\deployment_report.py --support-bundle --note "Describe the problem"
```

## Authenticated API

- `GET /api/deployment/status`
- `POST /api/deployment/update/validate`
- `POST /api/deployment/update/prepare`
- `POST /api/deployment/support-bundle`
- `GET /api/licensing/status`
- `GET /api/licensing/activation-request`
- `POST /api/licensing/install`
- `POST /api/licensing/remove`

## Following stages

Phase 6.8 builds the original multi-theme graphics engine. Phase 6.9 remains the Social Publishing Engine for Facebook and X event posts, sponsor-enabled social cards, player headshots, retries, corrections, and audit history.
