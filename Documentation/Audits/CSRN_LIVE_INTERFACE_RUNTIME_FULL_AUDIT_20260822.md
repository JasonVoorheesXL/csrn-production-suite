# CSRN Live Interface Runtime Full Audit - 2026-08-22

Audit scope: CSRN Production Suite live football runtime, Command Center, statistician/mobile workflow, OBS overlay, polling, persistence, media serving, and production safety under latency.

Repository audited: `C:\Users\Darth\My Drive\CSRN\Development\CSRN-Production-Suite`

Audit mode: static engineering audit only. No application code, packages, virtual environment, OBS configuration, customer/runtime game records, Git branch, or Git history were intentionally modified. The only repository write performed for this audit was creation of this report path.

## 1. Executive Summary

CSRN is not safe for another live football game without repairs to live-command idempotency, latency feedback, and media/request isolation.

The observed duplicate touchdowns and over-corrected score are directly explainable by the current architecture. Live mutation endpoints accept every valid click as an independent command. The frontend does not attach a unique command ID, does not disable or mark most live controls as pending, and does not expose a consistent READY / SUBMITTING / ACCEPTED / COMMITTED / FAILED / STALE state. Under latency, a legitimate operator can press once, see no trusted acknowledgement, press again, and produce a second valid score/event mutation.

The Waitress queue buildup is most likely a combined worker-starvation problem: high-frequency polling from Command Center, legacy overlay, production-theme runtime, captions, weather, theme polling, and previews shares the same 16-thread Waitress pool with large media delivery and synchronous Google Drive-backed JSON persistence. Sponsor Advertisement playback is a credible and probably material contributor because `/sponsor-ad-files/<filename>` is served by Flask/Waitress using `send_from_directory`, not by a separate static/media server. Whether it was the sole trigger was not proven in this audit.

Command Center and overlay consistency is improved by mutation responses and `/api/runtime-state`, but there is still no authoritative monotonic state revision suitable for command acknowledgement, stale-client detection, or old-response rejection. `/api/runtime-state` exposes a `revision`, but it is derived from timestamps and is not guaranteed to advance for every score/state mutation. The OBS overlay can silently display stale state after repeated polling failures, and the production-theme runtime can deactivate on render/fetch error without an operator-facing stale-state signal.

## 2. Repository / Runtime State

| Item | Observed value |
|---|---|
| Branch | `gate6/final-visual-matrix` |
| HEAD | `20311ed0ca201125560d91ca3c69e142b08e91c2` |
| Upstream | `origin/gate6/final-visual-matrix` |
| Git status | Dirty. Many modified tracked source/test/runtime files and many untracked audit/backup/data/static files. `git status --short` warned `.pytest_cache/` could not be opened. |
| Python from PATH | `python` and `py` not found in audit shell. |
| Local venv execution | `.venv\Scripts\python.exe --version` and `.venv-stale-20260730-125250\Scripts\python.exe --version` failed with `Access is denied`. |
| Documented Python | Project Bible says launcher verifies Python 3.13.14; not independently executable from audit shell. |
| Flask entrypoint | `app.py:create_app()` delegates to `application_factory.create_application`; module-level `app = create_app()` at `app.py:3018-3033`. |
| Waitress startup | `app.py:3049-3060`: `serve(app, host="0.0.0.0", port=5050, threads=16)`. |
| Runtime read caches | `state_read_cache.py` and `runtime_state_cache.py` wrap `/api/state` and `/api/runtime-state` with 250 ms TTL after `app = create_app()`. |

Major live-operation state/services/routes verified in source:

| Area | Files/functions/routes |
|---|---|
| Active state | `app.py:1686-1691`, `state_service.py`, `core_repositories.py:148-178`, `persistence_engine.py` |
| Runtime/public state | `routes/system_routes.py:61-70`, `app.py:1711-1722`, `state_service.py:179-293` |
| Direct score/state | `routes/live_game_routes.py:32-52`, `game_operations_service.py:100-225` |
| Event engine | `routes/live_game_routes.py:73-110`, `event_service.py:136-618`, `event_service.py:849-959` |
| Detailed play/statistician engine | `routes/live_game_routes.py:173-185`, `rules_service.py:203-805` |
| Clock/field/period | `routes/live_game_routes.py:155-171`, `rules_service.py:148-201`, `game_operations_service.py:147-225` |
| Graphics/sponsor/highlight | `routes/graphics_routes.py`, `graphics_service.py` |
| Sponsor ad media | `routes/asset_routes.py:29-36`, `routes/asset_routes.py:267-269` |
| OBS controls | `routes/obs_routes.py`, `obs_service.py`, `obs_client.py` |
| Command Center | `templates/index.html` |
| Legacy OBS overlay | `templates/overlay.html` |
| Production theme overlay runtime | `static/csrn-production-theme-runtime.js` |
| Captions/weather overlay polling | `templates/captions.html`, `templates/weather.html` |

## 3. Live Incident Reconstruction

Duplicate touchdown path:

1. Operator taps `TD` in Command Center or statistician UI. Buttons are plain `onclick` handlers in `templates/index.html:331`, `templates/index.html:340`, and statistician controls around `templates/index.html:1465-1480`.
2. The guided event modal opens. `confirmAutomationEvent()` sets text to `Recording event...` but does not disable the confirm button, close the action surface immediately, or attach a command ID. Evidence: `templates/index.html:2961-2969`.
3. It sends `POST /api/event-trigger`. Evidence: `templates/index.html:2968-2969` and `routes/live_game_routes.py:73-85`.
4. `EventService.trigger()` loads state under a lock, validates authority, applies score delta, appends event/play rows, and saves. Evidence: `event_service.py:143-206`, `event_service.py:236-274`, `event_service.py:527-601`.
5. There is no idempotency key, duplicate-event check, expected revision, or server-side command ledger. A second identical request is a second valid event.
6. If latency is long enough for a second tap, the second request queues behind the first lock and then executes against the newly scored state, adding another touchdown.

