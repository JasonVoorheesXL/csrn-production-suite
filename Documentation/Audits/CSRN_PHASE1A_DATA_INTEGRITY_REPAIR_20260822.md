# CSRN Phase 1A Data Integrity Repair - 2026-08-22

## Status

Phase 1A implementation has been applied, but Phase 1A is not declared fully approvable until the project pytest environment can run the targeted regression suite. The project `.venv` Python is currently blocked by Windows with `Access is denied`; bundled Codex Python can compile the files and run service-level smoke checks, but it does not include Flask or pytest.

## Pre-Change Baseline

- Branch: `gate6/final-visual-matrix`
- HEAD: `20311ed0ca201125560d91ca3c69e142b08e91c2`
- Working tree: dirty before repair. Many tracked and untracked files were already modified. `git status --short` warned that `.pytest_cache/` could not be opened.

## Rollback Location

Existing files touched by this repair were backed up before editing:

`C:\Users\Darth\My Drive\CSRN\Development\CSRN-Production-Suite\_phase1a_data_integrity_rollback_20260822-093354`

New files added by Phase 1A can be removed directly during rollback.

## Files Modified Or Added

- `live_command_service.py` added.
- `state_service.py` modified.
- `game_operations_service.py` modified.
- `event_service.py` modified.
- `rules_service.py` modified.
- `app.py` modified.
- `state_read_cache.py` modified.
- `runtime_state_cache.py` modified.
- `tests/test_phase1a_data_integrity.py` added.
- `tests/test_game_operations_service.py` modified for the intended single-save score commit.
- `Documentation/Audits/CSRN_PHASE1A_DATA_INTEGRITY_REPAIR_20260822.md` added.

## Command Schema

Mutation requests may now carry:

- `command_id`
- `client_id`
- `issued_at`
- `expected_revision`
- action payload fields already used by the existing routes

Responses for repaired command paths include command metadata:

- `command_id`
- `command_status`
- `client_id`
- `issued_at`
- `expected_revision`
- `action`
- `state_revision`
- `committed_at`

Legacy clients that omit `command_id` still work and receive `legacy_committed`. Those legacy requests are not retry-safe across lost HTTP responses because the server has no stable logical command identity to recognize.

## Idempotency Strategy

The repaired paths are:

- `/api/score`
- `/api/event-trigger`
- `/api/rules-play`

Each path checks `recent_commands[command_id]` under the existing mutation lock after loading active state and before running mutation logic. If a matching command exists for the same `broadcast_id`, the service returns the original stored result and does not rerun scoring, event, or play mutation code.

## Atomicity Strategy

The command ledger is persisted inside the authoritative active game state under `recent_commands`. For committed commands, the state mutation, new `state_revision`, and command result record are written in the same state save. This avoids the unsafe pattern where a touchdown can save but a separate idempotency file fails before retry.

## State Revision Design

`state_revision` is a true integer revision:

- normalized to `0` for old states without the field
- assigned before Phase 1A command saves
- persisted with authoritative state
- exposed through full public state
- exposed through runtime state
- used as the runtime `revision` when present

`StateService.save()` also ensures a save cannot persist a revision less than or equal to the stored raw revision; it advances to `stored_revision + 1` when a caller did not pre-assign a newer revision.

## Expected Revision Policy

Phase 1A does not blindly reject stale `expected_revision`. For `/api/score`, `/api/event-trigger`, and `/api/rules-play`, commands serialize under the server mutation lock and return the actual resulting `state_revision`. Dangerous absolute-state semantics such as undo, authority takeover, and broader stale-client rejection are deferred to Phase 1B because they require operator UX and reconciliation states.

## Direct Score Correction Strategy

Direct score adjustments now append an auditable `direct_score_adjustment` entry to `correction_log` with:

- team
- delta
- old score
- new score
- source
- reason/note
- command ID
- client ID
- state revision
- timestamp

This does not attempt full event/stat reconciliation in Phase 1A. It makes direct corrections auditable without adding a new live UI modal.

## Cache Invalidation Strategy

