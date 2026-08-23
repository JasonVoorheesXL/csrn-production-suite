# CSRN Phase 1B Operator Safety Repair - 2026-08-22

## Pre-Change Context

- Branch: `gate6/final-visual-matrix`
- HEAD: `20311ed0ca201125560d91ca3c69e142b08e91c2`
- Working tree: dirty before Phase 1B. Phase 1A/1A.1/1A.2 changes were already present.
- Rollback path: `C:\Users\Darth\My Drive\CSRN\Development\CSRN-Production-Suite\work\phase1b_operator_safety_rollback_20260822-104415`

## Files Modified

- `game_operations_service.py`
- `event_service.py`
- `rules_service.py`
- `routes/live_game_routes.py`
- `templates/index.html`
- `templates/overlay.html`
- `tests/test_phase1b_operator_safety.py`
- `tests/test_live_game_routes_blueprint.py`

Existing Phase 1A files remain part of the foundation:

- `live_command_service.py`
- `tests/test_phase1a_data_integrity.py`

## Command Client Design

Command Center now has one shared `LiveCommandClient` in `templates/index.html`.

Responsibilities implemented:

- persistent non-PII `client_id` in `localStorage`
- generated `command_id` per new logical action
- `issued_at` and `expected_revision` included in mutation payloads
- pending command map by logical control group
- reuse of the same `command_id` after UNKNOWN/timeout state
- relevant control-group disabling while SUBMITTING
- COMMITTED / FAILED / UNKNOWN status surfaced through operator notices and `operatorCommandHealth`
- revision-aware mutation acceptance
- stale poll rejection when `incomingRevision < currentRevision`
- poll health state: HEALTHY / DEGRADED / STALE

`GameStateManager.mutate()` now routes live mutations through `LiveCommandClient`, so callers do not carry bespoke pending logic.

## Backend Command-ID Coverage Matrix

| Route | Action | `state_revision` integrated | `command_id` accepted | Duplicate suppression | Safe automatic retry | Notes |
| --- | --- | --- | --- | --- | --- | --- |
| `/api/score` | direct score adjustment | Yes | Yes | Yes | Yes | Phase 1A path retained |
| `/api/event-trigger` | TD/FG/XP/2PT/turnover/penalty/ejection/kickoff | Yes | Yes | Yes | Yes | Phase 1A path retained |
| `/api/rules-play` | detailed play entry | Yes | Yes | Yes | Yes | Phase 1A path retained |
| `/api/set` | absolute state/period changes | Yes | Yes | Yes | Yes | Phase 1B added duplicate replay |
| `/api/control-source` | authority switch | Yes | Yes | Yes | Yes | Phase 1B added duplicate replay |
| `/api/game-correction` | quick correction/field spot | Yes | Yes | Yes | Yes | Phase 1B added duplicate replay |
| `/api/field-direction` | drive direction | Yes | Yes | Yes | Yes | Absolute setter plus duplicate replay |
| `/api/clock-control` | start/stop/set/adjust/reset/visibility | Yes | Yes | Yes | Yes | Adjust is unsafe without duplicate replay; now protected |
| `/api/undo` | undo last event/history | Yes | Yes | Yes | Yes | High-risk path now protected |
| `/api/restore` | restore last undone event | Yes | Yes | Yes | Yes | High-risk path now protected |
| `/api/toggle-halftime` | toggle halftime | Yes | Yes | Yes | Yes | Toggle retry protected by command ledger |
| `/api/toggle-scorebug` | toggle scorebug | Yes | Yes | Yes | Yes | OBS failure still does not mutate |
| `/api/end-game` | mark final | Yes | Yes | Yes | Yes | Duplicate final does not reapply |
| `/api/reset-data` | reset active game data | Yes | Yes | Yes | Yes | Duplicate reset does not repeat |
| `/api/new-broadcast` | return to new broadcast defaults | Yes | Yes | Yes | Yes | Duplicate new-broadcast does not repeat |
| `/api/events/<id>/edit` | edit canonical event/play | Yes | Yes | Yes | Yes | Phase 1B added duplicate replay |

