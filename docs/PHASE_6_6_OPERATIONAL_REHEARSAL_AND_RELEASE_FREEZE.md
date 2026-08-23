# Phase 6.6 — Operational Rehearsal and Release Freeze

Phase 6.6 establishes the evidence and approval boundary between a technically complete build and a game-day release candidate.

The software does not mark itself ready merely because automated tests pass. A release freeze requires two operator-recorded, full-length simulated broadcasts with the actual production hardware and OBS environment.

## Two-rehearsal requirement

Each completed rehearsal must cover the complete game-day workflow:

- pregame login, preflight, and safety snapshot;
- P4next isolated channels, headphone mixes, multitrack recording, and master recording;
- OBS profile, scenes, browser sources, stream test, and local recording;
- primary network path;
- channel-separated captions, correction, clear, and overlay behavior;
- venue weather monitoring and stale-data display;
- scoring, possession, clock, graphics, event history, and undo;
- halftime workflow and return to play;
- final score, postgame presentation, archive, and transcript export;
- clean application, OBS, recorder, and hardware shutdown.

A rehearsal cannot be completed until every per-rehearsal drill is marked passed with an operator note and no blocking defect remains open.

## Failure-recovery series

The following drills must each pass at least once across the two completed rehearsals:

- OBS disconnect and recovery;
- primary network loss and backup or local-recording response;
- application termination, restart, and live-state recovery;
- caption-worker loss without Command Center failure;
- weather-service failure and stale last-known data;
- mixer or USB audio disconnect and recovery;
- verified safety-snapshot restoration;
- weather-alert approval, delay screen, lightning timer, and official resumption.

The operator records the result, note, and optional evidence reference for each drill. A failed drill does not disappear; it remains part of the rehearsal record until rerun and passed.

## Blockers

Rehearsal blockers are either:

- `blocking` — prevents rehearsal completion and release freeze;
- `advisory` — retained for follow-up but does not independently block completion.

Resolving a blocker requires a written resolution. Completed rehearsals are locked from ordinary edits and must be explicitly reopened before correction.

## System gates

Even after rehearsal evidence is complete, the release freeze requires live system gates to pass:

- game-day preflight is ready;
- hardware and OBS commissioning is ready;
- no unresolved unclean-shutdown marker exists and no broadcast is live;
- at least two caption channels have unique customer-assigned speaker names rather than neutral placeholders;
- the active venue has coordinates and weather has completed a successful, non-stale refresh.

These checks are evaluated at the time readiness is requested and again at the time the release is frozen.

## Release freeze

Freezing requires:

- the exact confirmation phrase `FREEZE GAME DAY RELEASE`;
- the operator name;
- the exact tested Git commit;
- two completed rehearsals;
- all series failure drills passed;
- no open blocking defects;
- all live system gates ready.

The freeze process:

1. creates a `release-freeze` safety snapshot;
2. registers the tested commit as the known-good rollback release;
3. writes `Data/Releases/game_day_release_manifest.json`;
4. locks rehearsal modifications until the release is explicitly unfrozen.

The manifest records the version, commit, operator, rehearsal IDs, snapshot ID, system-gate evidence, failure-drill evidence, and notes.

Unfreezing requires the exact phrase `UNFREEZE GAME DAY RELEASE`, an operator name, and a written reason. Unfreezing is intended for defect correction before game day, not casual editing.

## Operator API

All endpoints require operator authentication.

- `GET /api/game-day/rehearsals`
- `GET /api/game-day/rehearsals/catalog`
- `POST /api/game-day/rehearsals`
- `PATCH /api/game-day/rehearsals/<id>/drills/<drill-key>`
- `POST /api/game-day/rehearsals/<id>/blockers`
- `PATCH /api/game-day/rehearsals/<id>/blockers/<blocker-id>`
- `POST /api/game-day/rehearsals/<id>/complete`
- `POST /api/game-day/rehearsals/<id>/reopen`
- `GET /api/game-day/release-readiness`
- `POST /api/game-day/release-freeze`
- `POST /api/game-day/release-unfreeze`
- `GET /api/game-day/release-manifest`

## Command-line report

From the repository root:

```cmd
python tools\rehearsal_report.py
```

The report prints completed rehearsal count, missing failure drills, open blockers, live system gates, and frozen-release status. It exits nonzero until the release is ready or already frozen.

## Commercial roadmap

Phase 6.6 closes the game-day release gate. Commercial work follows in this order:

- Phase 6.7 — Installer, Updates, and Licensing Foundation
- Phase 6.8 — Graphics Theme Engine
- Phase 6.9 — Social Publishing Engine
- Phase 6.10 — Grounded Game Recap Engine

The Social Publishing Engine remains a required commercial feature. It includes preview-first Facebook Page publishing and assisted-manual X packages, event graphics, player headshots, approved sponsors, weather delay/resumption posts, retries, correction history, and audit records. X does not use OAuth, developer credentials, paid API access, automatic posting, or an automatic queue.