`state_read_cache.py` and `runtime_state_cache.py` now expose invalidation functions. `app.save_state()` calls both invalidators after a successful state save. This prevents the 250 ms caches from continuing to serve a pre-mutation response as current immediately after a committed mutation.

## Backward Compatibility

Older state JSON without `state_revision` or `recent_commands` loads safely. `StateService.normalize()` supplies:

- `state_revision: 0`
- `recent_commands: {}`

The internal command ledger is removed from public and runtime state responses.

## Command Ledger Retention

The command ledger is bounded to 200 recent commands per active state. When the ledger exceeds the limit, the oldest records by `committed_at` are pruned. Command records are scoped by current `broadcast_id`, so a command ID from a previous broadcast does not replay against another broadcast.

## Automated Tests Added

Added `tests/test_phase1a_data_integrity.py` covering:

- score command idempotency
- touchdown command idempotency
- detailed play command idempotency
- duplicate response revision replay
- duplicate commands not advancing revision
- duplicate touchdown not appending a second event
- duplicate detailed play not appending a second play
- lost-response retry with same command ID
- revision increments for score, event, and rules play
- runtime/full state revision exposure
- rejected command does not increment revision
- distinct command IDs commit as distinct commands
- legacy state loads safely
- ledger bounding
- direct score audit records
- cache invalidation behavior
- concurrent same-command suppression
- concurrent distinct-command ordering

Updated `tests/test_game_operations_service.py` to expect one atomic score save instead of the old two-save planned-to-live path.

## Test Results

`py_compile` result:

- Passed for `live_command_service.py`, `state_service.py`, `game_operations_service.py`, `event_service.py`, `rules_service.py`, `runtime_state_cache.py`, `state_read_cache.py`, `app.py`, `tests/test_phase1a_data_integrity.py`, and `tests/test_game_operations_service.py`.

Pytest result:

- Passed: not available
- Failed: not available
- Skipped: not available
- Blocker: `.venv\Scripts\python.exe` and `.venv\Scripts\pytest.exe` both fail with `Access is denied`. Bundled Codex Python does not include `pytest` or `flask`, so it cannot run the Flask route/cache test module.

Service-level smoke checks run with bundled Python:

- Passed: duplicate direct score mutates once and returns revision `501`.
- Passed: direct score adjustment creates an audit record with command ID and revision.
- Passed: lost-response touchdown retry with command `ABC` returns original revision `501` without a second event.
- Passed: after the isolated fixture clears the pending-try phase, distinct touchdown command `DEF` commits as revision `502`.
- Passed: duplicate detailed play appends one play.
- Passed: distinct score command IDs serialize to ordered revisions.
- Passed: concurrent same-command direct score requests produce one mutation.
- Passed: legacy state normalizes revision and public/runtime state expose `state_revision`.

## Remaining Limitations

- Phase 1B frontend pending/unknown/stale UX is not implemented.
- Phase 2 media isolation, Waitress separation, polling rationalization, and persistence redesign are not implemented.
- Legacy clients without `command_id` are still not retry-safe if an HTTP response is lost.
- Direct score correction is auditable, but not fully reconciled into event/stat derivation.
- The command ledger is in the active state file and is protected by the current in-process mutation lock. A future multi-process deployment still needs a shared transactional store.
- Phase 1A should not be approved for game-night use until pytest can run in the intended project environment.

## Phase 1A Acceptance Assessment

Implemented in code:

1. Repeating the same touchdown `command_id` cannot score twice on the repaired path.
2. Repeating the same direct score `command_id` cannot alter score twice.
3. Repeating the same detailed play `command_id` cannot append two plays.
4. Lost-response retries with the same command ID are safe.
5. Committed repaired live mutations receive a newer integer `state_revision`.
6. Duplicate command replay returns the original result/revision.
7. Older state formats load without manual migration.
8. Direct score correction leaves an auditable record.
9. Runtime/full-state reads expose `state_revision`.
10. State read caches are invalidated after save.

Not fully accepted yet:

11. Full targeted pytest suite could not be executed because the project Python environment is OS-blocked.
12. Existing broader automated tests were not run for the same reason.

## Recommendation

