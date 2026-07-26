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

## Phase 5.3 school and association routes

`routes/school_routes.py` owns school listing, reading, creation, update, deletion, and duplicate checking under `/api/schools`.

`routes/association_routes.py` owns:

- association profile CRUD;
- generic association preview and approved import workflows;
- multipart and inline source parsing;
- association error-to-status mapping;
- compatibility routes for the MHSAA 5A school, branding, and enrichment manifests.

Manifest loading remains in the application composition root and is injected as callable boundaries. The route module does not know repository paths or create import services. Existing authentication, legacy response shapes, duplicate review behavior, and MHSAA compatibility semantics remain unchanged.

## Phase 5.4 roster, personnel, and venue routes

`routes/personnel_routes.py` owns broadcaster/personnel CRUD, social URL validation, public personnel-headshot serving, and authenticated headshot upload. The headshot storage directory and personnel-ID normalization are injected so the route module does not import the application root.

`routes/roster_routes.py` owns roster CRUD, player CRUD, and player-list import routes under `/api/rosters`.

`routes/venue_routes.py` owns venue listing, filtering, reading, creation, update, and deletion. Duplicate and in-use responses preserve their existing HTTP status mappings.

All mutation and query logic continues to delegate to the Phase 4 services. The Blueprint layer owns only request parsing, upload orchestration, authentication decoration, response serialization, and temporary-file cleanup when a personnel record is missing.

## Phase 5.5 sponsor, asset, and logo routes

`routes/sponsor_routes.py` owns sponsor CRUD, sponsor-to-asset linking, public legacy sponsor-logo serving, and sponsor-logo upload orchestration. Duplicate asset actions (`prompt`, `reuse`, and `replace`) preserve their current file and response behavior.

`routes/asset_routes.py` owns asset CRUD, filtering, public asset-file serving, and uploaded-file attachment. Asset hashing, duplicate detection, reuse, replacement, and metadata persistence continue to delegate to `AssetService`.

`routes/logo_routes.py` owns public school-logo serving, school-logo candidate processing, and logo-record filtering. The application composition root injects the base directory, school-logo directory resolution, and school-ID normalization so no route module imports application globals.

The route layer still owns multipart parsing and filesystem orchestration because those are HTTP-bound concerns. Record validation, image processing, duplicate policy, and domain persistence remain in the Phase 4 services.

## Phase 5.6 broadcast package and lifecycle routes

`routes/broadcast_package_routes.py` owns broadcast-package listing, creation, update, deletion, duplication, and loading. Loaded game state is passed through the injected public-state filter before serialization.

`routes/broadcast_routes.py` owns broadcast record creation, listing, reading, update, status changes, and deletion. Archive filtering and all existing status-code mappings remain unchanged.

`routes/broadcast_lifecycle_routes.py` owns planned-broadcast loading, compatibility initialization, live start, and resume. Lifecycle state construction and OBS coordination remain in `BroadcastLifecycleService`.

The application root continues to construct the package, broadcast, and lifecycle services. The Blueprints receive only callable service boundaries and retain the established authentication and response contracts.

## Phase 5.7 graphics and OBS routes

`routes/obs_routes.py` owns OBS status, connection testing, scorebug-visibility commands, and program visual-mode commands. Boolean validation and blocked-command responses preserve their current HTTP mappings, while OBS configuration, command execution, and status persistence remain in `OBSService`.

`routes/graphics_routes.py` owns lower-third, player, and personnel graphic updates. The application root injects state loading, persistence, public-state filtering, and the shared transaction lock. Graphic construction, exclusivity, duration handling, sponsor application, and record resolution remain in `GraphicsService`.

The compatibility helper used by broadcast-start automation remains in the composition root and continues to delegate to `OBSService`; it is not an HTTP route.

## Migration sequence

Later Phase 5 stages should move one coherent route domain at a time, add focused Blueprint tests, retain route-contract coverage, and remove the corresponding `@app` decorators only after the Blueprint passes integrated validation.
