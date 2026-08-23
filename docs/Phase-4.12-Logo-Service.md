# Phase 4.12 — Logo Service

## Purpose

Move school-logo processing and logo-catalog behavior out of Flask while preserving the existing school-logo upload and `/api/logos` contracts.

## Scope

`LogoService` owns:

- supported source-image extension handling;
- image decoding and validation;
- round master and scorebug derivative generation;
- school-color extraction;
- candidate logo metadata;
- school branding updates;
- logo-catalog insertion and replacement;
- logo listing, filtering, and lookup;
- storage failure isolation before database persistence.

Flask remains responsible for:

- authentication;
- multipart upload handling;
- choosing the on-disk logo directory;
- writing the original, master, and scorebug files;
- HTTP response codes and JSON serialization.

## Compatibility

The existing endpoints remain:

- `POST /api/schools/<school_id>/logo/process`
- `GET /api/logos`
- `GET /school-logos/<school_id>/<filename>`

The logo list still returns a JSON array. Optional `school_id`, `designation`, and `approval_status` filters are additive.

## Runtime identity

Phase completion updates the application to:

- Version: `1.13.0-alpha.4l`
- Build: `V1.13A4L-LOGO-SERVICE`
