# Game-Day Recovery Rehearsal

Run this rehearsal before the first live football broadcast and after any meaningful storage or deployment change.

## Preconditions

- CSRN Command Center is stopped.
- OBS is not actively streaming.
- No broadcast is marked live.
- The repository working tree is clean.
- A recent safety snapshot exists and verifies successfully.

## Data restore rehearsal

1. Start Command Center and authenticate.
2. Open the game-day safety snapshot list.
3. Select a recent verified snapshot.
4. Run the recovery rehearsal endpoint before any restore.
5. Confirm the response reports valid JSON and a verified payload.
6. Create a harmless test change in a non-live practice broadcast.
7. Stop Command Center.
8. Run the recovery restore with the exact snapshot identifier as confirmation.
9. Restart Command Center.
10. Confirm the restored schools, rosters, broadcasts, configuration, and state.
11. Confirm the automatic pre-restore snapshot exists and verifies.

A restore must be rejected while a broadcast is live or the game clock is running.

## Unclean shutdown rehearsal

1. Start Command Center through `RUN_CSRN_COMMAND_CENTER.bat`.
2. Confirm `Data/Backups/Recovery/active_session.json` exists.
3. End the Python process without using the normal shutdown path.
4. Start Command Center again.
5. Confirm the recovery status reports the previous unclean session.
6. Review the marker, then clear it from the authenticated recovery controls.
7. Close Command Center normally and confirm the active marker is removed.

## Known-good source rollback rehearsal

1. From a tested release candidate, run:

   `python tools/game_day_recovery.py mark-known-good --note "Rehearsed game-day build"`

2. Verify the rollback plan:

   `python tools/game_day_recovery.py rollback-plan`

3. Do not run the source rollback during an active broadcast.
4. With Command Center stopped and a clean Git working tree, execute the exact confirmation command shown by the plan.
5. Confirm a `pre-release-rollback` data snapshot is created.
6. Restart using the launcher and verify the known-good build.
7. Return to the normal development branch only after the rehearsal is documented.

## Required rehearsal record

Record the date, operator, selected snapshot, known-good commit, result, defects found, and corrective actions. A successful rehearsal does not replace the two complete simulated games required by Phase 6.5.
