# Phase 5 Route Architecture

Phase 5 moves Flask route definitions out of `app.py` while preserving the Phase 4 service boundaries and all existing HTTP contracts.

## Route module contract

Each route group:

- lives under the `routes` package;
- exposes a Blueprint factory rather than a global application object;
- receives services and application helpers through an immutable dependency object;
- limits itself to HTTP parsing, authentication decoration, status-code mapping, and response serialization;
- avoids importing `app.py` or constructing repositories and services;
- preserves existing URLs, methods, payloads, and authentication behavior.

## Completed route ownership

### Phase 5.1 — System routes

`routes/system_routes.py` owns configuration, diagnostics, public state, readiness, and build-journal endpoints.

### Phase 5.2 — Security and upgrade routes

`routes/security_upgrade_routes.py` owns authentication state, PIN setup/login/logout, upgrade inspection, status, and migration endpoints.

### Phase 5.3 — School and association routes

`routes/school_routes.py` owns school CRUD and duplicate checking. `routes/association_routes.py` owns association profile, source, preview, approved-import, MHSAA compatibility, branding, and enrichment workflows.

### Phase 5.4 — Roster, personnel, and venue routes

`routes/personnel_routes.py`, `routes/roster_routes.py`, and `routes/venue_routes.py` own their respective CRUD, import, validation, filtering, and upload endpoints.

### Phase 5.5 — Sponsor, asset, and logo routes

`routes/sponsor_routes.py`, `routes/asset_routes.py`, and `routes/logo_routes.py` own their domain CRUD, upload, duplicate-policy, linking, filtering, and public file-serving endpoints.

### Phase 5.6 — Broadcast package and lifecycle routes

`routes/broadcast_package_routes.py`, `routes/broadcast_routes.py`, and `routes/broadcast_lifecycle_routes.py` own broadcast-package CRUD/load, broadcast record CRUD/status, and planned/live lifecycle endpoints.

### Phase 5.7 — Graphics and OBS routes

`routes/obs_routes.py` owns OBS status, connection testing, scorebug-visibility commands, and program visual-mode commands. `routes/graphics_routes.py` owns lower-third, player, and personnel graphic updates.

### Phase 5.8 — Live game routes

`routes/live_game_routes.py` owns score and state changes, statistics, control-source selection, events and corrections, undo, scorebug and halftime controls, game completion and reset, clock control, field direction, and rules-driven play entry.

### Phase 5.9 — Support and page routes

`routes/page_routes.py` owns the public command-center and OBS overlay pages. `routes/support_routes.py` owns roster-headshot serving and upload, connection information, and QR generation.

## Phase 5.10 — Application factory and consolidation

`application_factory.py` constructs and configures Flask instances, registers the complete Blueprint collection, rejects duplicate Blueprint names and duplicate rule/method combinations, and publishes a serializable route manifest.

`app.py` remains the composition root for repositories, services, dependency objects, and production startup. It now collects Blueprints rather than registering them throughout the module. `create_app()` performs the single application-construction step, while the module-level `app` remains available for Waitress, existing tests, and compatibility imports.

The authentication decorator marks protected view functions with route metadata. The final architecture audit verifies:

- all 18 expected Blueprints are registered;
- no direct `@app` route decorators remain;
- no non-static endpoint bypasses Blueprint ownership;
- no duplicate rule/method registrations exist;
- the declared public endpoint set matches the actual route manifest;
- multiple factory-created applications expose equivalent route contracts.

## End state

Phase 5 is complete when the factory-backed application passes the permanent architecture audit and the complete repository validation suite on Windows and Ubuntu. Future feature work should add routes through injected Blueprint factories and preserve the route-manifest and authentication-policy checks.