Direct score over-correction path:

1. Score buttons call `score('home', -1)` etc. Evidence: `templates/index.html:328-340`.
2. `score()` sends `POST /api/score` with `{team,delta,source:'broadcaster',override:true}`. Evidence: `templates/index.html:2883-2890`.
3. `GameOperationsService.score()` treats each request independently, pushes history, increments/decrements score, saves state, and returns state. Evidence: `game_operations_service.py:100-145`.
4. Buttons are not disabled while request is in flight, and there is no command ID/idempotency/revision check. Repeated `-1` clicks are all valid score mutations.

Facebook graphics behind audio has two plausible classes. This audit cannot inspect OBS runtime telemetry or Facebook stream timestamps, but code confirms stale CSRN graphics are plausible: `/overlay` and production-theme runtime can continue showing last successful state without a stale warning. Evidence: `templates/overlay.html:218-223`, `static/csrn-production-theme-runtime.js:2394-2577`.

## 4. Confirmed Defects

### P0 - Live mutations are not idempotent and can execute more than once

Symptom: duplicated touchdowns, duplicated first downs/penalties/kickoffs/plays, repeated direct score changes.

Evidence: mutation routes accept raw payloads and call services directly: `routes/live_game_routes.py:32-203`. Direct score mutates every time in `game_operations_service.py:100-145`. Event mutations append every time in `event_service.py:527-601`. Detailed statistician plays append every time in `rules_service.py:587-798`. Search found no command ID, request ID, idempotency key, expected revision, or mutation ledger on these paths.

Root cause: commands are modeled as immediate state patches/events, not as uniquely identified operations with exactly-once semantics.

Reproduction: in an isolated test game, submit two identical `POST /api/event-trigger` TD requests or two identical `POST /api/score` `-1` requests. Both will mutate state.

Production consequence: live score and event/stat history can be corrupted by normal human retry behavior under lag.

Recommended repair: introduce `command_id`; persist a bounded command ledger per broadcast; return prior result for duplicate command IDs; require `expected_revision` or perform ordered command sequencing; include resulting `state_revision` and `command_status` in every mutation response.

Regression test: delayed first response plus second identical request must produce one touchdown and one command result, not two events.

### P0 - Live controls do not provide consistent pending/accepted/committed/failure states

Symptom: operator experience is "I clicked it, nothing happened, so I clicked again."

Evidence: direct buttons are inline `onclick` controls at `templates/index.html:328-343`, `templates/index.html:1492-1494`, and many graphics controls. `score()` does not disable buttons (`templates/index.html:2883-2890`). `confirmAutomationEvent()` sets text but does not prevent repeat submission (`templates/index.html:2961-2969`). `submitPlayEntry()`, `clockAction()`, `submitPenalty()`, `quickKickoff()`, `undo()`, and `restoreLastUndone()` lack shared pending locks.

Root cause: there is no frontend mutation coordinator. `GameStateManager.mutate()` updates `currentState` from responses but does not track in-flight commands or lock control groups (`templates/index.html:2525-2541`).

Recommended repair: a single `CommandClient` that generates command IDs, disables the relevant control group, shows SUBMITTING immediately, shows ACCEPTED/COMMITTED from server response, tracks timeout separately from unknown commit state, and prevents duplicate submits until resolved or explicitly retried.

### P0 - Score, events, and statistics can disagree

Evidence: direct score correction changes `home_score`/`visitor_score` only in `game_operations_service.py:125-134`; it does not append an event or correction-log entry. Event score changes append events/plays (`event_service.py:598-600`). Statistics are built from recorded plays/events and current state in separate paths. Quick correction logs game-state corrections but not direct score corrections (`event_service.py:620-682`).

Root cause: score is both directly mutable state and event-derived historical data, without an auditable score-adjustment event model.

Consequence: scoreboard may be made visually correct while event history/statistics remain wrong, or duplicated events may make statistics wrong even after direct score correction.

Recommended repair: define authoritative score policy. Either derive score from canonical events plus explicit score-adjustment events, or maintain direct score as primary with mandatory audited adjustment records and reconciliation warnings.

### P1 - Sponsor advertisement video is served through Waitress worker pool

Evidence: sponsor-ad assets with placement `sponsor_advertisement_video` are stored under `SponsorAdvertisements` and served at `/sponsor-ad-files/<filename>` by `send_from_directory`: `routes/asset_routes.py:29-36`, `routes/asset_routes.py:267-269`. Overlay video tags use sponsor media URL as source and call `.load()`/`.play()` when state selects the video: `templates/overlay.html:220`. Production theme runtime creates video elements with `preload="auto"`: `static/csrn-production-theme-runtime.js:2131-2148`.

Root cause: large media delivery and live-control/runtime-state JSON share the same Waitress threads.

Consequence: one or more OBS/preview video requests can occupy workers long enough to delay `/api/runtime-state`, `/api/state`, and mutation acknowledgements. Range support is not implemented explicitly in CSRN; behavior depends on Flask/Werkzeug. No evidence of X-Sendfile, CDN, separate static server, or OBS-local preloading was found.

Confidence: high that this path is capable of contributing to worker starvation; medium that it was the dominant live trigger without request logs.

Recommended repair: move sponsor/video media off the Flask control app path: separate static server, OBS-local file source, reverse proxy with Range and sendfile support, or preloaded local media cache. Game-control traffic must not compete with MP4 transfer.

### P1 - Overlay can silently show stale game state

Evidence: legacy overlay polls `/api/runtime-state` with 2 s abort, in-flight guard, 500 ms normal delay, exponential backoff up to 5 s, and silently catches errors: `templates/overlay.html:218-223`. It keeps last DOM values on failure. There is no overlay `last_success` timestamp rendered or exposed to operator. Production-theme runtime fetches `/api/themes/public-state`, `/api/runtime-state`, and captions; on errors it logs/deactivates and reschedules, but does not signal operator stale scoreboard state: `static/csrn-production-theme-runtime.js:2388-2577`.

