# CSRN Phase 1D Runtime Diagnostics / Play Register Authority

Date: 2026-08-22

Status: COMPLETE FOR PHASE 1D ONLY

Rollback snapshot: `work\phase1d_runtime_diagnostics_rollback_20260822-181713`

## Incident Finding

The statistician phone and Command Center laptop were already intended to use Flask as the sole authority. They do not need, and must not use, client-to-client propagation.

The problem was in the register retrieval contract:

- `/api/rules-play` commits to authoritative state, but its success response uses `command_result_state()`, which strips `plays` and `events`. It includes the single created `play`, but not the canonical register collection.
- `/api/runtime-state` intentionally omits `plays` and `events` to keep sub-second polling lightweight.
- `/api/state` includes the full canonical state, including `plays`, but routine laptop polling uses `/api/runtime-state`, not `/api/state`.

That means a play could be committed by Flask while another client only saw a revision bump through `/api/runtime-state` and did not receive the canonical play register. This explains the rehearsal symptom without requiring a new database.

## Authoritative Storage

Authoritative game state is persisted through:

- `app.py`: `STATE_FILE = PRODUCT_PATHS.state_file`
- `app.py`: `STATE_REPOSITORY = StateRepository(CORE_PERSISTENCE, STATE_FILE, DEFAULT_STATE)`
- `StateService` normalizes/public-renders that persisted state.
- `RulesService.play()` appends committed records to `state["plays"]` and `state["events"]`, then saves through the existing state service path.

The authoritative collection is `state["plays"]` in the persisted game state, not phone memory and not laptop memory.

## Register Path Audit

Statistician phone play submit:

1. Phone calls `POST /api/rules-play`.
2. Flask `RulesService.play()` appends `play` to authoritative `state["plays"]`.
3. Response is slim: `state` excludes `plays` and `events`; response includes the created `play`.
4. Phone now fetches `GET /api/play-register` after commit to retrieve the canonical collection from Flask.

Laptop Command Center register:

1. Laptop polls `GET /api/runtime-state`.
2. Runtime state remains lightweight and does not carry `plays`.
3. When runtime revision advances, laptop now fetches `GET /api/play-register`.
4. Laptop renders from the canonical play collection returned by Flask.

Full refresh:

- `/api/state` still returns full public state and can hydrate the register at startup/full refresh.

Runtime polling:

- `/api/runtime-state` remains lightweight and does not carry the full game history.

## New Endpoint

Added authenticated `GET /api/play-register`.

Response includes:

- `state_revision`
- `broadcast_id`
- `plays`
- `events`
- `play_count`
- `event_count`
- `latest_play_id`
- `latest_event_id`

This keeps the healthy architecture:

`client command -> Flask -> authoritative persisted play -> any client can retrieve/render it`

and avoids:

`phone -> Flask -> laptop -> persistence`

## Runtime Diagnostics

Added structured diagnostics for:

- `/api/rules-play`
- `/api/event-trigger`
- `/api/score`
- `/api/set`
- `/api/game-correction`
- `/api/clock-control`
- `/api/undo`
- `/api/restore`
- `/api/runtime-state`
- `/api/play-register`

Each relevant record captures:

- timestamp
- request ID
- command ID
- client ID
- route/action/method/status
- duration
- state revision before/after
- broadcast ID
- replay/duplicate status
- play/event IDs
- play counts before/after
- latest play ID
- error type/message

## Client Diagnostics

Added event-driven client telemetry for:

- `COMMAND_SUBMIT`
- `COMMAND_COMMITTED`
- `COMMAND_UNKNOWN`
- `COMMAND_FAILED`
- `POLL_ACCEPTED`
- `POLL_REJECTED_STALE`
- `PLAY_REGISTER_RECEIVED`
- `REGISTER_UPDATED`
- `REGISTER_EMPTY_UNEXPECTEDLY`
- `REGISTER_RENDER_ERROR`
- commercial start/stop correlation events

Register comparison fields include:

