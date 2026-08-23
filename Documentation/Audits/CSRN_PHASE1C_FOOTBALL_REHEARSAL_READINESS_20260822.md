# CSRN Phase 1C Football Rehearsal Readiness

Date: 2026-08-22

Status: COMPLETE FOR PHASE 1C ONLY

Rollback snapshot: `work\phase1c_football_rehearsal_rollback_20260822-110707`

## Scope Boundary

Phase 1C stayed inside the approved rehearsal-readiness scope:

- Resolved the five football failures from Phase 1B validation.
- Brought coin-toss record/undo routes into the existing command safety architecture.
- Made OBS Browser Source health visible to the Command Center operator.
- Added focused regression coverage for football workflow, command safety, and OBS health visibility.

No Phase 2 work was started. This pass did not redesign media isolation, Waitress/runtime hosting, Drive persistence, polling architecture, OBS encoder settings, OBS audio, or package workflows.

## Repairs Completed

### Football Workflow

- Preserved the canonical second-half kickoff path when a second-half receiver exists.
- Added a legacy halftime-toggle fallback for older operator workflow state that resumes Q3 live at 1st and 10 when no receiver context exists.
- Corrected stale XP/2PT tests to set up `pending_try` before recording conversions.
- Updated the old R41 gate to assert the current data-integrity rule: conversions outside `pending_try` are rejected instead of silently changing score.
- Added retry/idempotency checks for halftime and conversion handling.

### Coin Toss Command Safety

- Added command metadata, state revision assignment, duplicate command replay, and recent-command ledger writes to `/api/coin-toss`.
- Added the same command-safety behavior to `/api/coin-toss/undo`.
- Routed Command Center coin-toss save/undo through `GameStateManager.mutate()` and `LiveCommandClient` command groups.
- Added pending UI selectors for coin-toss modal buttons and coin-toss undo.

### OBS Operator Health

- Added `/api/overlay-health` POST for the OBS overlay Browser Source to report real overlay telemetry.
- Added authenticated `/api/overlay-health` GET for the Command Center operator view.
- Added a Command Center OBS health indicator near the existing command health indicator.
- Integrated the health check into the existing runtime poll rhythm with a 4-second throttle.
- Added overlay reporting on success, degraded failure, stale transition, and recovery paths.

## Files Touched For Phase 1C

- `game_operations_service.py`
- `routes\coin_toss_routes.py`
- `routes\system_routes.py`
- `templates\index.html`
- `templates\overlay.html`
- `tests\test_event_service.py`
- `tests\test_gate184_r4_scoring_lifecycle.py`
- `tests\test_phase1c_football_rehearsal.py`

The repository was already dirty before this phase. Unrelated modified and untracked files were left intact.

## Validation Results

- Incident five-test repro command: 5 passed in 0.33s.
- New Phase 1C regression file: 10 passed in 0.99s.
- Touched event/game/Phase1C suite: 52 passed in 0.72s.
- Phase 1A + Phase 1B suites: 85 passed in 63.08s.
- Related service/route/cache suite: 123 passed in 3.06s.
- Football workflow suite: 79 passed in 1.01s.
- System routes + Phase1C route coverage: 21 passed in 1.20s.
- Python syntax check: passed for touched Python modules and tests.
- Command Center raw live-mutation audit: only `/api/setup-pin` remains outside command-client mutation flow.

## Rehearsal Checklist

T-4 hours:

- Start CSRN locally and authenticate Command Center.
- Open OBS and load the intended scene collection/profile.
- Confirm overlay Browser Source points at `/overlay`.
- Confirm Command Center shows OBS health as `HEALTHY` with a recent revision after overlay loads.

T-2 hours:

- Create/load the football broadcast.
- Record coin toss from the active authority console.
- Retry Save Coin Toss once during rehearsal and confirm no duplicate revision/side effect.
- Confirm kickoff possession, kicking team, receiving team, and second-half receiver.

T-60 minutes:

- Record touchdown, XP good, touchdown, 2PT failed, and undo a touchdown during rehearsal.
- Confirm each TD creates one pending try and each resolved try returns to kickoff state.
- Toggle halftime, then resume second half. If receiver context is present, verify kickoff path; if not, verify Q3 1st-and-10 fallback.

T-15 minutes:

- Watch Command Center command health and OBS health while OBS overlay is visible.
- Temporarily close/disable the OBS Browser Source during rehearsal and confirm OBS health moves degraded/stale, then recovers after reload.
- Confirm no operator controls remain disabled after command completion.

Go / No-Go:

- GO only if Phase 1A/1B/1C validation remains green, OBS health is visible and current, coin toss is recorded once, and the football pending-try workflow behaves as rehearsed.
- NO-GO if OBS health is stale without recovery, coin-toss record/undo duplicates effects, or TD/try state becomes incoherent.

## Remaining Risks

- OBS health is now visible to the operator, but this phase intentionally did not tune encoder/audio/package settings.
- The worktree contains many unrelated dirty and untracked files; only the Phase 1C surfaces above were validated here.
- `/api/overlay-health` stores last overlay telemetry in process memory. That is sufficient for operator visibility in the current local runtime, but not a persistence redesign.

STOP. Phase 1C is complete. Do not begin Phase 2 from this report.