Root cause: polling health is internal and viewer/operator-visible state age is not tracked.

Consequence: OBS can render old scores while audio/video production remains otherwise current. This matches the additional incident hypothesis B.

Recommended repair: add `server_timestamp`, true monotonic `state_revision`, `overlay_last_success`, `overlay_last_revision`, request sequence, and operator-only stale-source telemetry. Do not place viewer-facing warnings by default; surface health in Command Center and optionally in an OBS-safe operator monitor.

### P1 - `/api/runtime-state` revision is not a sufficient authoritative revision

Evidence: `state_service.py:291-337` computes `revision` as max of selected timestamps like `last_saved_at`, `updated_at`, graphics timestamps, last event timestamps, and ticker timestamps. Direct score and many state changes do not consistently set `last_saved_at` or `updated_at`. Therefore two score changes can occur without a guaranteed monotonic revision advance.

Root cause: revision is derived opportunistically from domain timestamps, not assigned transactionally during every state write.

Consequence: clients cannot reject old responses, detect missed commits reliably, or correlate command responses to polling convergence.

Recommended repair: increment `state_revision` inside the same lock/transaction as every state write and include it in mutation responses and read endpoints.

### P1 - Synchronous JSON persistence and linked snapshot writes occur in request threads

Evidence: `JsonPersistenceEngine.save()` writes temp file, flushes, fsyncs, snapshots previous file, atomically replaces, and prunes backups in the request path: `persistence_engine.py:80-123`, `persistence_engine.py:208-228`. `StateService.save()` also persists a linked broadcast snapshot when `broadcast_id` exists: `state_service.py:143-152`; app implementation writes broadcast list and detail JSON: `app.py:1647-1668`.

Root cause: live mutation acknowledgements wait for disk, backup copy, backup prune, state normalization, linked broadcast list write, and Google Drive synchronization effects if the repo/Data path is synced.

Consequence: p95/p99 mutation latency can rise enough to create repeated clicks and Waitress queue growth.

Recommended repair: keep the authoritative live state in one fast local store during broadcast, write append-only command/event log, batch/archive secondary snapshots asynchronously, and move synchronized Drive archival out of the request critical path.

### P1 - Multiple high-frequency pollers share one app server

Confirmed recurring client request inventory:

| Client/page | Endpoint(s) | Interval | Timeout | In-flight guard | Overlap risk | Server work |
|---|---:|---:|---:|---|---|---|
| Command Center `templates/index.html` | `/api/runtime-state` | 1.25 s visible, 3 s hidden plus backoff | 6.5 s AbortController | yes | no per tab | load normalized state, runtime view, cache 250 ms |
| Legacy overlay `templates/overlay.html` | `/api/runtime-state` | 500 ms normal; backoff 500 ms to 5 s | 2 s AbortController | yes | no same overlay | same runtime state, DOM/video work |
| Legacy overlay theme check | `/api/themes/public-state` | 2 s fixed | none | no | yes if slow | theme public state |
| Production theme runtime | `/api/themes/public-state`, `/api/runtime-state`, `/api/captions/overlay-state` | 300-900 ms adaptive | none in `fetchJson` | renderBusy prevents same-loop overlap | no same runtime loop | theme state, runtime state, captions |
| Captions preview | `/api/captions/overlay-state` | 250 ms fixed | none | no | yes | caption state JSON/service |
| Weather overlay | `/api/weather/overlay-state` | 1 s fixed | none | no | yes | weather state |
| Security check | security status path | 15 s | none observed | no | possible | auth/security |
| Sponsor/player video | `/sponsor-ad-files/*`, media URLs | browser media-driven | browser-defined | no app-level guard | yes, multiple clients | file streaming via Waitress |

Base live load estimate with 1 Command Center, 1 OBS overlay using both legacy and production runtime, and 1 statistician phone: roughly 4 to 8 JSON requests/second before captions/weather/previews/media, plus mutation bursts. With captions preview open, add 4 requests/second. This is not fatal when all routes are sub-50 ms, but it becomes unsafe when media/file/Drive operations hold workers for seconds.

## 5. Probable Defects

| Severity | Defect | Confidence | Reason |
|---|---|---:|---|
| P1 | Sponsor video playback contributed to Waitress queues | Medium-high | MP4 served by Waitress route; video tags preload/play; same 16 worker pool handles state. Need request logs to prove live timing. |
| P1 | Google Drive synchronized-folder I/O materially increased latency | Medium | Repository path is under `My Drive`; persistence snapshots and JSON rewrites are synchronous. Need measured p95/p99. |
| P1 | OBS/Facebook visual delay was stale overlay data rather than true A/V desync | Medium | Overlay stale behavior confirmed; OBS/Facebook telemetry unavailable. |
| P2 | Old `/api/runtime-state` responses can overwrite newer local UI after mutation | Medium | Command Center merges polling snapshots into current state and lacks revision rejection; mutation and poll can race. |
| P2 | Multiple tabs can multiply poll load and mutation risk | High | Per-tab guards only; no shared-tab leader election, server session command queue, or browser BroadcastChannel coordination found. |

## 6. Risks Not Yet Reproduced

Static audit did not execute destructive or semi-destructive game operations. The following require isolated fixture runtime testing:

- Exact p50/p95/p99 durations for `/api/runtime-state`, `/api/state`, `/api/event-trigger`, `/api/score`, and `/sponsor-ad-files/*`.
- Whether Flask/Werkzeug honors Range for sponsor ad files under current Waitress deployment.
- How OBS CEF requests MP4 files in this setup: single request, Range bursts, retries, concurrent preview/program requests.
- Whether production-theme runtime plus legacy overlay are both active in the actual OBS scene and therefore double-polling.
- Whether Facebook incident was true A/V desync or stale graphics inside current video.

