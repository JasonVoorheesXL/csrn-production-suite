

Phase 6.9 - Social Publishing Engine
- Added preview-first X and Facebook Page publishing adapters.
- Added theme-driven event cards with school logos, player headshots, and approved sponsors.
- Added explicit approval, retries, audit history, corrections, retractions, and emergency sponsor suppression.
- Added a grounded postgame data handoff for Phase 6.10.
Phase 6.10m - HTTPS Facebook Callback
- Corrected the Facebook OAuth callback after Meta required HTTPS for the current app configuration.
- Added configurable HTTPS redirect validation with the exact CSRN callback path.
- Moved OAuth state validation into the connection service so a secure public callback can return to the local operator interface.
- Preserved Windows DPAPI storage for the Meta App Secret and Page access token.
- Prepared the development flow for a temporary HTTPS tunnel; commercial release remains bound to a PossumFrog-hosted connection broker.
Phase 6.10p - Social Card Fit and Sponsor Presentation
- Added responsive social-card text fitting for long team names, scores, matchups, and event details.
- Added headshot-aware layout geometry and a dedicated sponsor footer.
- Added configurable public player-name policies while retaining preferred-name support.
- Added PICK SIX and defensive-touchdown public headings derived from grounded turnover events.
- Added per-draft active-sponsor selection and preview fit warnings.


Phase 6.10q - Social Draft Workflow
- Added a full edit/correction dialog with different behavior for unpublished and published posts.
- Added grounded touchdown conversion summaries from recorded XP and two-point events.
- Unified sponsor selection across manual and eligible-event draft creation and filtered unavailable sponsors.

Phase 6.10t - Commercial Sponsor Lockup
- Rebuilt the standard sponsor footer as a unified, mobile-readable paid placement.
- Added a large contrast-backed logo panel and enlarged sponsor attribution typography.
- Preserved dedicated horizontal artwork as the only true full-width banner mode.

Phase 6.10u - Sponsor Value and Jersey Fidelity
- Made number-only jersey formatting independent of roster resolution.
- Rebuilt the standard sponsor footer as a sponsor-first commercial lockup.

Phase 6.10v - Social Draft Lifecycle
- Added controlled discard, Facebook retraction, and archival workflows.
- Preserved publication and audit records instead of permanently erasing social history.
- Added explicit lifecycle statuses, confirmations, and inactive-record separation in the operator interface.



Phase 6.10x - Live Queue Guardrails
- Restored lifecycle methods alongside grounded conversion outcomes.
- Added game-bound and eight-hour expiration for unpublished live updates.
- Added server-side stale-draft rejection and a modal assisted-manual X workflow.


Phase 6.10y - X Package Interaction Fix
- Replaced the assisted-manual X package section with a reliable modal dialog.
- Added preparing, success, failure, copy, download, and compose feedback.
- Preserved the no-OAuth, no-API, manual X boundary.


Phase 6.10z - Immediate Queue and X Draft Access
- Allowed manual X package preparation directly from fresh drafts.
- Added optimistic queue removal after confirmed draft discard.
- Added visible X package preparation feedback.


Phase 6.11a - Postgame Summary Handoff
- Added an explicit recap review, approval, final-draft, and Social Publishing handoff.
- Added recap provenance to FINAL social drafts.
- Added Copy graphic for optional manual X image pasting.
- Changed discard completion to a reliable full-page refresh.


Phase 6.11b - Deterministic Article Generator
- Converted grounded recap facts into a readable article without hosted or local AI.
- Added deterministic prose variation, Player of the Game handling, article sponsor selection, and social handoff metadata.
- Replaced delayed discard refresh with a hard Social Publishing redirect.


Phase 6.12a - Football Release Candidate Readiness
- Centralized grouped responsive navigation across primary interfaces.
- Added release-gate preflight and downloadable rehearsal reports.
- Kept fictional fixture removal separate and non-destructive.


Phase 6.12d - Verified Navigation and Readiness
- Corrected prior packaging source error.
- Rebuilt from known-good 6.12a payload.
- Deployed root and templates index files.
- Verified grouped navigation, Release Readiness controls, and state synchronization.


Phase 6.12e - Cross-Page Navigation Fix
- Fixed persistent open dropdowns.
- Added real links for all primary suite modules.
- Kept local module switching on the root page.
- Added outside-click and Escape dismissal.


Phase 6.12f - Player Identity Repair
- Normalized fictional roster and school media paths.
- Installed fixture media in supported local storage locations.
- Added temporary non-event player headshot management utility.
