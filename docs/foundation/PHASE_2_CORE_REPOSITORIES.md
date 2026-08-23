# Phase 2 — Core Repositories

Status: repository layer implemented; application integration pending.

## Added

- `JsonObjectRepository`
- `ConfigurationRepository`
- `StateRepository`
- `SecurityRepository`
- regression tests for all three core domains

## Configuration behavior

- Recursively merges stored values into current defaults.
- Preserves user settings while adding newly introduced default keys.
- Supports explicit schema migration hooks.
- Applies package version and build identity from a single runtime identity input.
- Refuses structurally invalid configuration data.
- Relies on the persistence engine to quarantine corrupt files and recover only from validated backups.

## State behavior

- Preserves the full default state shape during load and updates.
- Supports complete replacement and partial recursive updates.
- Validates score, play-number, history, event, correction-log, crew, and broadcast-ID field types.

## Security behavior

- Preserves PIN hashes and secret keys exactly as supplied.
- Validates lockout counters and timestamps.
- Provides focused operations for failed attempts, lockout clearing, and credential replacement.

## Safety boundary

These repositories are not yet wired into `app.py`. The current application still uses its existing core load/save functions until the next integration stage is completed and tested.

## Next stage

Phase 2 integration will instantiate these repositories from the application paths and replace the existing configuration, state, and security persistence functions without changing route behavior.