## 7. Waitress Request/Worker Analysis

Current production server: 16 Waitress threads at `app.py:3060`.

A 16-thread pool can sustain the normal polling model only if all read routes are consistently fast and no media requests occupy threads. It is not safe if any of the following occur:

- MP4 route holds 1-4 workers for multi-second transfers or Range bursts.
- Google Drive sync blocks or slows state JSON writes/snapshots.
- `/api/state` or `/api/runtime-state` rebuilds are expensive under large state.
- Several browser tabs or previews are left open.
- Captions preview is open at 250 ms polling.
- OBS browser source and Command Center preview request the same sponsor media simultaneously.

Increasing threads may reduce symptoms but does not fix correctness. Duplicate commands and stale overlay remain even with more threads.

## 8. State Architecture Map

Authoritative persisted state appears to be `state.json` through `STATE_REPOSITORY`, normalized by `StateService` and loaded via `load_state()`.

Flow:

operator click -> `templates/index.html` JS -> `fetch()` -> Flask route -> service -> `load_state()` -> in-process lock for most mutations -> mutate full state dict -> `save_state()` -> `StateService.save()` -> `StateRepository.replace()` -> `JsonPersistenceEngine.save()` -> linked broadcast snapshot write -> mutation response -> `currentState` render -> later `/api/runtime-state` polls -> overlay/production runtime render -> OBS browser source -> OBS program -> Facebook.

Staleness points:

- Client-side `currentState` can be optimistic (`setStateFrom`, `setState`).
- Polling snapshots can arrive after mutation responses and merge without true revision comparison.
- `/api/runtime-state` omits bulky collections, so Command Center preserves older full-state fields while replacing live fields.
- Overlay retains last DOM on fetch failure.
- Production-theme runtime may skip render when signature unchanged, patching only some fields.
- Facebook transport latency is separate from CSRN overlay freshness.

## 9. Mutation Flow Map

| Action | Route | Method | Response | Duplicate safety |
|---|---|---|---|---|
| Direct score `-1/+1/+2/+3/+6` | `/api/score` | POST | full state | none; every click mutates |
| Set possession/down/distance/quarter/visibility | `/api/set` | POST | full state | none; optimistic UI for some paths |
| TD/FG/XP/2PT/turnover/first down/penalty/ejection/kickoff | `/api/event-trigger` | POST | `{state, trigger, message}` | none; every accepted request appends event/play |
| Detailed statistician play | `/api/rules-play` | POST | `{state, play}` | none; every accepted request appends event/play |
| Quick correction | `/api/game-correction` | POST | full state | no command id; logs correction |
| Clock controls | `/api/clock-control` | POST | full state | no command id; repeated adjust/start/stop all accepted |
| Field direction | `/api/field-direction` | POST | full state | no command id |
| Undo/restore | `/api/undo`, `/api/restore` | POST | full state | no frontend pending guard; restore has server availability checks |
| Sponsor/player/highlight/personnel graphics | `/api/graphics/*` | POST | public state | no command id; uses lock |
| Sponsor ad media | `/sponsor-ad-files/<filename>` | GET | media | no app-level Range/media isolation |

## 10. Polling Inventory

Critical aggregate findings:

- 1 Command Center + 1 OBS overlay + 1 statistician phone likely produces at least 3 runtime-state consumers. If production theme runtime is active inside `/overlay`, OBS may issue both legacy overlay and production runtime state requests.
- Captions preview adds 4 requests/sec by itself.
- Fixed `setInterval` in captions/weather can overlap if server is slow because no in-flight guard exists (`templates/captions.html:143-154`, `templates/weather.html:99-106`).
- Overlay and Command Center use in-flight guards for state polling, which is good, but they silently swallow failures.

## 11. Live Mutation Safety Matrix

| Action group | Route | Can double-submit? | Unique op ID? | Server idempotent? | Pending UI? | Uses response? | Risk |
|---|---|---:|---:|---:|---:|---:|---|
| Direct score | `/api/score` | yes | no | no | no | yes | P0 |
| TD/FG/XP/2PT/turnover | `/api/event-trigger` | yes | no | no | weak modal text only | yes | P0 |
| First down | `/api/event-trigger` | yes | no | no | no | yes | P0 |
| Penalty | `/api/event-trigger` | yes | no | no | weak modal message | yes | P1/P0 if scoring/stat impact |
| Detailed play | `/api/rules-play` | yes | no | no | no | yes | P0 |
| Possession/down/distance/quarter | `/api/set` | yes | no | no | optimistic | yes | P1 |
| Field position slider/click | `/api/game-correction` | yes | no | no | no | response then full refresh | P1 |
| Clock adjust | `/api/clock-control` | yes | no | no | no | yes | P1 |
| Halftime/period/final | `/api/toggle-halftime`, `/api/set` | yes | no | no | no | yes | P1 |
| Kickoff quick | `/api/event-trigger` | yes | no | no | no | yes | P1 |
| Undo | `/api/undo` | yes | no | partially history-based | no | response then refresh | P1 |
| Restore | `/api/restore` | yes | no | server checks availability | disabled only when unavailable | response then refresh | P2 |
| Sponsor/program visual actions | `/api/graphics/*`, `/api/obs/*` | yes | no | no | mixed | yes | P2/P1 |
| Broadcaster takeover | `/api/control-source` | yes | no | no | no | yes | P1 during pending commands |

## 12. Mobile Statistician Audit

Phone-size CSS exists for score grid/statistician controls (`templates/index.html:59`, `templates/index.html:6240`), and touch targets are generally 42-44 px in some mobile rules. However, production safety states are missing.

The statistician cannot reliably distinguish READY, SUBMITTING, ACCEPTED, COMMITTED, FAILED, RECONNECTING, and STALE. There is no per-command pending ledger, no stale-state banner tied to last successful poll, and no degraded-server warning before more controls are pressed. Buttons can retain active availability while requests are unresolved. Multiple pending mutations are possible from repeat taps or multiple tabs/clients.

