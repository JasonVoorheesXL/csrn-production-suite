# Amory game data loss: investigation

Broadcast `FB-2026-OPEN-W00-001` (Caledonia vs Amory, 2026-09-04). Investigation only; no code changed.

## Bottom line

- **The game was live-tracked.** The record's own command ledger (its last 200 commands) shows plays through 9/4 21:44, with clock, correction, undo, and edit commands, and the state reached revision 592. Play numbers run to 145. The Caledonia-Amory PDF (printed 9/4 21:50 from CSRN's statistics module) reproduces all 145 plays.
- **The play data was destroyed by an archive write.** `final_state_archive` now holds 0 events and 0 plays. An archive write at `end_game` (9/5 18:45) overwrote the archive without checking whether one already existed. Confidence: high for the overwrite, medium for the exact sequence (see below).
- **This is a live, repeatable bug.** The overwrite is unconditional in code, and the trigger (a `final_game` period action followed later by `end_game`) is a normal operator sequence.
- **Full recovery of the stats is possible** from the PDF's Play Register. An exact byte-level restore of the original archive JSON is possible only if an older copy exists elsewhere (see Recovery).

## Timeline

| Local time (CDT) | Event | Source |
|---|---|---|
| 8/30 21:02 | Broadcast record created | `created_at` |
| 9/4 19:07 | Game started (`started_at`) | record |
| 9/4 21:43-21:44 | Last real plays: rev 587 (play 144, 21:43:49), rev 588 (play 145, 21:44:46) | ledger |
| 9/4 21:46:18 | `period:end_quarter`, rev 589 | ledger |
| 9/4 21:46:23 | `period:final_game`, rev 590. Sets status `completed`, updates the record, runs the archive-and-clear path | ledger, `period_service.py`, `game_operations_service.py:277-288` |
| 9/4 21:50 | PDF printed with all 145 plays (proof the data existed) | PDF footer |
| 9/5 18:43:17 | `toggle_halftime`, rev 591, runs against a state with 0 events | ledger |
| 9/5 18:45:11 | `end_game`, rev 592. Archive written with 0 events/plays. `final_state_archived_at` and `completed_at` both set to 18:45 | ledger, record |
| 10/4 11:04 | Record's `updated_at` changed again (writer unidentified; see Open items) | record |

The revision chain has no gaps (ledger `expected_revision` always equals the previous `resulting_revision`).

## What the evidence proves

1. **Play data existed through 9/4 21:44.** Plays 144 and 145 were committed with their play objects in the ledger results.
2. **The archive that exists now is empty** and was written at 18:45 by `end_game`.
3. **`write_broadcast_final_archive` has no guard** against overwriting an existing archive (`app.py:2505-2550`). It writes the snapshot, reads it back, and verifies it against itself. An empty snapshot verifies cleanly.
4. **`final_game` archives and clears when it succeeds.** `period_service` sets `status = completed`; `set_values` then calls `_archive_and_clear_history_if_final`, which clears events and plays only after a verified archive.
5. **Across all completed broadcasts in this data directory, the double-archive sequence appears only for Amory.** Games with `end_game` alone have full archives (117, 120, 174 plays). `FB-2026-5A-W04-001`, which had `final_game` but no `end_game`, kept its 138-play archive. Amory is the only game with both commands in its ledger, and the only one with an empty archive.

## What the evidence does not prove

- **Whether the 21:46 archive was written.** The natural explanation: `final_game` archived all 145 plays and cleared the live state at 21:46, and `end_game` at 18:45 overwrote that archive with the cleared state. The history entries cannot confirm this. `push_history` strips `events`, `plays`, `redo_stack`, and `correction_log` from every snapshot by design, so their emptiness proves nothing. The archive's `final_state_archived_at` was overwritten at 18:45, so the 21:46 timestamp is gone.
- **An inconsistency I could not resolve.** The rev 591 snapshot reports `status: live`, but `final_game` set `completed` at rev 590, and the toggle at 18:43 ran against the state reconstructed from the record. The record's status path between 21:46 and 18:43 is unexplained. This affects the exact sequence, not the conclusion that the second archive destroyed the data.
- **Whether something else emptied the live state before 18:43.** Possible candidates I could not rule out: a `load()` rebuild from record defaults (`broadcast_lifecycle_service.py:82-87`), which would drop events if the mirror snapshot was empty. Either way, the archive overwrite is what made the loss permanent and silent.

## Why the earlier round was wrong

The earlier NO_PLAYER_DATA round read `final_state_archive.history` (two snapshots, both with `broadcast_created: True`, quarter 4, and the final score already set) and concluded the game had never been tracked. Those snapshots were already post-loss, and `history` is stripped of event data by design, so the conclusion did not follow. The ledger, which that round did not read, contradicts it directly.

## Recovery

- **Stats: recoverable now.** The PDF Play Register lists plays 1-145 with quarter, down and distance, offense, play type, result, and yards. The MaxPreps `.txt` files built from it reconcile against the report's team and player totals. Event-level detail such as before/after snapshots and the correction log is not recoverable from the PDF.
- **Exact archive JSON: possibly recoverable from Google Drive version history.** `Data/Broadcasts/` lives in My Drive. Google Drive keeps non-current file versions for about 30 days, so versions from 9/4-9/5 may be expiring about now. **Recommend checking Drive's version history for `Data/Broadcasts/FB-2026-OPEN-W00-001.json` before those versions age out.** I could not verify Drive's retention or whether these versions exist.
- **Local backups do not reach back far enough.** The oldest `Backups/Core/broadcasts` snapshot is from 9/25, by which point the archive was already empty. The runtime diagnostics log retains five rotated files, starting 9/25.

## Is it still live?

Yes. Any game where an operator runs `final_game` (the Command Center "final" action) and later runs `end_game` will overwrite a good archive with an empty one. The verification step passes because it checks the new snapshot against itself. Nothing alerts the operator, and the response reports success.

Suggested severity: **high**. The loss is silent and cannot be detected from the UI. The next game that follows the normal Final-then-End sequence would hit it.

Candidate fixes for a later round, not built here:

1. `write_broadcast_final_archive` should refuse to overwrite an existing archive that has play data when the incoming snapshot has none. It should fail closed and report an error.
2. `_archive_and_clear_history_if_final` should be idempotent: if an archive is already verified for this broadcast, do not archive again.
3. `load()`'s rebuild path should refuse to replace a live state that has play data for the same broadcast.

## Open items

- Something rewrote this record at 10/4 11:04. The `broadcasts.json` backup taken at the same moment suggests a Game Manager or Command Center action on this card. It does not touch the archive, but do not click anything on the Amory card until the Drive check is done.
- Other completed games are not affected by this specific sequence, based on the ledger scan. This scan covered broadcasts in `Data/Broadcasts/` only, not any other store.