Do not proceed to Phase 1B or Phase 2 yet. First run the targeted pytest suite in an environment where the project `.venv` is executable, or repair the local venv access issue without changing package versions. If those tests pass, Phase 1A can be considered ready for review.

---

## Phase 1A Validation Gate

Validation mode constraints were followed: no Phase 1B frontend repair, no Phase 2 media/polling/persistence work, no OBS changes, no package upgrades, no package version changes, no Git reset/clean/commit/push, and no production game data edits.

### 1. Root Cause Of `.venv` Access Denied

Read-only findings:

- `.venv\Scripts\python.exe` exists, length `255200`, normal `Archive` attributes, not a reparse point, no `Zone.Identifier` stream found.
- `.venv\Scripts\pytest.exe` exists, length `108404`, normal `Archive` attributes.
- ACL for `.venv\Scripts\python.exe` includes the owner and `CodexSandboxUsers` with modify rights.
- `.venv\pyvenv.cfg` points to `C:\Users\Darth\AppData\Local\Python\pythoncore-3.13-64\python.exe` with version `3.13.14`.
- Executing that base interpreter directly returns Windows `Access is denied`.
- Inspecting ACLs, streams, signature, directory listing, reparse data, and copying from `C:\Users\Darth\AppData\Local\Python\pythoncore-3.13-64` also returns `Access is denied`, even after read permission was granted in Codex.
- The stale venv points to `pythoncore-3.14-64` and fails similarly.

Narrowest supported diagnosis: the project venv launcher is failing because the base Python installation under `AppData\Local\Python\pythoncore-3.13-64` is blocked by OS-level ACL/security policy or equivalent local protection. The project `.venv\Scripts\python.exe` itself does not look like a Google Drive placeholder, MOTW-blocked file, or missing file.

### 2. Test Environment Actually Used

The production `.venv` was not modified.

Validation used:

- Executable: bundled Codex Python `3.12.13` at `C:\Users\Darth\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe`.
- Package path: bundled Python site-packages first, then the project `.venv\Lib\site-packages`.
- Pytest: `9.1.1` from the existing project `.venv`.
- Flask: `3.0.3` from the existing project `.venv`.
- Pillow: bundled compatible `12.3.0`, because the project venv Pillow is compiled for Python 3.13 and cannot load under the 3.12 workaround.

Known environment differences:

- Python executable is `3.12.13`, not the project venv's configured `3.13.14`.
- Compiled packages from the 3.13 venv are not universally importable under the 3.12 workaround. Full app import cache tests still fail on `greenlet._greenlet` through Playwright.

### 3. Exact Test Totals

Phase 1A targeted suite:

- Command: `tests/test_phase1a_data_integrity.py -q`
- Result: `25 passed in 55.60s`

Focused direct-score/cache subset:

- Command: `test_direct_score_adjustment_is_auditable`, `test_score_route_duplicate_command_returns_original_result`, `test_cache_does_not_return_pre_mutation_revision_after_commit`
- Result: `3 passed in 0.64s`

Related existing suites:

- Command: `tests/test_game_operations_service.py tests/test_state_service.py tests/test_event_service.py tests/test_rules_service.py tests/test_live_game_routes_blueprint.py tests/test_gate185_r1_runtime_state_cache.py tests/test_gate184_r117_state_response_cache.py -q`
- Result: `104 passed, 9 failed in 4.63s`

Compilation:

- `py_compile` passed for touched Python files and Phase 1A tests.

### 4. Failing Tests And Cause

Related-suite failures:

- `tests/test_game_operations_service.py::test_toggle_halftime_resumes_third_quarter_at_first_and_ten`
  - Cause classification: existing behavior/test mismatch outside Phase 1A idempotency. Phase 1A did not change `toggle_halftime` logic.
- `tests/test_event_service.py` conversion tests for XP/2PT outcomes.
  - Cause classification: existing behavior/test mismatch around pending-try enforcement. Phase 1A did not introduce the pending-try requirement; validation observed it while running related tests.