Conclusion: mobile statistician workflow is currently unsafe for another live game.

## 13. Command Center Audit

Strengths:

- Startup gets one full `/api/state`, then uses lightweight `/api/runtime-state`.
- Command Center state polling has an in-flight guard and timeout: `templates/index.html:4143-4163`.
- Many mutations now use the authoritative mutation response instead of immediately fetching full state: `templates/index.html:2525-2541`.

Defects:

- No shared mutation pending guard.
- No command ID or revision rejection.
- Poll failures are swallowed (`templates/index.html:4157-4158`).
- `GameStateManager.refresh()` silently retains last state on error (`templates/index.html:2525-2528`).
- Some controls use optimistic UI before commit (`templates/index.html:2546-2551`, `templates/index.html:2981-2983`), while others wait, so operator feedback is inconsistent.
- Navigation/module switching does not appear to create duplicate state polling loops in the inspected path, but additional module-specific pollers exist, such as caption runtime polling, security polling, and OBS/status actions.

## 14. OBS Overlay Audit

Legacy overlay:

- `/api/runtime-state` poll: 500 ms normal, 2 s abort, no overlap, backoff to 5 s, silent failure. Evidence: `templates/overlay.html:218-223`.
- Theme revision poll: `/api/themes/public-state` every 2 s, silent catch. Evidence: `templates/overlay.html:156-174`.
- Local clock interpolation every 250 ms. Evidence: `templates/overlay.html:217`.
- Sponsor video playback is driven directly by state and media URL. Evidence: `templates/overlay.html:220`.

Production theme runtime:

- Fetches theme state, runtime state, and caption state; then does potentially heavy render/media preparation. Evidence: `static/csrn-production-theme-runtime.js:2388-2577`.
- Poll delay is 300-900 ms under normal conditions, 1500 ms on error.
- No operator-visible stale state watchdog.

Overlay needs an operator-facing stale-state watchdog and revision-aware response handling.

## 15. Sponsor Video / Media Serving Audit

Confirmed route: `/sponsor-ad-files/<filename>` in `routes/asset_routes.py:267-269`.

Confirmed storage selection: placement `sponsor_advertisement_video` maps to `SponsorAdvertisements` and `/sponsor-ad-files/` in `routes/asset_routes.py:29-36`.

Confirmed playback paths:

- Legacy overlay uses `sponsorSpotlightVideo.src = spotlightUrl`, `.load()`, `.play()`; `preload="metadata"` in markup. Evidence: `templates/overlay.html:133-134`, `templates/overlay.html:220`.
- Production theme runtime creates sponsor video with `preload="auto"`, autoplay, muted, no controls. Evidence: `static/csrn-production-theme-runtime.js:2131-2148`.

Risk mechanism:

OBS Browser Source/CEF may request video bytes through Waitress. Large video transfer, Range request bursts, replay/restart, or simultaneous Command Center preview plus OBS source can occupy Waitress workers. Those workers are the same pool serving live commands and state polls.

Recommendation: isolate media delivery before next live game. The safest immediate design is OBS-local media path or separate static server/reverse proxy with tested Range support. Keep Flask/Waitress for control JSON, not MP4 delivery.

## 16. Event and Score Integrity Audit

- Event mutations update both score and event/play history for scoring events. Evidence: `event_service.py:259-274`, `event_service.py:598-600`.
- Detailed play engine derives scoring from field result and appends event/play. Evidence: `rules_service.py:520-798`.
- Direct score corrections do not append event/correction records. Evidence: `game_operations_service.py:125-145`.
- Undo rebuilds canonical state from remaining events/plays and snapshots. Evidence: `event_service.py:849-920`.
- Restore has server-side availability checks. Evidence: `event_service.py:922-959`.
- Event IDs are timestamp-based (`EV-{timestamp_ms}`) in event service and timestamp plus play number in rules service. Evidence: `event_service.py:533-535`, `rules_service.py:599-600`. Under the global lock, collision is unlikely in one process but not formally impossible across processes or restored/replayed commands.

Most dangerous integrity defect: no exactly-once command semantics for scoring/event mutations.

## 17. Concurrency / Race Condition Audit

Confirmed protections:

- Most live mutation services receive `transaction_lock=lock` from `app.py:2043`, `app.py:2070`, `app.py:2109`, `app.py:2962`, `app.py:3009`.
- The lock is `threading.Lock()` at `app.py:258`.
- `JsonPersistenceEngine` has its own `RLock` for JSON operations (`persistence_engine.py:44-48`).

Remaining gaps:

- Lock is in-process only. Multiple Waitress processes are not configured here, but any future multi-process deployment would not be protected.
- No optimistic concurrency/version check exists for clients.
- Full-state read/modify/write remains the mutation model.
- Linked broadcast snapshot writes update separate files after state normalization.
- Read caches are TTL-based and not explicitly invalidated on mutation.

## 18. Error Handling / Silent Failure Audit

Notable silent or weak error handling:

- Overlay theme poll catches and discards all errors: `templates/overlay.html:171`.
- Overlay runtime poll increments failure count but gives no operator-visible stale signal: `templates/overlay.html:223`.
- Command Center state poll catches and discards details: `templates/index.html:4157-4158`.
- Command Center full-state refresh retains old state silently: `templates/index.html:2525-2528`.
- Social draft creation after event is swallowed: `event_service.py:603-608`.
- Captions preview hides captions on any refresh error: `templates/captions.html:143-154`.
- Weather overlay catches and ignores errors: `templates/weather.html:99-106`.
- Production theme runtime logs to console and deactivates binding, but not to operator UI: `static/csrn-production-theme-runtime.js:2548-2558`.

## 19. Performance Findings

Primary request-cost concerns:

