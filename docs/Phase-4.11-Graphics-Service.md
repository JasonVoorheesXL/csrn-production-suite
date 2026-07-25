# Phase 4.11 — Graphics Service

## Scope

Phase 4.11 extracts primary identification graphic behavior from Flask into `GraphicsService`.

The service owns:

- Lower-third field updates, visibility, duration, and expiration.
- Player graphic roster and school identity enrichment.
- Personnel graphic identity enrichment.
- Sponsor metadata application and warning propagation.
- Mutual exclusivity between lower-third, player, and personnel channels.
- Automated timed player graphics used by event workflows.
- Shared player-display and position normalization rules.

Flask retains:

- Authentication.
- Request and response translation.
- The application state lock.
- State persistence.
- Overlay-safe response filtering.

## Compatibility

The existing routes remain unchanged:

- `POST /api/graphics/lower-third`
- `POST /api/graphics/player`
- `POST /api/graphics/personnel`

The existing helper names used by the event engine remain available as wrappers around `GraphicsService`.

## Runtime identity

Completion target:

- Version: `1.13.0-alpha.4k`
- Title: `Graphics Service`
- Build: `V1.13A4K-GRAPHICS-SERVICE`