- `tests/test_gate185_r1_runtime_state_cache.py` and `tests/test_gate184_r117_state_response_cache.py`
  - Cause classification: environment problem in workaround runtime. Full app import reaches Playwright/greenlet, and project venv `greenlet` is compiled for Python 3.13, so bundled Python 3.12 cannot import `greenlet._greenlet`.

### 5. HTTP Idempotency Results

Added and passed route-layer tests using the real Flask `live_game_routes` blueprint and real Phase 1A services against isolated in-memory state:

- `POST /api/score` duplicate `command_id` returns original revision and mutates once.
- `POST /api/event-trigger` duplicate touchdown `command_id` returns original revision and appends one event/play.
- `POST /api/rules-play` duplicate `command_id` returns original revision and appends one event/play.
- Concurrent `POST /api/score` requests with the same `command_id` return revision `501` and mutate once.

### 6. `state_revision` Semantic Findings

Validated behavior:

- Repaired command paths increment `state_revision` once for committed score/event/rules-play mutations.
- Duplicate command replay does not advance `state_revision`.
- Rejected commands do not advance `state_revision`.
- Runtime/full state expose `state_revision`.

Approval blocker found:

- `StateService.save()` currently advances `state_revision` on an identical rewrite. A state with revision `10` saved unchanged becomes revision `11`.
- A metadata-only save then advances to revision `12`.

This violates the preferred Phase 1B semantic if `state_revision` is meant to represent only committed authoritative active-state changes. It is acceptable for every real active-state mutation to advance, but not for identical rewrites or secondary/archive-style writes to advance merely because `save()` was called.

Per validation instructions, this was not silently patched during this validation pass. Phase 1A should not be approved until `state_revision` semantics are tightened or explicitly redefined.

### 7. Frontend Routes And Actions Still Omitting `command_id`

Search found no `command_id` usage in `templates` or `static`. Current browser/operator paths still omitting command IDs include:

- `setControlSource()` -> `/api/control-source`
- `setStateFrom()` -> `/api/set`
- `recordFirstDown()` -> `/api/event-trigger`
- `submitPenalty()` -> `/api/event-trigger`
- `commitFieldSpot()` -> `/api/game-correction`
- `setFieldDrive()` -> `/api/field-direction`
- `submitPlayEntry()` -> `/api/rules-play`
- `setDriveDirection()` -> `/api/field-direction`
- `clockAction()` / `adjustClock()` / `setClockDialog()` / `toggleClockVisibility()` -> `/api/clock-control`
- `quickKickoff()` -> `/api/event-trigger`
- `score()` -> `/api/score`
- `confirmAutomationEvent()` -> `/api/event-trigger`
- `quickEvent()` -> `/api/event-trigger`
- `setState()` -> `/api/set`
- `submitQuickCorrection()` -> `/api/game-correction`
- `submitEjection()` -> `/api/event-trigger`
- `undo()` -> `/api/undo`
- `restoreLastUndone()` -> `/api/restore`

These were not fixed because command ID generation/pending UI belongs to Phase 1B. Legacy no-command requests still function but are not retry-idempotent.

### 8. Direct Score Audit Integrity

Validated:

- One direct score command creates one `direct_score_adjustment` correction record.
- Duplicate same `command_id` does not create a second correction record.
- Correction record contains old score, new score, delta, command ID, client ID, revision, and timestamp.
- Direct score adjustment does not append event/play rows in the repaired test path.

Undo/restore event behavior was not changed by Phase 1A, and direct score reconciliation remains an audit trail rather than full event/stat reconstruction.

### 9. Cache Invalidation Results

Validated through the isolated real Flask system blueprint/cache wrappers:

- `/api/runtime-state` cache populated at revision `1`.
- After invalidation and state mutation to revision `2`, immediate `/api/runtime-state` returns revision `2`.
- Same result for `/api/state`.

Full app cache tests could not complete in the workaround runtime because app import fails on Python-version-mismatched compiled `greenlet`.

### 10. Code Changed During Validation And Why

Validation found a real Phase 1A scalability defect: command ledger records and history snapshots could recursively copy `recent_commands`, `history`, and growing archive fields. The bounded-ledger test hung before this was corrected.