- Synchronous state writes include JSON serialization, fsync, backup copy, backup pruning, and linked broadcast writes.
- The app runs from `My Drive`, so Google Drive sync can add latency to file operations and lock contention outside Python's control.
- Runtime/public-state reads have 250 ms coalescing cache, which helps but can also return briefly stale state after a mutation if not invalidated.
- Media delivery through Flask is the highest-risk worker occupancy path.
- Multiple overlays/previews/tabs can multiply load without a shared browser/session leader.

Thread count alone is not a sufficient repair. Correctness must be fixed first, then media isolation and observability, then thread/request tuning.

## 20. Reproduction Results

No destructive reproduction was run against current production data. Python execution from the local venv was denied in the audit shell, so no pytest or live Flask test server was started.

Designed non-destructive test plan:

1. Fixture broadcast idle: measure `/api/runtime-state` p50/p95/p99 with one client.
2. Command Center + overlay: measure request rate and convergence T2/T3.
3. Command Center + overlay + statistician phone equivalent: measure request rate and mutation ack latency.
4. Rapid touchdown double click: send same command twice without command ID; assert current build records two events, repaired build records one.
5. Delayed touchdown response followed by second click: inject server delay before response but after commit.
6. Rapid `-1` score correction: assert current build decrements multiple times.
7. Artificial server latency around persistence and media route.
8. Two simultaneous score mutations from two clients.
9. Authority switch during pending statistician request.
10. Runtime-state request delayed beyond poll interval.
11. Runtime-state timeout and overlay stale display duration.
12. Several consecutive overlay polling failures.
13. Sponsor video playing while runtime-state is polled.
14. Sponsor video plus Command Center plus statistician polling.
15. Sponsor replay/restart and Range request capture.
16. Multiple browser tabs accidentally open.
17. Client disconnect/reconnect.
18. Requests resolving out of order.
19. Successful server mutation followed by lost HTTP response.
20. Repeated identical event request.

Required instrumentation:

- T0 operator press timestamp and spoken phrase.
- T1 server commit timestamp in mutation transaction.
- T2 Command Center DOM render timestamp for new revision.
- T3 OBS overlay DOM render timestamp for new revision.
- T4 external stream visible timestamp.
- request ID, command ID, route, thread, status, duration, client/session, state revision before/after, and media request byte/range metadata.

## 21. P0/P1/P2/P3 Findings Table

| ID | Severity | Finding | Status |
|---|---|---|---|
| F1 | P0 | Score/event/play mutations lack idempotency and exactly-once semantics | Confirmed |
| F2 | P0 | Live controls remain usable without consistent pending/committed/failed states | Confirmed |
| F3 | P0 | Direct score and event/stat history can disagree | Confirmed |
| F4 | P1 | Sponsor ad media is served through Waitress and can starve control traffic | Confirmed capability, inferred live contribution |
| F5 | P1 | Overlay can silently show stale state | Confirmed |
| F6 | P1 | Runtime `revision` is not a true monotonic state revision | Confirmed |
| F7 | P1 | Synchronous JSON/backup/linked snapshot writes are in request path | Confirmed |
| F8 | P1 | High-frequency pollers share the same constrained worker pool | Confirmed |
| F9 | P1 | Google Drive synchronized runtime storage likely worsens latency | Inferred |
| F10 | P1 | Facebook graphics-behind-audio likely can be stale CSRN overlay rather than platform latency | Inferred |
| F11 | P2 | Poll failures are swallowed across multiple pages | Confirmed |
| F12 | P2 | Multiple browser tabs multiply polling and command risk | Confirmed capability |
| F13 | P2 | In-process lock would not protect multi-process deployment | Confirmed architectural limit |
| F14 | P3 | Current source-of-truth docs are stale relative to current branch/status | Confirmed |

## 22. Recommended Repair Architecture

Minimum justified architecture:

- One authoritative live state with transactional `state_revision` incremented on every committed mutation.
- Every live command carries `command_id`, `client_id`, `issued_at`, `expected_revision`, and action payload.
- Server persists command results in a bounded per-broadcast idempotency ledger.
- Duplicate `command_id` returns original result without re-mutating.
- Server responses include `{command_id, command_status, state_revision, state, committed_at}`.
- Clients disable or mark relevant controls pending immediately at T0.
- Clients use mutation response for immediate authoritative paint and reject polling snapshots older than current revision.
- Overlay tracks `overlay_last_success`, `overlay_last_revision`, and stale age.
- Command Center exposes operator-only health: server latency, state age, overlay revision age, poll failures, and media route warnings.
- Media delivery is separated from game-control Waitress workers.
- Live state persistence is optimized for local low-latency writes; Drive archival is asynchronous or postgame.

## 23. Recommended Repair Order

1. Add live command model: `command_id`, idempotency ledger, mutation response contract, and tests for duplicated score/event/play commands.
2. Add transactional monotonic `state_revision` to all state writes and read endpoints.
3. Add frontend `CommandClient` pending-state manager for all live mutation controls, including mobile/statistician controls.
4. Add stale-client and stale-overlay detection using revisions and timestamps.
5. Isolate sponsor/player video media from Flask/Waitress control server.
6. Add request/worker instrumentation and queue-health dashboard.
7. Move linked broadcast snapshots/Drive sync out of mutation critical path or batch them safely.
8. Rationalize polling intervals and remove fixed-overlap `setInterval` pollers or add guards.
9. Add full live rehearsal tests with T0-T4 timing separation.
10. Update Project Bible and operator docs after code is repaired and verified.

## 24. Required Automated Regression Tests

