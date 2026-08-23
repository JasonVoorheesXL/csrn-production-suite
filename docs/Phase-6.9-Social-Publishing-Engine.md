# Phase 6.9 — Social Publishing Engine

## Purpose

Phase 6.9 converts recorded CSRN game events into reviewable, branded social drafts. Approved Facebook Page drafts may publish through the isolated Facebook adapter. X remains an assisted-manual export and is not an authenticated publisher. The social system is not the game-data authority and may use only information already recorded in the active broadcast, roster, sponsor, theme, weather, and recap state.

## Operator workflow

1. Configure the Meta development application once on the CSRN laptop.
2. Click **Connect Facebook Page** and complete Facebook Login in the browser.
3. Select one of the Pages returned for the signed-in Facebook account. Page name, ID, URL, profile image, and available tasks populate automatically.
4. Run the read-only **Test connection** check before attempting any publication.
5. Create a draft manually, from an eligible recorded event, or through the optional automatic-draft setting.
6. Review the copy, score, attribution, branding, sponsor, link, and platform-sized card. Editing clears prior approval and regenerates the platform copy and cards.
7. Approve with the exact confirmation phrase `APPROVE SOCIAL POST`.
8. Publish to the selected enabled Facebook Page or process an explicitly enabled Facebook-only automatic queue.
9. For X, prepare the assisted-manual package, copy the text, download the X graphic, open the public composer, attach the graphic, and publish manually.
10. Review automatic Facebook attempts and manual X package preparation in persistent audit history. Corrections are linked drafts; supported published posts can be retracted with `RETRACT SOCIAL POST`.

## Facebook connection test

Alpha.6l implements a real OAuth authorization-code flow for development testing. The operator supplies a Meta App ID and App Secret locally, registers the exact loopback callback displayed by CSRN, signs in through Facebook, and grants the Page permissions requested by the application. CSRN exchanges the authorization code, queries `/me/accounts`, and presents manageable Pages without exposing their Page access tokens.

The selected Page access token and Meta App Secret are protected with Windows Data Protection API (DPAPI) for the current Windows user. They are not written into `Data/Social/social_state.json`, normal configuration, Flask session data, route responses, draft payloads, audit rows, or support bundles. Facebook setup, connection, selection, test, and disconnect actions are restricted to `127.0.0.1`/`::1` so credentials cannot be configured from a phone or another device on the broadcast network.

The local App Secret design is acceptable only for an owner-operated development test. It is not the commercial customer architecture because a desktop application cannot permanently conceal a shared App Secret. Commercial releases require a PossumFrog-controlled HTTPS OAuth broker, secure server-side App Secret custody, Meta App Review/Advanced Access where required, and a customer-safe token renewal/revocation process.

## Requested Facebook permissions

- `pages_show_list` — return Pages available to the signed-in operator;
- `pages_manage_posts` — create and manage Page posts after explicit CSRN approval;
- `pages_read_engagement` — read the selected Page identity and engagement-related fields needed for validation.

The application begins with a read-only Page identity check. A test post is never created merely by connecting or testing the authorization.

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

Active sponsors can be assigned to specific event types or placed into a rotation. Expired or inactive sponsors are rejected. Severe-weather emergency drafts always suppress sponsor name, logo, and lead-in regardless of account, mapping, rotation, or operator payload. Ordinary weather-delay and resumption posts may use normal branding when approved by the operator.

## Player and brand assets

The renderer accepts only CSRN-managed local files: approved school logos, roster headshots, sponsor assets, and organization branding. Remote image fetching and path traversal are rejected. Missing optional media does not prevent a text-and-brand card from being rendered.

## Theme integration

Cards use the active Phase 6.8 theme tokens and are generated independently for X at 1600 × 900 PNG and Facebook at 1200 × 630 PNG. Each generated file is retained with the draft so the exact approved visual can be audited and retried.

## Platform boundaries

The Facebook adapter publishes a Page photo with message text through a version-configurable Graph API endpoint. The adapter resolves the selected Page token from the Windows-user-bound secure vault by reference; it never receives a raw token from an HTTP request or social-state record.

X is assisted-manual only. CSRN generates a 1600 × 900 graphic, prepares text within the X character limit, provides copy and download controls, and opens the public X composer. CSRN does not request X OAuth, require an X developer account, consume X API credits, upload X media, create X posts, or place X in an automatic queue.

## Retry, correction, and event isolation

A platform attempt records account, platform, result code, retryability, retry-after delay, and timestamp. Provider error details are bounded and must not contain credentials. Corrections are new linked drafts and do not mutate the content originally approved. The Event Service invokes social draft creation only after the authoritative game event is saved; a social failure can never invalidate game data.

## Postgame handoff

The social engine exposes a structured handoff containing recorded score, events, plays, halftime score when available, and whether statistician data is present. Phase 6.10 uses that handoff to create a grounded recap. Missing information is omitted; yardage, attribution, scoring events, weather, and statistics must never be invented.