Tightly scoped validation fixes applied:

- `live_command_service.command_result_state()` now strips internal/archive fields from command result state projections before storing replay results.
- `StateService.push_history()` excludes `recent_commands` from undo/history snapshots.
- Repaired score/event/rules-play paths temporarily shield injected history callbacks from `recent_commands` and defensively cap history to 50 entries after the callback.
- Route-level Phase 1A validation tests were added to `tests/test_phase1a_data_integrity.py`.

No Phase 1B or Phase 2 behavior was implemented.

### 11. Approval Recommendation

Phase 1A is not yet safe to approve.

Reasons:

1. The targeted Phase 1A suite passes, including HTTP route idempotency, duplicate replay, direct score audit, concurrent same-command handling, and cache invalidation in an isolated Flask path.
2. However, `state_revision` semantics are not yet precise enough for Phase 1B stale-client rejection because identical and metadata-only `StateService.save()` calls advance the revision.
3. Full app cache tests remain blocked until the real project Python 3.13 environment is executable or a compatible temporary test environment can be built without changing dependency versions.

Recommended next validation/repair step: fix or explicitly define `StateService.save()` revision semantics so only authoritative active-state mutations advance `state_revision`, then rerun the Phase 1A and related suites. Do not begin Phase 1B until that is resolved.

## Phase 1A.1 Revision Semantics Repair

Date: 2026-08-22

### 1. Prompt Validation

The Phase 1A.1 prompt was valid and worth executing. It correctly identified the remaining architectural defect: generic persistence was conflating "a save happened" with "an authoritative live-state mutation committed." That would have made Phase 1B stale-client rejection unreliable because identical rewrites, metadata-only writes, and secondary snapshot activity could falsely advance `state_revision`.

No Phase 1B or Phase 2 work was started.

### 2. Root Cause

Before this repair, `StateService.save()` normalized the incoming state, read the stored state revision, and advanced to `stored_revision + 1` whenever the incoming revision was less than or equal to the stored revision.

Incorrect result:

- Revision `10` saved unchanged became `11`.
- A metadata-only save after that became `12`.
- Repaired command handlers that already assigned one explicit revision risked hidden extra revision movement at the generic persistence layer.

### 3. Adopted Revision Rule

`state_revision` is now treated as a committed active-state ordering number, not a save counter.

Current persistence semantics:

- Explicit mutation boundaries assign the next revision.
- Generic `StateService.save()` preserves the supplied revision.
- Identical saves do not advance revision.
- Metadata/internal saves do not advance revision unless the caller has already assigned a new revision.
- If an incoming state has a lower revision than the stored state, `StateService.save()` preserves the stored revision to prevent numeric regression.
- If an incoming state carries a higher explicit revision, `StateService.save()` preserves that explicit revision.

This is intentionally conservative. Generic save still cannot prove whether a stale writer is authoritative or non-authoritative because no caller intent flag exists yet. Phase 1B stale rejection should therefore be implemented at explicit mutation/API boundaries, not by reintroducing automatic generic-save increments.

### 4. Code Change

Changed:

- `state_service.py`
  - Removed automatic revision bump on equal revision.
  - Preserves stored revision only when the incoming revision is lower.

No frontend commands, OBS behavior, Waitress configuration, package versions, or production game data were changed.

### 5. Caller Matrix