## Frontend Mutation Coverage Matrix

| Frontend caller | Route | Coordinator coverage |
| --- | --- | --- |
| `score()` | `/api/score` | Yes |
| `confirmAutomationEvent()` | `/api/event-trigger` | Yes |
| `triggerEvent()` / guided events | `/api/event-trigger` | Yes |
| `submitPenalty()` | `/api/event-trigger` | Yes |
| `quickKickoff()` | `/api/event-trigger` | Yes |
| `submitEjection()` | `/api/event-trigger` | Yes |
| `submitPlayEntry()` | `/api/rules-play` | Yes |
| `setState()` / `setStateFrom()` / period action | `/api/set` | Yes |
| `setControlSource()` | `/api/control-source` | Yes |
| `commitFieldSpot()` / `submitQuickCorrection()` | `/api/game-correction` | Yes |
| `setFieldDrive()` / `setDriveDirection()` | `/api/field-direction` | Yes |
| `clockAction()` / `adjustClock()` / clock visibility | `/api/clock-control` | Yes |
| `undo()` | `/api/undo` | Yes, except coin-toss undo remains its own route |
| `restoreLastUndone()` | `/api/restore` | Yes |
| `toggleScorebug()` | `/api/toggle-scorebug` | Yes |
| `toggleHalftime()` | `/api/toggle-halftime` | Yes |
| `endGame()` | `/api/end-game` | Yes |
| `resetData()` | `/api/reset-data` | Yes |
| `newBroadcast()` | `/api/new-broadcast` | Yes |

Search result after repair: no raw `api()` calls remain for the listed dangerous live-game mutation routes in `templates/index.html`.

## Pending-State Design

On command submit:

- status becomes `SUBMITTING`
- body receives `data-command-status="SUBMITTING"`
- matching control-group buttons are disabled
- operator notice is updated immediately

On commit:

- returned authoritative state is accepted only if its revision is not older
- UI renders immediately from the mutation response
- status briefly shows `COMMITTED`
- controls are released

On failure:

- controls are released
- error is shown through the existing operator-friendly error message path

On timeout/fetch uncertainty:

- status becomes `UNKNOWN`
- pending command is retained in localStorage with the same `command_id`
- retry reuses the same command identity

## Client ID Design

`client_id` is a UUID-like random identifier persisted in browser `localStorage` under `csrn.clientId.v1`.

It does not use name, IP address, account identity, school identity, or other PII. A different device/browser gets a different client ID.

## Revision Rules

Mutation response:

- accept if `response.state_revision >= currentRevision`
- reject if older

Polling response:

- accept newer or equal revisions
- reject older revisions and log to console
- revision jumps are accepted as normal multi-client convergence

## Stale Thresholds

Command Center:

- HEALTHY: fewer than two consecutive poll failures and last update age at or under 4 seconds
- DEGRADED: at least two poll failures or last update older than 4 seconds
- STALE: at least four poll failures or last update older than 8 seconds

These thresholds are based on the current 1.25 second visible Command Center poll interval and 6.5 second poll abort timeout. They were not changed in this phase.

## OBS Overlay Health

`templates/overlay.html` now exposes `window.CSRNOverlayHealth`:

- `overlay_last_success`
- `overlay_last_revision`
- `overlay_state_age`
- `consecutive_failures`
- `status`

The overlay continues rendering the last valid state and does not show a viewer-facing stale stamp by default. Health is available through the browser source runtime object and body data attributes for operator diagnostics/rehearsal tooling.

## Toggle Safety Decisions

- Scorebug and halftime remain backend toggle routes for compatibility.
- Retrying the same logical toggle is now safe because the backend ledger suppresses duplicate `command_id`.
- Clock visibility goes through `/api/clock-control` as an absolute `visible` value and also carries a command ID.

## Undo / Restore Protection

`undo()` and `restore()` now accept command envelopes and record command results. A duplicated logical undo/restore returns the original result and cannot pop a second history/event entry.

## Tests Added

New file: `tests/test_phase1b_operator_safety.py`

Coverage includes:

