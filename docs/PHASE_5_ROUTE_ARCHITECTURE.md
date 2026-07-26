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

`routes/system_routes.py` owns configuration, diagnostics, public state, readiness, and build-journal endpoints.

## Phase 5.2 security and upgrade routes

`routes/security_upgrade_routes.py` owns authentication state, PIN setup/login/logout, upgrade inspection, status, and migration endpoints.

## Phase 5.3 school and association routes

`routes/school_routes.py` owns school CRUD and duplicate checking. `routes/association_routes.py` owns association profile, source, preview, approved-import, MHSAA compatibility, branding, and enrichment workflows.

## Phase 5.4 roster, personnel, and venue routes

`routes/personnel_routes.py`, `routes/roster_routes.py`, and `routes/venue_routes.py` own their respective CRUD, import, validation, filtering, and upload endpoints.

## Phase 5.5 sponsor, asset, and logo routes

`routes/sponsor_routes.py`, `routes/asset_routes.py`, and `routes/logo_routes.py` own their domain CRUD, upload, duplicate-policy, linking, filtering, and public file-serving endpoints.

## Phase 5.6 broadcast package and lifecycle routes

`routes/broadcast_package_routes.py`, `routes/broadcast_routes.py`, and `routes/broadcast_lifecycle_routes.py` own broadcast-package CRUD/load, broadcast record CRUD/status, and planned/live lifecycle endpoints.

## Phase 5.7 graphics and OBS routes

`routes/obs_routes.py` owns OBS status, connection testing, scorebug-visibility commands, and program visual-mode commands. `routes/graphics_routes.py` owns lower-third, player, and personnel graphic updates.

## Phase 5.8 live game routes

`routes/live_game_routes.py` owns the operational game endpoints for:

- score and general state changes;
- statistics reporting;
- control-source selection;
- event creation, correction, editing, reporting, and undo;
- scorebug, halftime, game completion, reset, and new-broadcast controls;
- clock control, field direction, and rules-driven play entry.

The Blueprint receives the existing game-operations, event, rules, and statistics services through injected getters. It owns only request parsing, authentication, status-code mapping, and response serialization. State mutation, football rules, scoring authority, event persistence, statistics calculation, OBS coordination, and transaction locking remain in the Phase 4 services.

## Phase 5.9 support and page routes

`routes/page_routes.py` owns the public command-center and OBS overlay pages. Application identity remains an injected composition-root boundary.

`routes/support_routes.py` owns public roster-headshot serving, authenticated player-headshot upload, connection information, and QR generation. Player lookup, image processing, storage, network-address discovery, and QR construction remain in `SupportMediaService`.

After Phase 5.9, `app.py` contains no direct Flask route decorators. It remains the application composition and startup module until Phase 5.10 introduces the final application-factory and route-registration consolidation.

## Migration sequence

Later Phase 5 stages should move one coherent route domain at a time, add focused Blueprint tests, retain route-contract coverage, and remove the corresponding `@app` decorators only after the Blueprint passes integrated validation.