| Caller / path | Authoritative active mutation? | Desired revision behavior | Phase 1A.1 status |
| --- | --- | --- | --- |
| `/api/score` repaired command path | Yes | Advance once per distinct accepted command | Implemented and validated |
| `/api/event-trigger` repaired command path | Yes | Advance once per distinct accepted command | Implemented and validated |
| `/api/rules-play` repaired command path | Yes | Advance once per distinct accepted command | Implemented and validated |
| Duplicate `command_id` replay | No new mutation | Return original result and revision | Implemented and validated |
| Rejected command | No | No revision advance | Implemented and validated |
| Command ledger write | Internal to same commit | Share command revision, no second advance | Implemented and validated |
| History write | Internal to same commit | Share command revision, no second advance | Implemented and validated |
| Direct score correction log | Internal audit of same commit | Share command revision | Implemented and validated |
| Linked broadcast snapshot | Secondary persistence | Preserve source revision | Implemented and validated |
| Identical `StateService.save()` | No | Preserve revision | Implemented and validated |
| Metadata-only generic save | No active-state commit | Preserve revision | Implemented and validated |
| `/api/set`, game correction, clock, field direction, control source, undo/restore, halftime/end/reset/new-game | Yes when used for live game control | Should eventually advance once at explicit mutation boundary | Not broadened in Phase 1A.1; needs Phase 1B or a follow-up explicit-revision integration pass |
| Graphics/program visual state routes | Presentation mutation | Should be classified before stale rejection policy is applied globally | Not broadened in Phase 1A.1 |
| Caption/theme/weather/config services | Usually non-game-state or separate state | Should not automatically move active game `state_revision` unless explicitly classified | Not changed |

### 6. Added Phase 1A.1 Tests

Added coverage for:

- `test_identical_state_save_does_not_advance_revision`
- `test_metadata_only_secondary_save_does_not_advance_active_revision`
- `test_revision_never_regresses`
- `test_score_command_advances_revision_once`
- `test_event_command_advances_revision_once`
- `test_rules_play_advances_revision_once`
- `test_duplicate_score_command_does_not_advance_revision`
- `test_duplicate_event_command_does_not_advance_revision`
- `test_duplicate_rules_play_command_does_not_advance_revision`
- `test_rejected_command_does_not_advance_revision`
- `test_command_internal_ledger_write_does_not_double_increment_revision`
- `test_history_write_does_not_double_increment_revision`
- `test_direct_score_audit_record_shares_command_revision`
- `test_linked_snapshot_preserves_source_revision`
- `test_cache_immediately_returns_committed_revision`
- `test_revision_sequence_matches_phase1a1_scenario`

Validated scenario:

- Start at revision `500`.
- Touchdown command commits revision `501`.
- Duplicate touchdown command returns revision `501`.
- New independent touchdown command commits revision `502`.
- Identical save remains revision `502`.
- Secondary metadata save remains revision `502`.

### 7. Validation Results

Real project venv access was restored after Windows filesystem permissions were updated for `CodexSandboxUsers`.

Focused Phase 1A suite:

- Command: `.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/test_phase1a_data_integrity.py -q`
- Result: `41 passed in 64.23s`

Related service/cache suite:

- Command: `.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/test_game_operations_service.py tests/test_state_service.py tests/test_event_service.py tests/test_rules_service.py tests/test_live_game_routes_blueprint.py tests/test_gate185_r1_runtime_state_cache.py tests/test_gate184_r117_state_response_cache.py -q`
- Result: `108 passed, 5 failed in 4.16s`

Compilation:

- Command: `.\.venv\Scripts\python.exe -m py_compile state_service.py live_command_service.py game_operations_service.py event_service.py rules_service.py tests/test_phase1a_data_integrity.py`
- Result: passed

### 8. Remaining Failures

The five broader-suite failures are unchanged legacy behavior/test mismatches outside Phase 1A.1:

- `tests/test_game_operations_service.py::test_toggle_halftime_resumes_third_quarter_at_first_and_ten`
  - Existing halftime behavior mismatch. Phase 1A.1 did not change `toggle_halftime`.
- Four `tests/test_event_service.py` XP/2PT conversion tests
  - Existing pending-try enforcement mismatch. Phase 1A.1 did not change conversion semantics.

The previous cache test failures caused by the temporary Python 3.12 workaround are gone under the real Python 3.13 project venv.

### 9. Approval Recommendation

Phase 1A.1 is approved.

The specific blocker found during validation has been repaired: generic saves no longer advance `state_revision` by themselves, while the repaired score/event/rules-play command paths still advance exactly once per distinct accepted command.

Phase 1B stale-client rejection should not be applied globally until the legacy authoritative mutation paths listed in the caller matrix are given explicit revision-boundary behavior. That is a Phase 1B/follow-up integration requirement, not a remaining Phase 1A.1 blocker.