- command client command-ID reuse after timeout
- new action receives a new command ID
- score/event/rules-play pending control coverage
- older poll rejection
- newer poll acceptance
- revision jump acceptance
- stale health and health recovery
- duplicate retry safety for score, event, rules play, set, clock, game correction, undo, restore, control source, and toggle
- mobile pending-state visibility contract
- reconnect/authoritative refresh contract
- UNKNOWN state does not generate a new command ID
- poll/cache cannot overwrite newer mutation state
- artificial latency at 500 ms, 2 s, 5 s, and 10 s
- lost-response retry demonstration
- multi-client revision convergence
- OBS stale-health contract

## Exact Test Results

Focused Phase 1B:

- Command: `.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/test_phase1b_operator_safety.py -q`
- Result: `33 passed in 18.59s`

Focused Phase 1A:

- Command: `.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/test_phase1a_data_integrity.py -q`
- Result: `52 passed in 44.21s`

Combined focused gate:

- Command: `.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/test_phase1a_data_integrity.py tests/test_phase1b_operator_safety.py -q`
- Result: `85 passed in 57.38s`

Related service/cache/route suite:

- Command: `.\.venv\Scripts\python.exe -m pytest -p no:cacheprovider tests/test_game_operations_service.py tests/test_state_service.py tests/test_event_service.py tests/test_rules_service.py tests/test_live_game_routes_blueprint.py tests/test_gate185_r1_runtime_state_cache.py tests/test_gate184_r117_state_response_cache.py -q`
- Result: `108 passed, 5 failed in 2.97s`

Compilation:

- Command: `.\.venv\Scripts\python.exe -m py_compile live_command_service.py game_operations_service.py event_service.py rules_service.py routes/live_game_routes.py tests/test_phase1a_data_integrity.py tests/test_phase1b_operator_safety.py tests/test_live_game_routes_blueprint.py`
- Result: passed

## Artificial Latency Results

Automated latency simulations passed at:

- 500 ms
- 2 s
- 5 s
- 10 s

In each case, repeated attempts using the same logical TD command produced one event, one score mutation, and one committed revision.

## Lost-Response Retry Demonstration

`test_lost_response_retry_demonstration` commits a touchdown, discards the idea of the first HTTP response, and retries the same `command_id`. The retry returns revision `501`, and the event list remains length `1`.

## Multi-Client Revision Results

`test_multi_client_revision_convergence` simulates:

- statistician at revision 500 commits TD to revision 501
- broadcaster with stale expected revision 500 commits an independent direct score adjustment
- final state converges at revision 502 without overwriting the TD

`test_multi_client_stale_poll_after_newer_mutation_rejected` confirms a client at revision 504 rejects a later-arriving poll at revision 500.

## OBS Stale-State Results

`test_obs_stale_rehearsal_contract` confirms the overlay includes:

- `CSRNOverlayHealth`
- `overlay_last_revision`
- failure transition through `updateOverlayHealth(false)`

Runtime behavior remains intentionally operator/diagnostic-facing, not viewer-facing.

## Remaining Limitations

- Coin-toss submit/undo uses separate `/api/coin-toss` routes and was not included in the minimum requested active live-game route list.
- Graphics routes remain outside backend command-ledger coverage; they are presentation mutations and should be classified before retry semantics are applied.
- The five known legacy behavior/test mismatches remain:
  - halftime resume
  - four XP/2PT pending-try behavior tests
- This pass did not run a real browser/mobile viewport automation session. The mobile safety assertions are automated source/contract tests plus backend latency simulations. A controlled rehearsal should still be run on the actual phone workflow.
- No Phase 2 media isolation, Waitress tuning, Drive persistence redesign, package upgrades, or OBS encoder/audio changes were made.

## Approval Recommendation

Phase 1B code-level operator safety is ready for controlled rehearsal.

It should not be treated as final game-night approval until:

1. the actual Command Center and statistician phone are rehearsed under induced network delay,
2. OBS overlay health is observed during runtime-state fetch failures,
3. the remaining halftime and XP/2PT behavior mismatches are either fixed or formally accepted as known behavior.

No production game data was intentionally altered.
