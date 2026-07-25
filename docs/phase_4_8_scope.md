# Phase 4.8 — Broadcast Service

Phase 4.8 extracts broadcast planning and record-lifecycle behavior from Flask into a testable `BroadcastService` boundary.

## Included

- Permanent broadcast ID generation
- Broadcast schedule listing and record lookup
- Planned broadcast creation
- Broadcast record updates and active-state synchronization
- Planned/live/completed status changes
- Linked broadcast lifecycle updates used by live operation
- Reopening completed broadcast records
- Broadcast deletion, detail-file cleanup, and active-state reset
- Branding fallback warnings
- Existing API response-contract preservation

## Retained at the Flask boundary

- Authentication
- Request parsing and HTTP status selection
- OBS commands
- Active live-game state construction and overlay behavior
- Readiness checks
- Physical detail-file location wiring through injected callbacks

## Completion target

- Runtime version: `1.13.0-alpha.4h`
- Runtime label: `Broadcast Service`
- Cross-platform validation on Ubuntu and Windows
