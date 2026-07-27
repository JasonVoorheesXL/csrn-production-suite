# Phase 6.10 — Commercial UX, Navigation, and Account Onboarding

## Purpose

Phase 6.10 converts completed CSRN engines from discoverable-by-URL developer features into a customer-facing product workflow. The phase does not remove advanced configuration. It places normal setup in a guided hub and moves technical free-text values behind clearly labeled advanced settings.

## Setup & Integrations hub

Authenticated operators can open `/setup` from the Command Center navigation. The hub provides:

- launch-readiness progress;
- plain-language setup checks;
- a controlled graphics-theme selector;
- consumer-style social-account connection controls;
- a directory of every customer-facing product area;
- visible return paths to Command Center and Advanced Settings;
- responsive layouts for desktop, laptop, tablet, and phone widths.

The Command Center supports query-based module links such as `/?module=obs`, so the setup directory can take an operator to the requested module rather than requiring them to locate it manually.

## Controlled selections

The main Settings page no longer accepts an arbitrary theme name. It offers the eight registered Phase 6.8 presets and directs the operator to the visual theme gallery for previews. This pattern is now a permanent product requirement: whenever CSRN already knows the valid choices, the normal customer workflow must use a selector, card gallery, detected-device list, or searchable picker rather than an internal-name text field.

Advanced/custom text entry may remain for unusual installations, but it must be labeled as advanced and may not be the default path.

## Social account onboarding

### X

The X connection uses OAuth 2.0 Authorization Code with PKCE. The authorization request uses a random state value, an S256 code challenge, and only the scopes required by the publishing workflow:

- `tweet.read`
- `tweet.write`
- `users.read`
- `media.write`
- `offline.access`

The customer clicks **Connect X**, signs in with X, grants the requested permissions, and returns to CSRN. Access and refresh tokens are written only to the protected credential vault. The Social Publishing queue receives a `vault:` reference and never receives a raw token.

A PossumFrog X developer application still must be registered and its public client ID supplied as `CSRN_X_CLIENT_ID` before the button can initiate live authorization.

### Facebook Pages

Facebook Page onboarding uses a PossumFrog OAuth broker. Meta application secrets must not be embedded in or distributed with the Windows desktop application. The desktop app sends the customer to the configured broker, receives a short-lived broker exchange code, and stores only the selected Page token in the protected local vault.

The broker base URL is configured as `CSRN_META_OAUTH_BROKER_URL`. Until the commercial Meta application and broker exist, the Setup hub shows **Setup required** instead of asking the customer to copy Page tokens.

## Protected credential storage

Production Windows builds use the current Windows user’s Data Protection API (DPAPI):

- `CryptProtectData` protects credential values;
- `CryptUnprotectData` restores them only for the same Windows user context;
- the disk file contains encrypted blobs and safe reference names;
- support bundles, route responses, setup status, Social Publishing state, and audit records do not expose credential values.

The in-memory vault exists only for automated tests.

## Connection lifecycle

Each provider card reports:

- provider application configured or setup required;
- protected vault available or unavailable;
- connected account identity;
- last connection-test status;
- Connect, Test Connection, and Disconnect actions.

Disconnect requires the exact confirmation phrase `DISCONNECT SOCIAL ACCOUNT` and removes protected credential material from the vault.

## Product-wide usability requirements

Before commercial launch, every customer-facing feature must meet these guardrails:

1. Reachable from Command Center or Setup & Integrations.
2. Standalone pages include a visible return path.
3. Known values use controlled selectors rather than guessed internal identifiers.
4. Technical settings are separated from normal setup.
5. Required fields include validation and plain-language errors.
6. Save, test, connect, reconnect, and disconnect actions report clear results.
7. Unsaved changes are guarded where data loss is possible.
8. Keyboard navigation and responsive layout are preserved.
9. Customer names, real schools, personal names, and local credentials are not shipped as commercial defaults.
10. Upgrades preserve customer data and do not overwrite local configuration.

## Deferred work

Phase 6.10 establishes the desktop OAuth flows and commercial UX boundary. Live account connection still depends on external provider registrations:

- PossumFrog X developer application;
- PossumFrog Meta application;
- PossumFrog Meta OAuth broker and secure server-side secret storage;
- provider review or approval where required;
- production callback URL registration and operational monitoring.

Phase 6.11 remains the Grounded Game Recap Engine. The future fictional demo teams and illustrated sample rosters will be handled as commercial demo-data work and will not replace customer-created data.