- `test_score_command_id_idempotent_under_duplicate_post`
- `test_touchdown_command_id_idempotent_under_duplicate_post`
- `test_rules_play_command_id_idempotent_under_duplicate_post`
- `test_duplicate_command_returns_original_state_revision`
- `test_expected_revision_rejects_or_sequences_stale_command`
- `test_mutation_response_contains_command_status_and_state_revision`
- `test_runtime_state_revision_increments_for_direct_score`
- `test_overlay_rejects_older_revision`
- `test_command_center_rejects_older_poll_after_mutation_response`
- `test_sponsor_video_route_not_served_by_control_app` or equivalent deployment contract
- `test_poll_failure_sets_stale_health_state`
- `test_mobile_controls_disable_while_command_pending`
- `test_lost_response_retry_with_same_command_id_does_not_duplicate`
- `test_two_clients_simultaneous_score_commands_are_ordered`

## 25. Required Live-Rehearsal Tests

Run only on fixture/practice broadcast data:

- T0-T4 touchdown timing with spoken phrase "TEST TOUCHDOWN NOW".
- T0-T4 direct score correction timing.
- OBS preview vs Facebook audio/video comparison.
- Sponsor ad playback while Command Center/statistician/overlay poll.
- Sponsor replay/restart with request logs and Waitress queue observation.
- Multiple browser tabs open accidentally.
- Wi-Fi/phone disconnect and reconnect during pending mutation.
- Authority switch while statistician command is pending.
- Runtime-state endpoint artificial 3/6/10 second delays.
- Overlay network failure for 5, 15, and 30 seconds, verifying operator stale warning.

## 26. Exact Files / Functions / Routes Implicated

| Finding | File/location |
|---|---|
| Direct score duplicates | `templates/index.html:328-340`, `templates/index.html:2883-2890`, `routes/live_game_routes.py:32-42`, `game_operations_service.py:100-145` |
| Event duplicates | `templates/index.html:2961-2969`, `routes/live_game_routes.py:73-85`, `event_service.py:136-618` |
| Detailed play duplicates | `templates/index.html:2649`, `routes/live_game_routes.py:173-185`, `rules_service.py:203-805` |
| Missing pending UI | `templates/index.html:2525-2541`, `templates/index.html:2883-2890`, `templates/index.html:2961-2969` |
| Runtime revision weakness | `state_service.py:291-337` |
| Runtime/public state endpoints | `routes/system_routes.py:61-70`, `app.py:1711-1722` |
| Read caches | `state_read_cache.py`, `runtime_state_cache.py`, `app.py:3037-3043` |
| Synchronous persistence | `persistence_engine.py:80-123`, `persistence_engine.py:208-228`, `state_service.py:143-152`, `app.py:1647-1668` |
| Sponsor ad media | `routes/asset_routes.py:29-36`, `routes/asset_routes.py:267-269`, `templates/overlay.html:220`, `static/csrn-production-theme-runtime.js:2131-2148` |
| Overlay stale behavior | `templates/overlay.html:156-174`, `templates/overlay.html:218-223`, `static/csrn-production-theme-runtime.js:2388-2577` |
| Polling pressure | `templates/index.html:4143-4163`, `templates/index.html:5965-5979`, `templates/captions.html:143-154`, `templates/weather.html:99-106`, `static/csrn-production-theme-runtime.js:2564-2577` |
| Authority race risk | `routes/live_game_routes.py:62-71`, `event_service.py:120-134`, `templates/index.html:2543` |
| Undo/restore | `templates/index.html:3226-3235`, `event_service.py:849-959` |
| Waitress config | `app.py:3049-3060` |

## Required Incident Answers

1. What is the single authoritative live game state? The active state object loaded/saved through `STATE_REPOSITORY` and `StateService`, persisted to `state.json`. However, linked broadcast snapshots create secondary copies and direct score/event history are not fully reconciled.
2. How quickly should Command Center, statistician console, and OBS converge after a mutation? After repair, Command Center should paint the mutation response immediately and OBS should poll/render within one normal interval, target under 1 second for local OBS absent media/CPU load.
3. Can a successful mutation presently execute more than once because the operator clicks again? Yes, confirmed.
4. Can two clients overwrite each other's state? The in-process lock serializes most mutations, but without expected revisions, later commands can validly apply stale intent. Future multi-process would be unsafe.
5. Can requests execute out of order? Server lock serializes arrival order, but clients have no sequencing contract and polling/mutation responses can be observed out of order.
6. Can the UI display stale state without warning? Yes, confirmed.
7. Can an operator currently determine whether a command is pending? Not reliably.
8. Can the sponsor-video route consume enough Waitress capacity to delay game-state traffic? Yes, capability confirmed.
9. Are media delivery and game-control traffic improperly sharing the same constrained worker pool? Yes.
10. Is Google Drive synchronized runtime storage contributing materially to request latency? Plausible/probable, not measured.
11. Are there multiple sources of truth for score or game state? There is one persisted active state, but score also exists as event-derived history and linked broadcast snapshots, so practical divergence is possible.
12. Can the event history and score disagree? Yes, confirmed via direct score correction and duplicate events.
13. Can OBS be displaying an older state than Command Center without either side identifying that condition? Yes.
14. What specifically caused or could cause the live behavior observed? Confirmed duplicate-command design plus latency; probable Waitress queue from shared polling/media/persistence load, with sponsor video as a likely contributor.

## Final Audit Conclusions

Top 10 findings:

1. P0 confirmed: live score/event/play mutations lack idempotency.
2. P0 confirmed: live controls do not disable or show reliable pending/committed/failed states.
3. P0 confirmed: direct score and event/stat history can diverge.
4. P1 confirmed capability: sponsor ad video is served through Waitress and can starve control traffic.
5. P1 confirmed: overlay can silently display stale state.
6. P1 confirmed: runtime `revision` is not a true monotonic state revision.
7. P1 confirmed: synchronous JSON persistence and linked snapshots run in request threads.
8. P1 confirmed: high-frequency pollers share the same worker pool as mutations and media.
9. P1 inferred: Google Drive synchronization likely worsens p95/p99 latency.
10. P1 inferred: Facebook graphics-behind-audio may have been stale CSRN graphics, not normal platform latency.