## Phase 1A.2 Legacy Revision Boundary Integration

Date: 2026-08-22

### 1. Scope

This follow-up implemented the Phase 1A.1 recommendation to give remaining legacy authoritative mutation paths explicit revision-boundary behavior before Phase 1B stale-client rejection is applied.

Still not included:

- Frontend `command_id` generation.
- Stale-client rejection/enforcement.
- OBS, Waitress, package, media-isolation, or production-data changes.
- Halftime behavior repair or XP/2PT pending-try behavior repair.

### 2. Implemented Revision Boundaries

`game_operations_service.py`:

- `/api/set` service path now advances `state_revision` once for accepted changes.
- Period-action transitions in `/api/set` advance once.
- Toggle scorebug advances once after successful OBS command handling, not after OBS failure.
- Toggle halftime advances once after accepted state transition.
- End game advances once.
- Reset data advances once from the current active revision while preserving broadcast identity context.
- New broadcast advances once from the current active revision instead of starting revision numbering over from default state.

`event_service.py`:

- Control-source changes advance once.
- Quick correction advances once.
- Event edit advances once and preserves the active revision across canonical rebuild before assigning the next revision.
- Undo advances once whether it removes an event/play or restores from history.
- Restore advances once and preserves the active revision across canonical rebuild.

`rules_service.py`:

- Clock-control saves advance once.
- Field-direction saves advance once.

Existing repaired Phase 1A command paths remain unchanged:

- `/api/score`
- `/api/event-trigger`
- `/api/rules-play`

### 3. Tests Added / Updated

Added focused coverage in `tests/test_phase1a_data_integrity.py` for:

- `test_set_values_advances_revision_once`
- `test_toggle_scorebug_advances_revision_once`
- `test_toggle_halftime_advances_revision_once`
- `test_end_game_advances_revision_once`
- `test_reset_data_advances_from_current_revision`
- `test_new_broadcast_advances_from_current_revision`
- `test_control_source_advances_revision_once`
- `test_quick_correction_advances_revision_once`
- `test_undo_restore_advance_revision_from_current_state`
- `test_clock_control_advances_revision_once`
- `test_field_direction_advances_revision_once`

Updated `tests/test_game_operations_service.py::test_new_broadcast_restores_complete_default_state` to expect the revision field now produced by the service boundary.

### 4. Validation Results

Focused Phase 1A data-integrity suite:

- Command: `.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/test_phase1a_data_integrity.py -q`
- Result: `52 passed in 47.59s`

Related service/cache suite:

- Command: `.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/test_game_operations_service.py tests/test_state_service.py tests/test_event_service.py tests/test_rules_service.py tests/test_live_game_routes_blueprint.py tests/test_gate185_r1_runtime_state_cache.py tests/test_gate184_r117_state_response_cache.py -q`
- Result: `108 passed, 5 failed in 2.89s`

Compilation:

- Command: `.\.venv\Scripts\python.exe -m py_compile state_service.py live_command_service.py game_operations_service.py event_service.py rules_service.py tests/test_phase1a_data_integrity.py tests/test_game_operations_service.py`
- Result: passed

### 5. Remaining Failures

The five remaining failures are the same known legacy behavior/test mismatches:

- `tests/test_game_operations_service.py::test_toggle_halftime_resumes_third_quarter_at_first_and_ten`
- `tests/test_event_service.py::test_extra_point_no_good_records_event_without_score_change`
- `tests/test_event_service.py::test_two_point_failed_records_event_without_score_change`
- `tests/test_event_service.py::test_successful_conversion_outcomes_award_points`
- `tests/test_event_service.py::test_invalid_conversion_outcome_is_rejected`

They are not caused by Phase 1A revision-boundary work. They should be handled as separate behavioral repairs before live production confidence is declared complete.

### 6. Approval Recommendation

Phase 1A.2 legacy revision-boundary integration is approved.

The main active-state mutation paths now have explicit revision assignment before persistence, and generic save still does not advance revision by itself. This makes the backend substantially better prepared for Phase 1B stale-client rejection, pending a final decision on frontend `command_id` generation and stale-write API policy.
