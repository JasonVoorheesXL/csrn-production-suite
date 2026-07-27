# Phase 6.9 — Social Publishing Engine

## Purpose

Phase 6.9 converts recorded CSRN game events into reviewable, branded social drafts and publishes approved drafts through isolated platform adapters. The social system is not the game-data authority. It may use only information already recorded in the active broadcast, roster, sponsor, theme, and weather state.

## Operator workflow

1. Configure one or more X or Facebook Page account records.
2. Store only a credential reference in CSRN. The credential value is supplied outside the queue through the process environment or a future OAuth credential provider.
3. Create a draft manually, from an eligible recorded event, or through the optional automatic-draft setting.
4. Review the generated copy, score, player attribution, headshot, school branding, sponsor, link, and platform-sized card.
5. Edit the draft when required. Editing clears prior approval and regenerates the platform copy and cards.
6. Approve with the exact confirmation phrase `APPROVE SOCIAL POST`.
7. Publish to selected enabled accounts or process an explicitly enabled automatic queue.
8. Review every attempt in the persistent audit history. Retry transient failures from the retained draft.
9. For a published factual error, create a linked correction draft. A published post can also be retracted with `RETRACT SOCIAL POST` when the platform adapter supports deletion.

## Supported draft types

- Touchdown
- Turnover
- Field goal
- Safety
- Lead change
- Halftime
- Final score
- Milestone
- Player of the game
- Weather delay
- Game resumption
- Severe-weather emergency

A recorded touchdown, turnover, or field goal may be converted directly from its event identifier. A milestone, player-of-the-game, or emergency draft requires a grounded operator message because CSRN must not invent the achievement or official warning language.

## Sponsor rules

Active sponsors can be assigned to specific event types or placed into a rotation. Expired or inactive sponsors are rejected. Severe-weather emergency drafts always suppress sponsor name, logo, and lead-in regardless of account, event mapping, rotation, or operator payload. Ordinary weather-delay and resumption posts may use normal branding when approved by the operator.

## Player and brand assets

The renderer accepts only CSRN-managed local files:

- approved school logos;
- roster headshots;
- sponsor assets;
- organization branding.

Remote image fetching and path traversal are rejected. Missing optional media does not prevent a text-and-brand card from being rendered.

## Theme integration

Cards use the active Phase 6.8 theme tokens and are generated independently for:

- X: 1600 × 900 PNG;
- Facebook: 1200 × 630 PNG.

Each generated file is retained with the draft so the exact approved visual can be audited and retried.

## Platform boundaries

The X adapter uses an OAuth user access token supplied by the external credential resolver, uploads the image through the X API v2 media endpoint, then creates the post through `POST /2/tweets`. The Facebook adapter publishes a Page photo with message text through a version-configurable Graph API endpoint. Platform API versions, account identifiers, and credential references remain configuration rather than application secrets.

Default environment references:

- `CSRN_X_ACCESS_TOKEN`
- `CSRN_FACEBOOK_PAGE_ACCESS_TOKEN`

Commercial deployments should replace direct environment resolution with an OAuth/account-connection provider. CSRN must never place access tokens, refresh tokens, app secrets, or passwords inside `Data/Social/social_state.json`, support bundles, draft payloads, route responses, or audit records.

## Retry and correction model

A platform attempt records:

- account and platform;
- result code;
- retryability;
- retry-after delay when supplied;
- timestamp.

A successful platform publication is preserved even when another account fails, producing a partial status. Corrections are new linked drafts and do not mutate the historical content that was originally approved. Retraction is an explicit, audited action.

## Event integration

The Event Service invokes an optional social callback only after the authoritative game event has been saved. The callback may create a draft when automatic draft creation is enabled. It never performs network publication inside the game-event transaction, and any social exception is isolated so it cannot invalidate a touchdown, turnover, field goal, or other game action.

## Postgame handoff

Phase 6.9 exposes a structured handoff containing the final recorded score, events, plays, halftime score when available, and whether statistician data is present. Phase 6.10 will use that handoff to create a grounded recap. Missing data must be omitted; yardage, player attribution, scoring events, weather conditions, and statistics must never be invented.
