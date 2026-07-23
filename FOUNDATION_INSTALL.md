# CSRN Production Suite v1.13 Foundation

## Purpose

This release adds hardened JSON persistence without rewriting the existing feature routes. It protects roster, package, state, security, configuration, school, personnel, sponsor, asset, venue, logo, broadcast, and journal writes that use the application's shared `save_json` function.

## Install for testing

1. Back up the entire current CSRN folder.
2. Check out or download the `foundation/persistence-engine` branch.
3. Place the downloaded files in a separate test folder. Do not overwrite the currently working installation for the first test.
4. Copy the current `Data` folder, `state.json`, and `security.json` into the test folder.
5. Start the suite with:

   `START_CSRN_FOUNDATION.bat`

Do not start this test build with `python app.py`; that bypasses the v1.13 runtime integration.

## First-start checks

- Sign in normally.
- Open Game Manager and verify existing broadcasts.
- Open Rosters and verify roster and player counts.
- Add a temporary player, refresh, and confirm the player persists.
- Delete the temporary player and confirm the roster remains.
- Create and delete a temporary roster.
- Confirm files appear under `Data/Backups/Persistence` after writes.
- Confirm `Data/Logs/persistence_audit.log` contains `FOUNDATION_RUNTIME_INSTALLED` and save entries.

## Recovery behavior

When a protected JSON file cannot be decoded:

1. The damaged file is copied to `Data/Backups/Quarantine`.
2. The runtime searches the rotating backups for the newest valid copy.
3. If a valid backup exists, it is loaded.
4. If no valid backup exists, the API returns `DATA_CORRUPTION` instead of replacing the database with an empty default.

## Destructive-write protection

Populated list databases cannot normally be replaced with an empty list or suffer an extreme record-count collapse. Intentional deletion of the final roster uses a specific domain action that first snapshots the existing database.

## Rollback

The foundation branch does not alter the copied production data format. To roll back:

1. Stop CSRN.
2. Return to the previous installation folder or branch.
3. Copy back the pre-test backup only if test data must be discarded.

## Known boundary

This release hardens individual JSON writes. It does not yet provide a true multi-file transaction for the three broadcast representations (`state.json`, broadcast index, and detail file). Each individual write is atomic and backed up, but a machine failure between those writes can still require reconciliation. That transaction coordinator remains the next foundation stage.
