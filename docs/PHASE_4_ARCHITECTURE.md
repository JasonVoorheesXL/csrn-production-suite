# Phase 4 Service Architecture

Phase 4 converts `app.py` into a transport and composition layer. Business rules live in Flask-independent services with injected persistence, filesystem, OBS, timing, and migration boundaries.

## Required service contract

Each Phase 4 service:

- lives in a dedicated `*_service.py` module;
- does not import Flask;
- may use framework-neutral utilities such as Werkzeug password hashing;
- receives external dependencies through its constructor or method arguments;
- returns a result object carrying a stable `code`, structured `data`, and an `ok` indicator where applicable;
- is covered by focused service tests and route-contract tests;
- preserves existing HTTP routes and response payloads during extraction.

## Service boundaries

### Core and configuration

- `SecurityService`
- `ConfigurationService`
- `StateService`
- `DiagnosticsService`
- `UpgradeService`

### School and association data

- `SchoolService`
- `RosterService`
- `SponsorService`
- `VenueService`
- `PersonnelService`
- `LogoService`
- `AssetService`
- `AssociationImportService`
- `AssociationSupplementService`
- `AssociationProfileService`
- `AssociationSourceService`
- `AssociationWorkflowService`

### Broadcast construction and operation

- `BroadcastPackageService`
- `BroadcastService`
- `BroadcastLifecycleService`
- `GraphicsService`
- `OBSService`
- `SupportMediaService`

### Live game domain

- `EventService`
- `RulesService`
- `StatisticsService`
- `GameOperationsService`

## Composition-layer responsibilities

`app.py` may:

- define Flask routes and authentication decorators;
- translate HTTP inputs into service calls;
- map service result codes to HTTP status codes;
- assemble injected dependencies;
- serialize service data into responses;
- retain narrow compatibility wrappers required by older clients.

`app.py` should not reimplement image validation, QR generation, network discovery, game rules, statistics, event mutation, broadcast lifecycle, persistence rules, or OBS command policy.

## Guardrails

`phase4_architecture.py` and `tests/test_phase_4_architecture.py` enforce:

- the complete 27-service manifest;
- Flask independence for every service module;
- service imports in the application composition root;
- delegation of the final operational routes;
- absence of extracted support-media implementations from `app.py`;
- the presence of result-contract classes.

Any future service extraction or rename must update the manifest, this document, and the architecture tests in the same change.
