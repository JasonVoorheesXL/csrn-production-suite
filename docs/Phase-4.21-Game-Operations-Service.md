# Phase 4.21 — Game Operations Service

Phase 4.21 extracts the remaining live game-operation routes from `app.py` into a Flask-independent `GameOperationsService`.

## Service responsibilities

- Manual score adjustments with broadcaster/statistician authority enforcement
- Allowed game and ticker field updates
- Scorebug visibility changes with optional OBS command coordination
- Halftime entry and third-quarter resume
- Final-game lifecycle and final-score persistence
- Operational data reset while retaining the selected broadcast identity
- Complete new-broadcast state reset
- Undo-history snapshots for mutable live operations

## Preserved route contracts

- `POST /api/score`
- `POST /api/set`
- `POST /api/toggle-scorebug`
- `POST /api/toggle-halftime`
- `POST /api/end-game`
- `POST /api/reset-data`
- `POST /api/new-broadcast`

## Runtime identity

- Version: `1.13.0-alpha.4u`
- Feature: `Game Operations Service`
- Build: `V1.13A4U-GAME-OPERATIONS-SERVICE`