- client ID
- client role
- current revision
- server/canonical play count where known
- received play count
- rendered play count
- latest play ID
- broadcast ID

Telemetry is event-driven. There is no new high-frequency telemetry poller.

## Log Location

Primary log location:

`%LOCALAPPDATA%\CSRN\Logs\runtime-diagnostics.jsonl`

If that local folder cannot be created, the service falls back to:

`%TEMP%\CSRN\Logs\runtime-diagnostics.jsonl`

Both locations are local/unsynchronized and outside the Google Drive-backed project tree. The active path is shown in the Runtime Diagnostics panel and incident bundle metadata.

Logging uses:

- asynchronous queued writer
- bounded ring buffer
- bounded rotating JSONL files
- exception isolation so logging failures do not break live mutations

## Operator Diagnostics

Added a compact Runtime Diagnostics section under Technical Diagnostics with:

- server logging health
- Command Center revision
- OBS overlay revision
- authoritative play count
- latest play ID
- poll failure count
- recent runtime events
- active log location

Added `Export Incident Bundle`.

Bundle includes:

- metadata
- recent in-memory diagnostic events
- current state snapshot summary
- runtime-state snapshot
- active runtime diagnostic log when present
- OBS overlay-health snapshot

Export does not mutate game state.

## Commercial Correlation

Sponsor advertisement run/stop now records diagnostic events:

- `COMMERCIAL_START_REQUESTED`
- `COMMERCIAL_STARTED`
- `COMMERCIAL_FAILED`
- `COMMERCIAL_STOP_REQUESTED`
- `COMMERCIAL_STOPPED`

No sponsor/media serving behavior was changed.

## Validation Results

- Phase 1D focused diagnostics/register tests: 15 passed in 1.11s.
- Live/system/Phase1D route tests: 51 passed in 1.46s.
- Phase 1A + Phase 1B + Phase 1C regression: 95 passed in 69.08s.
- Football workflow/service/Phase1C/Phase1D suite: 94 passed in 2.61s.
- Python compile check for touched Python files: passed.

Measured async logging overhead test:

- `RuntimeDiagnosticsService.record()` returned in under 50 ms while the writer was forced to sleep for 200 ms.

## Files Changed

- `runtime_diagnostics_service.py`
- `routes\live_game_routes.py`
- `routes\system_routes.py`
- `templates\index.html`
- `tests\test_phase1d_runtime_diagnostics.py`
- `Documentation\Audits\CSRN_PHASE1D_RUNTIME_DIAGNOSTICS_20260822.md`

## Incident Bundle Addendum

Bundle reviewed:

`C:\Users\Darth\AppData\Local\CSRN\Logs\IncidentBundles\CSRN-Incident-Bundle-20260822-184606`

Findings:

- Authoritative state ended at revision 16 with 9 plays and 9 events.
- Latest authoritative play was `FB-2026-TEST-W01-001-0009`.
- OBS overlay health was `HEALTHY` at revision 16.
- `/api/runtime-state` repeatedly reported authoritative play counts correctly, but `runtime_contains_plays` was false by design.
- `/api/play-register` returned the canonical play collection, and both command center and statistician clients later reported `received_play_count: 9` and `rendered_play_count: 9`.
- The statistician client reported transient `REGISTER_EMPTY_UNEXPECTEDLY` events immediately after slim mutation responses. Root cause: the client applied the slim `/api/rules-play` state, which excludes `plays/events`, before the canonical `/api/play-register` refresh restored the register.

Follow-up correction:

- The play-submit client extractor now preserves the current `plays` and `events` arrays while applying the slim mutation state, then immediately refreshes `/api/play-register`.
- This prevents the temporary blank register between mutation acknowledgement and canonical register fetch.

Additional validation after addendum:

- Phase 1D focused diagnostics/register tests: 15 passed in 0.64s.
- Live/system/Phase1D route tests: 51 passed in 1.70s.

## Mutation Acknowledgement Semantics Addendum

Rehearsal defect covered:

