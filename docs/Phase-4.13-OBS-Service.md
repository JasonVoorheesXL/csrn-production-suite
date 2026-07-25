# Phase 4.13 — OBS Service

## Purpose

Move approved OBS validation and control decisions out of Flask routes while preserving the existing API and live-broadcast behavior.

## Scope

- Current OBS status retrieval
- Read-only OBS environment validation
- Controlled scorebug show/hide commands
- Controlled Program Visual graphic/camera switching
- Controlled-command safety checks
- OBS error normalization
- Shared status updates
- Atomic visual-mode history and state persistence
- Compatibility with broadcast-start scorebug automation

Physical OBS WebSocket communication remains in `obs_client.py`. Flask remains responsible for HTTP authentication and response mapping.

## Route contracts

- `GET /api/obs/status`
- `POST /api/obs/test`
- `POST /api/obs/scorebug-visibility`
- `POST /api/obs/program-visual-mode`

## Runtime identity

- Version: `1.13.0-alpha.4m`
- Build: `V1.13A4M-OBS-SERVICE`
