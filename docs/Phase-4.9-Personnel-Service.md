# Phase 4.9 — Personnel Service

Phase 4.9 extracts personnel-domain behavior from Flask into a testable service boundary.

## Scope

- Personnel list, create, update, and delete behavior
- Stable personnel IDs and collision handling
- Legacy broadcaster-record normalization
- Role, category, status, pronunciation, and producer metadata
- Social-profile normalization and validation
- Personnel headshot path normalization and linking
- Existing `/api/broadcasters`, `/api/personnel/<id>/headshot`, and `/api/validate-social` contracts

## Boundary

`PersonnelService` is independent of Flask and physical file storage. The application injects personnel loading and saving functions. Multipart upload handling and file delivery remain in Flask; the service decides whether and how a saved headshot is linked to a personnel record.

## Compatibility

The existing broadcaster JSON file and API routes remain supported. Legacy `name`/`primary_role` records are normalized to the current personnel schema without requiring a separate destructive conversion.
