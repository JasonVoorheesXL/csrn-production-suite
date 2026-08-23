# CSRN Production Suite v1.13 Foundation Baseline

Branch: `release/1.13-foundation`
Base: `develop-1.13`

## Immediate findings

- The application remains centered in a large `app.py` module.
- Persistent data paths include state, security, configuration, schools, broadcasters, rosters, assets, sponsors, venues, logos, broadcasts, packages, and the build journal.
- Several save paths still write JSON directly with `Path.write_text(...)` rather than a shared persistence layer.
- `load_config()` replaces unreadable configuration data with defaults and writes those defaults back, which can destroy the only copy of damaged user data.
- Application identity is duplicated across defaults, runtime overrides, and `VERSION.txt`; the inspected baseline contains inconsistent version labels.
- State, broadcast index, and per-broadcast data are not yet coordinated as one transaction.

## Foundation objectives

1. Introduce one atomic JSON persistence implementation.
2. Quarantine corrupt files and recover from verified backups.
3. Block accidental empty or major record-count reductions.
4. Add explicit transaction support for related broadcast files.
5. Move persistence concerns out of route handlers.
6. Add startup diagnostics and automated regression tests.
7. Preserve existing operator-facing behavior during the refactor.

## Delivery order

1. Baseline inventory and test harness.
2. Atomic persistence engine.
3. Store adapters for existing JSON data.
4. Roster migration.
5. Broadcast transaction migration.
6. Remaining data stores.
7. Upgrade-manager hardening.
8. Diagnostics, packaging, and release validation.

## Safety rule

`develop-1.13` remains the known-working branch. All foundation work is isolated on `release/1.13-foundation` until validated and explicitly merged.
