# CSRN Production Suite Roadmap

## Current stage — Release-candidate integration and evidence

The operational Google Drive build is `1.13.0-alpha.8e`. Broad football functionality and several commercial-facing engines are implemented, but the formal Phase 6.6 operational rehearsal and release-freeze gate is not complete.

## Completed or substantially implemented

- football scorebug and Command Center;
- event, roster, personnel, statistics, sponsor, asset, and graphics foundations;
- safety snapshots, recovery foundations, diagnostics, and OBS integration;
- theme engine foundation;
- social publishing foundation with assisted-manual X only;
- grounded recap and deterministic article generation;
- responsive cross-page navigation and football readiness reporting.

## Removed from scope

- dedicated Chromebook/PWA product track;
- automated X posting;
- hosted AI;
- local AI.

Browser-capable devices remain supported as remote clients without a separate Chromebook product.

## Now

1. Align the exact Drive `alpha.8e` tree with GitHub.
2. Audit fixture identity and expand both test rosters to 22 players.
3. Run the release-candidate test process in `docs/FOOTBALL_RC_TEST_PROCESS.md`.
4. Correct blocking defects only.
5. Complete two software-only rehearsals.
6. Configure P4next and commission hardware/OBS.
7. Complete the formal Phase 6.6 rehearsals and recovery series.
8. Freeze the exact tested commit.

## After game-day release freeze

- commercial installer/uninstaller and stable customer data location;
- licensing and entitlement hardening;
- customer-safe support and update channels;
- Mac host edition after Windows stability;
- other sports after football release evidence is complete.