Single most likely cause of live Waitress queue buildup: sponsor/media delivery and high-frequency polling sharing the 16-thread Waitress pool, worsened by synchronous Google Drive-backed JSON persistence. Sponsor video is the most suspicious individual trigger because MP4 bytes are served by Flask/Waitress.

Single most dangerous data-integrity defect: no server-side idempotency/exactly-once semantics for scoring and event commands.

Sponsor advertisement contribution: confirmed capable and likely contributory, not proven as sole cause without live request logs.

Mobile statistician safety: not safe for another live game in current form.

Recommended repair order: command idempotency, state revision, frontend pending states, stale overlay/client detection, media isolation, observability, persistence decoupling, polling rationalization, live rehearsal.

---

## 15. Supplemental OBS Log Audit - 2026-08-21 Logs

Inputs reviewed after the initial audit:

- OBS log beginning `2026-08-21 11:38:57`, provided as pasted text.
- OBS log beginning `2026-08-21 17:05:26`, provided as pasted text.

### OBS Finding 1 - Confirmed Scorebug Browser Source Fetch Failure

Severity: P0/P1, depending on whether this overlapped live scoring operations.

The `17:05:26` OBS log confirms repeated OBS browser-source JavaScript failures from the CSRN scorebug source:

- Source: `BRWSR - Football Scorebug`.
- Error: `[CSRN Gate 16.9 R2] production theme binding blocked: TypeError: Failed to fetch`.
- URL: `http://127.0.0.1:5050/static/csrn-production-theme-runtime.js?v=19.6-r18-r5-caption-sticky:2549`.
- Observed repeatedly from `17:33:35.619` through `17:34:49.520`.

Audit conclusion update: this materially strengthens the stale-overlay hypothesis. The Facebook symptom described as audio only slightly behind while graphics were further behind is now more likely to involve the local CSRN OBS browser source failing to fetch/update overlay state, rather than being explained solely by Facebook ingest/player A/V latency.

This is also consistent with the earlier application audit: overlay polling/fetch failures can degrade silently, and the operator has no strong stale-state indicator in the OBS output.

### OBS Finding 2 - No Strong Encoder Overload Evidence In The Pasted Logs

The pasted OBS logs do not show a clear `encoder overloaded`, stream reconnect, or network drop signature in the searched content. The second log contains a short recording window:

- Recording started at `17:41:17.275`.
- Recording stopped at `17:41:29.829`.
- Total frames output: `364`.
- Total drawn frames: `377`.

Profiler data from the second log shows GPU encode thread health looked acceptable during the captured interval:

- `obs_gpu_encode_thread`: median `0.984 ms`, 99th percentile `3.293 ms`, `100% below 33.333 ms`.
- `render_video`: median `0.078 ms`, 99th percentile `0.541 ms`.

There are large max values in OBS profiler buckets, but the 99th percentiles are low. Those max values are not enough by themselves to prove sustained encoder or renderer overload during the incident.

Audit conclusion update: OBS logs currently support local browser-source/app fetch failure more strongly than GPU encoder overload.

### OBS Finding 3 - Recurrent ZOOM P4next ASIO Device Loss/Recovery

Both logs show repeated `ZOOM P4next ASIO Driver` availability failures and recoveries.

Examples:

- In the `11:38:57` log, the device is opened at startup, then many `failed to open device "ZOOM P4next ASIO Driver": No device` entries appear across the session, followed by recoveries.
- In the `17:05:26` log, startup initially fails to open/register the ZOOM device, it recovers at `17:28:42.528`, then later fails and recovers again around `17:44:16.772` and `18:01:31.695`.

Audit conclusion update: this is a separate production reliability concern for audio capture stability. It does not directly explain graphics being behind audio, but it should be treated as a game-day readiness risk because the audio chain can disappear and recover mid-session.

### OBS Finding 4 - Browser Hardware Acceleration, HAGS, and Environment Notes

Both logs show:

- OBS 32.2.2 on Windows 10/11 build 26200.
- Browser Hardware Acceleration enabled.
- NVIDIA RTX 4050 Laptop GPU selected for D3D11.
- Hardware-Accelerated GPU Scheduling enabled.
- OBS not running as administrator; D3D11 GPU priority setup failed with `not admin?`.
- Game DVR enabled and Game Mode probably enabled.
- `obs-multi-rtmp` plugin loaded with one target.
- `atkAudio` plugin loaded.

These are not proven root causes. They are operational variables to pin down during the next rehearsal so a future failure can be compared against a stable baseline.

### Revised Root-Cause Weighting After OBS Logs

1. Confirmed and now highest-confidence for the graphics-lag symptom: CSRN OBS scorebug browser source failed repeated fetches from localhost, causing stale or blocked overlay updates.
2. Still confirmed from application audit: Waitress serves live API, static/runtime JS, and sponsor/media routes from the same process/thread pool, so fetch failures may be downstream of local server saturation or request-path blocking.
3. Still likely contributory: sponsor/media traffic and high-frequency polling can starve live control and overlay fetches, especially when combined with synchronous JSON/Drive-backed persistence.
4. Less supported by these logs: sustained OBS GPU encoder overload or Facebook-only A/V latency as the primary explanation.
5. Separate reliability risk: ASIO device instability in the ZOOM P4next audio path.

### Added Verification Requirement

During the T0-T4 rehearsal, OBS must be included in instrumentation:

- Capture OBS log timestamps while exercising score changes, statistician events, sponsor video playback, and overlay updates.
- Add an on-overlay visible stale indicator tied to last successful state/runtime fetch time.
- Record local screen output and Facebook output at the same time.
- Compare command click time, server receive time, state commit time, OBS fetch success time, OBS visual update time, and Facebook visible time.
- Treat any OBS browser-source `Failed to fetch` burst as a failed rehearsal, even if audio and encoder metrics look normal.
