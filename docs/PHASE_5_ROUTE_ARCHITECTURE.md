# Phase 5 Route Architecture

Phase 5 moves Flask route definitions out of `app.py` while preserving the Phase 4 service boundaries and all existing HTTP contracts.

## Route module contract

Each route group should:

- live under the `routes` package;
- expose a Blueprint factory rather than a global application object;
- receive services and application helpers through an immutable dependency object;
- limit itself to HTTP parsing, authentication decoration, status-code mapping, and response serialization;
- avoid importing `app.py` or constructing repositories and services;
- preserve existing URLs, methods, payloads, and authentication behavior.

## Phase 5.1 foundation

`routes/system_routes.py` owns:

- `GET /api/config`
- `POST /api/config`
- `GET /api/diagnostics`
- `GET /api/state`
- `GET /api/readiness`
- `GET /api/build-journal`

`app.py` remains the composition root and registers the Blueprint using injected application boundaries. The public state route remains unauthenticated for the OBS overlay; the remaining routes preserve operator authentication.

## Phase 5.2 security and upgrade routes

`routes/security_upgrade_routes.py` owns:

- `GET /api/security-status`
- `POST /api/setup-pin`
- `POST /api/login`
- `POST /api/logout`
- `GET /api/upgrade/candidate`
- `GET /api/upgrade/status`
- `POST /api/upgrade/migrate`

These routes remain public because they establish or report authentication state and support first-run or pre-login upgrades. Session mutation remains an HTTP-layer responsibility, while PIN validation, lockout behavior, candidate inspection, and migration coordination stay in their Phase 4 services.

## Migration sequence

Later Phase 5 stages should move one coherent route domain at a time, add focused Blueprint tests, retain route-contract coverage, and remove the corresponding `@app` decorators only after the Blueprint passes integrated validation.