- Command `client-1787438594199-8cd6202286e66:/api/rules-play:1787442153436:15c51ab5220f6` committed Flask state revision `15 -> 16`, created play `FB-2026-TEST-W01-001-0009`, and increased the canonical play count `8 -> 9`.
- The submitting phone nevertheless logged a failed command after transport uncertainty and displayed a play-recording failure message.

Correction:

- `LiveCommandClient` now classifies aborted fetches, transport failures, and unreadable mutation responses as `UNKNOWN_COMMIT` instead of definitive failure.
- `UNKNOWN_COMMIT` commands remain pending under the same control group and are retried/reconciled with the original `command_id`; no new command ID is generated for reconciliation.
- Explicit non-OK server responses remain `DEFINITIVE_FAILURE`.
- `submitPlayEntry()` now separates mutation acknowledgement from register/UI follow-up. A confirmed commit shows `Play recorded.`, while post-commit register sync trouble shows `Play recorded. Updating play register...`; only definitive pre-commit rejection uses `Play was not recorded.`
- The Record Play workflow immediately displays `RECORDING...` and remains protected by the shared pending command controls while unresolved.

Validation after acknowledgement repair:

- Phase 1D focused diagnostics/register tests: 17 passed in 0.86s.
- Phase 1A + Phase 1B + Phase 1C + Phase 1D regression: 112 passed in 90.89s.
- Live/system/Phase1D route tests: 53 passed in 2.10s.

## Route-Level Commit Observability Hardening Addendum

Gap addressed:

- `/api/rules-play` previously emitted `SERVER_RULES_PLAY` only on the straight-line path after `RulesService.play()` returned.
- If the service committed authoritative state but response preparation then raised, the committed play could exist in state/ledger without a matching route diagnostic for that command.

Correction:

- `rules_play()` now keeps the existing HTTP contract and status mapping while wrapping service invocation and response construction in a narrow `try/except`.
- The intended HTTP status is determined from the existing result codes: `INVALID_PLAY -> 400`, `NO_ACTIVE_BROADCAST -> 409`, `CONTROL_SOURCE_LOCKED -> 409`, and successful/other existing OK handling -> `200`.
- Normal requests prepare the Flask response, emit exactly one `SERVER_RULES_PLAY` record, then return it.
- If response preparation raises after the rules service has returned, the route reloads the authoritative summary and emits one `SERVER_RULES_PLAY` record with the committed revision/play counts, `play_id`, intended `http_status`, `response_uncertain: true`, and the exception type/message, then re-raises the original exception to Flask.
- Diagnostic failure handling does not replace the original response-path exception.
- `log_route()` now includes a `response_uncertain` boolean; normal route records remain `false`.

Focused regression coverage added:

- `test_rules_play_logs_committed_mutation_when_response_preparation_raises` monkeypatches route-level `jsonify` to raise after the stub rules service commits.
- The test verifies authoritative state advances `10 -> 11`, play count advances `0 -> 1`, the committed `play_id` is retained, exactly one matching `SERVER_RULES_PLAY` record exists, intended status is `200`, `response_uncertain` is true, and the response-preparation error is recorded.

Validation for this addendum:

- Python compile check for the touched route and focused test: passed.
- The available connector execution sandbox does not include Flask, so pytest could not be executed there; no new passing test totals are claimed from that sandbox. The authoritative laptop environment should run the existing Phase 1D/Phase 1A-1C regression commands before game use.

Files changed by this addendum:

- `routes\live_game_routes.py`
- `tests\test_phase1d_runtime_diagnostics.py`
- `Documentation\Audits\CSRN_PHASE1D_RUNTIME_DIAGNOSTICS_20260822.md`

Boundary remains unchanged: no Phase 2 work, media redesign, OBS changes, polling changes, persistence redesign, Waitress/server redesign, or play-register authority redesign.

## Boundary

No Phase 2 work was started.

No media serving redesign was performed.

No Waitress/server redesign was performed.

No persistence backend redesign was performed.

STOP.
