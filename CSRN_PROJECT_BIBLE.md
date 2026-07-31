# CSRN Production Suite — Project Bible

Document role: Living source of truth, continuity record, and new-chat handoff  
Product: CSRN Production Suite  
Primary release target: Finished Windows-hosted football broadcasting product  
Owner: Jason Chrest  
Last audited: 2026-07-30  
Current status: **GATE 4 ACTIVE — repair blocking identity and Command Center interface defects**

---

## 1. How every new chat must use this document

At the beginning of any new ChatGPT or Codex conversation concerning CSRN:

1. Read this entire file before recommending or changing anything.
2. Treat the paths, Git state, scope, decisions, blockers, and release gates here as authoritative unless Jason explicitly changes them.
3. Inspect the current Git branch, commit, and worktree before editing code.
4. Verify the exact active file and runtime route before preparing a patch.
5. Report discrepancies between this document and the repository before proceeding.
6. Update this document whenever a decision, branch, version, blocker, or release-gate status materially changes.
7. Never claim that background or overnight work is continuing unless an actual task or automation was created and can be verified.

This file governs continuity. Chat memory does not.

---

## 2. Authoritative locations

### Current synchronized development folder

```text
C:\Users\Darth\My Drive\CSRN\Development\CSRN-Production-Suite
```

Jason currently launches the suite from this folder using:

```text
RUN_CSRN_COMMAND_CENTER.bat
```

### GitHub repository

```text
https://github.com/JasonVoorheesXL/csrn-production-suite
```

### Intended source-of-truth policy

Once recovery is complete:

- **GitHub** is authoritative for application source, tests, documentation, and release history.
- **A local Git checkout** is used for development and testing.
- **Google Drive** stores backups, exported reports, approved release packages, screenshots, operator material, and customer/runtime data. It must not remain a parallel live source tree.
- **Regular ChatGPT** is used for product decisions, workflow reasoning, visual review, and release priorities.
- **Codex** is used for repository inspection, implementation, testing, and controlled Git changes.

No chat is itself a source of truth.

---

## 3. Verified launch and entrypoint behavior

`RUN_CSRN_COMMAND_CENTER.bat`:

1. Changes into its own project directory.
2. Uses `.venv\Scripts\python.exe`.
3. Verifies Python 3.13.14 and the exact runtime dependency lock without
   installing or upgrading anything.
4. Runs game-day storage preflight and recovery startup tracking.
5. Launches `app.py`.
6. Serves the suite with Waitress on port 5050.
7. Records clean shutdown when the application exits normally.

The current Flask page route uses:

```python
render_template("index.html")
```

Therefore, the active Command Center interface is:

```text
templates\index.html
```

The obsolete root-level `index.html` duplicate was removed during Gate 1.

Environment setup is now intentionally separate:

- `SETUP_CSRN_ENVIRONMENT.bat` creates/synchronizes the runtime environment;
- `SETUP_CSRN_DEVELOPMENT_ENVIRONMENT.bat` adds the locked test toolchain;
- an incompatible `.venv` is preserved as `.venv-stale-<timestamp>` rather than
  deleted;
- normal startup is offline and launches only from a verified locked
  environment.

---

## 4. Current audited Git and version state

The synchronized development folder was audited directly after Gate 1.

### Gate 4 working branch

```text
gate4/blocking-product-repairs
```

### Authoritative merged Gate 3 commit

```text
09329821e2b13ebe066dc7c8d42b872afb789618 — Merge PR #89: make CSRN environment and releases reproducible
```

### Tracking branch

```text
origin/gate4/blocking-product-repairs
```

### Canonical version identity

```text
1.13.0-alpha.8f — Player Identity Repair and Source Alignment
```

### Canonical build identity

```text
V1.13A8F-SOURCE-ALIGNMENT
```

### Current Gate 3 implementation state

```text
The Gate 3 branch starts from merged commit
`ef9d4a5d11b7c0aa6535e501d0a6503907120f76`. The environment/startup/build
repair is implemented in the working tree and awaits creation of a clean
Python 3.13.14 development environment, the full test suite, commit, push, and
GitHub CI.
```

### Branch lineage

The recovery branch was created from the verified Phase 6.9 lineage, captured
the later operational worktree, completed source-hygiene cleanup, and was
independently verified locally and through GitHub at `9f37189c`. The
previously uncommitted `alpha.8f` application is now represented by a remote
Git commit.

---

## 5. GitHub state and PR warning

GitHub `main` remains the historical:

```text
v1.5.0-alpha
```

Closed PRs:

```text
PR #86 — stale documentation-only branch; closed without merge
PR #87 — superseded after a remote-ref race prevented a trustworthy PR snapshot
```

Merged recovery PR:

```text
https://github.com/JasonVoorheesXL/csrn-production-suite/pull/88
```

PR #88 targeted `develop-1.13` from
`recovery/alpha-8f-source-alignment`. Its first full Windows and Ubuntu CI run
reached the complete test suite and reported `16 failed, 1197 passed`. The
identity-rendering checks fixed at `0d16f17f` passed. The remaining failures
were classified as a bounded mixture of OAuth callback defects, recap prose
regressions, and stale architecture/documentation assertions.

**PR #88 passed both required CI jobs and merged into `develop-1.13` at
`ef9d4a5d11b7c0aa6535e501d0a6503907120f76`.**

The merged recovery branch was:

```text
recovery/alpha-8f-source-alignment
```

It was based on:

```text
origin/phase/6.9-social-publishing-engine
```

It did not start from `main`.

---

## 6. Current product stage

The correct stage is:

```text
Source recovery, release-candidate integration audit, and controlled operational testing
```

The product is not in ordinary feature-development mode.

The product is not ready for:

- another installer patch;
- a formal full-game rehearsal;
- a release freeze;
- a merge to `main`;
- a customer installer;
- production deployment.

The next engineering action is Gate 3: replace the broken local development
environment with a reproducible declared setup, keep CI green, and separate
dependency setup/update from normal Command Center startup.

---

## 7. Confirmed strengths

The audit confirmed substantial working product architecture:

- 193 unique Flask routes register.
- 139 Python test files exist.
- All Python source compiles.
- Embedded JavaScript in all eight HTML pages passes syntax validation.
- No missing static API route reference was found in the UI scan.
- `/`, `/overlay`, `/captions`, `/weather-overlay`, and `/api/security-status` pass basic smoke tests.
- Protected pages reject unauthenticated access.
- Root and template `index.html` copies are currently identical, although only the template is the Flask entrypoint.
- The active lineage contains the game-day, repository, service, route, OBS, recovery, weather, caption, theme, social, and recap foundations.

The project is recoverable. The current problem is integration discipline and release evidence.

---

## 8. Confirmed blocking defects

### 8.1 Source and release identity

Resolved in Gates 1 and 2:

- `alpha.8f` is represented in Git and merged into `develop-1.13`;
- the canonical runtime, documentation, version, and build identity agree;
- PR #86 was closed without merge as stale.

### 8.2 Player and school identity rendering

Resolved in Gate 4:

- The Command Center preview and live overlay no longer use unrelated CSRN
  branding for missing player or school identity.
- Approved school-logo fields are included in the school display payload.
- The live overlay applies the identity order directly without a transitional
  mutation observer or intermediate CSRN-logo assignment.

Enforced fallback order:

Player portrait area:

1. Player headshot
2. Selected player’s team logo
3. Neutral player silhouette

Team watermark area:

1. Selected player’s team/school logo
2. School monogram
3. Neutral blank treatment

### 8.3 Roster headshot visibility

Resolved in Gate 4: roster rows show the jersey number, player name, position,
class, status, headshot thumbnail, team-logo fallback, and explicit
missing-headshot state. Integrated uploads persist the stored URL and player
metadata, and failed repository saves remove the newly written file.

### 8.4 Obsolete headshot utility

Resolved in Gate 1: the obsolete standalone headshot utility was removed after
the integrated player-edit upload path was retained.

### 8.5 Player-event visual defects

Resolved in Gate 4:

- event-label color and backing are independent from team accent color;
- event label, player name, details, and play detail have explicit spacing;
- long player names wrap and dynamically fit within the on-air treatment;
- `pg-onair-play-detail` has an explicit preview/on-air style contract;
- invalid home/visitor logos hide cleanly, and player/team media follow tested
  fallbacks. Gate 6 retains the full screenshot matrix.

### 8.6 Duplicate HTML IDs

Resolved in Gate 4: the duplicate school-import control block was removed, and
the active Command Center is protected by a unique-ID regression test. The
former duplicate IDs were:

```text
schoolImportPanel
importState
importClassification
importCreateVenues
runSchoolImport
runSchoolEnrichment
runBrandingEnrichment
schoolImportSummary
schoolImportResults
```

Each now appears at most once.

### 8.7 Test reproducibility

Implementation complete; execution evidence pending:

- runtime dependencies are exactly pinned in `requirements.txt`;
- pytest and all test dependencies are exactly pinned in
  `requirements-dev.txt`;
- local and CI development environments share the same declaration;
- Python 3.13.14 is the single supported baseline;
- the stale synchronized `.venv` will be preserved and replaced only by the
  explicit setup command;
- normal startup performs verification only and never installs packages;
- full Windows and Ubuntu CI must pass before Gate 3 can merge.

### 8.8 Runtime data in source control

Twenty-three `Data` files are already tracked, including:

- pre-upgrade backups;
- social state;
- weather state;
- caption state;
- venue state;
- theme state;
- package state;
- rehearsal state.

Runtime/customer data must be separated from source. A sampled tracked backup contained an OBS password field, but its value was empty at audit time.

---

## 9. Frozen football product scope

The initial finished product is a Windows-hosted football broadcasting suite with browser-based control from phones, tablets, Chromebooks, and secondary computers.

Explicitly removed from scope:

- dedicated Chromebook/PWA product;
- automated X posting;
- X OAuth/API integration;
- hosted AI;
- local AI;
- other sports before football release evidence;
- macOS host before Windows stability.

X remains assisted-manual only.

Postgame articles remain deterministic and grounded in recorded data.

### Required existing workflow

- Configuration
- School Database
- Venue association
- Staff/personnel directory
- Rosters and player media
- New Broadcast
- Command Center
- OBS/scorebug
- clock, quarter, down/distance, possession, scoring, corrections, and undo
- event history
- statistics
- sponsors
- captions
- weather and alerts
- Social Publishing
- manual X package
- Facebook workflow where configured
- Player of the Game
- grounded recap
- deterministic article
- archive and recovery
- release readiness

### Remaining approved pre-freeze football features

These may be implemented only after source recovery and baseline repair:

1. Regional classification and region assignment.
2. Region-game flag.
3. Overall and regional record tracking.
4. Scrimmage/exhibition rules that do not alter official records.
5. Special-game designations such as Homecoming, Senior Night, rivalry, playoff, and championship.
6. Player Spotlight using the existing Player Identification Card.
7. Team-filtered player selection for Player Spotlight.
8. Manual show, hide, and clear controls.
9. Verified statistics only.

No additional pre-release features are to be added without an explicit scope decision recorded here.

---

## 10. Recovery and completion plan

### Gate 0 — Preserve and freeze

- Stop installer-based changes.
- Stop feature development.
- Do not merge PR #86.
- Preserve the current Drive tree.
- Record file hashes.

Exit condition: today’s state is recoverable.

### Gate 1 — Recover `alpha.8f` into Git

- Create `recovery/alpha-8f-source-alignment` from `origin/phase/6.9-social-publishing-engine`.
- Apply the 26 tracked changes.
- Review the 21 untracked paths individually.
- Add valid source, tests, documentation, and fixture assets.
- Exclude live data, secrets, caches, virtual environments, generated output, obsolete utilities, and temporary tunnel artifacts.
- Move fictional data into a dedicated versioned fixture tree.

Exit condition: one clean Git commit reproduces the operational application.

### Gate 2 — Repair governance

- Choose one version/build identity.
- Synchronize `VERSION.txt`, README, roadmap, changelog, build journal, UI identity, and this Bible.
- Close PR #86 as superseded.
- Review and merge the recovery branch into `develop-1.13`.

Exit condition: documents and application identify the same commit and version.

### Gate 3 — Reproducible environment and tests

- Add `pytest` to a development dependency declaration.
- Pin or lock production dependencies.
- Build a clean virtual environment.
- Run all 139 tests.
- Add GitHub CI.
- Add a deterministic build command.
- Separate setup/update from normal application startup.

Exit condition: a clean clone can install, test, build, and launch.

**Status: complete.** PR #89 passed Windows and Ubuntu on Python 3.13.14
and merged into `develop-1.13` at
`09329821e2b13ebe066dc7c8d42b872afb789618`.

### Gate 4 — Repair blocking product defects

- neutral identity fallbacks;
- roster thumbnails/missing indicators;
- integrated headshot persistence;
- obsolete headshot utility removal;
- event-label contrast;
- event/name/detail spacing;
- play-detail styling;
- long-name containment;
- home/visitor logo validation;
- duplicate ID repair;
- regression tests.

Exit condition: no open blocking identity or interface defect.

**Status: complete.** PR #90 passed Windows and Ubuntu on Python 3.13.14 in
GitHub Actions run `30579098825` and merged into `develop-1.13` at
`10afa40c99877dca9b4362a1ad4ef4c950db362d`.

### Gate 5 — Complete frozen football scope

- regional data and record rules;
- special-game designations;
- Player Spotlight card and Player Highlight video;
- tests and documentation.

Exit condition: approved football scope is complete.

**Status: active.** Branch `gate5/frozen-football-scope` was created and pushed
from the exact Gate 4 merge
`10afa40c99877dca9b4362a1ad4ef4c950db362d`.

Initial audit:

- schools persist classification and region, but broadcasts do not yet persist
  home/visitor overall and region records or a rule controlling which result
  affects which record;
- no structured special-game designation exists in the broadcast record or
  Create/Edit Broadcast interface;
- the player graphic already renders `play_detail`, but the manual operator
  path did not expose or persist the frozen-scope `Player Spotlight` type.
- Player Spotlight is the first independent Gate 5 repair; the record and
  designation model must be fixed before implementation so archived broadcasts
  retain their original pregame context.

#### Player Spotlight operator workflow

The production destination is a dedicated **Player Spotlight** menu within
Program Visual Controls. Player Identification Master remains the roster and
identity source; it must not be Jordan's primary live highlight workflow.

The Program Visual Controls menu must let the operator:

- select the applicable roster and player;
- select which prepared player information or saved highlight note to feature,
  with a controlled custom-text option for an unplanned live achievement;
- preview the complete graphic before air;
- select its display duration; and
- show, update, hide, or clear the spotlight without editing the underlying
  player identity.

Prepared spotlight information belongs with the player's reusable roster data
so it can be entered before the broadcast and selected quickly during the
event. The live custom-text field remains available for a new achievement that
was not known during preparation.

Player-event sequencing is deterministic. If a touchdown is recorded while a
Player Spotlight is on air, the touchdown graphic is queued rather than
discarded or allowed to overwrite the active spotlight. When the spotlight
ends—by duration expiry or operator hide—the queued touchdown graphic appears
next. The queue must preserve the scoring player and event detail, prevent
duplicate delivery, and expose a way to cancel an erroneous queued event before
it reaches air. `Clear` behavior and queue advancement must be explicit in the
operator interface and covered by tests.

#### Sponsor Spotlight operator workflow

Program Visual Controls must also provide a dedicated **Sponsor Spotlight**
activity for filling a natural broadcast lull. It is separate from Player
Highlight while following the same preview-first operator pattern.

The Sponsor Spotlight menu must let the operator:

- select an approved sponsor profile from the sponsor library;
- select one of that sponsor's approved still graphics or video assets;
- optionally select a prepared lead-in or caption;
- preview the exact composition without putting it on air;
- choose a display duration for still media and use either the approved clip
  duration or a controlled cutoff for video; and
- show, update, hide, clear, or cancel the activity.

The on-air composition covers most of the program canvas but remains below the
scorebug. The scorebug is a protected top layer and stays visible for the full
Sponsor Spotlight. Sponsor media must preserve its aspect ratio, must not expose
browser playback controls, and must end cleanly without leaving a black frame,
stale audio, or a hidden scorebug.

Sponsor Spotlight is a low-priority, lull-only activity. Live game-event
graphics take precedence when play resumes. The graphics coordinator must
define and test whether each event interrupts the spotlight immediately or is
queued behind it; no event may be lost or silently overwrite another activity.
Video audio policy, transition timing, replay behavior, and cancellation must
be visible and deterministic in the operator interface.

Gate 5 implementation checkpoint:

- Program Visual Controls now owns dedicated Player Spotlight and Sponsor
  Spotlight operator panels with preview-first selection and duration controls.
- A persisted graphics queue holds a touchdown recorded while Player Spotlight
  is active. Expiry or operator hide advances the queued event exactly once;
  each pending item can be cancelled before air.
- Sponsor Spotlight accepts active sponsors and Sponsor-category image/video
  assets whose rights status is Owned, Licensed, Permission Granted, or Public
  Domain. Unverified media is blocked from air.
- Sponsor Spotlight is interrupted by a live automated scoring-player graphic.
  The scorebug and event ticker are protected above the spotlight layer.
- Sponsor video begins muted in this checkpoint. Enabling program audio requires
  a separate explicit operator control and OBS audio-path validation.
- Player Spotlight duration choices are consistent between Program Visual
  Controls and Player Identification Master through the 30-second option.
- The live overlay publishes and checks an overlay schema revision. After one
  manual OBS browser-source refresh for this checkpoint, later incompatible
  overlay updates automatically reload instead of retaining stale HTML.
- Sponsor Spotlight uses a shared feature-stage layout: a theme-driven lead-in,
  sponsor name, and caption band overlays the top of the media; the still image
  or video fits at the largest aspect-preserving size beneath that band; and the
  stage ends at the top of the protected scorebug in compact and graphic modes.
  The band consumes the operator-selected theme's surface, accent, text, border,
  radius, shadow, and font tokens.
- Broadcaster penalty buttons use the context-free label `Penalty`; the home or
  visitor column supplies team context, preventing stale fixture or generic
  team names from leaking into the live controls.

#### Frozen follow-on — Player Highlight video

Player Highlight means actual season highlight video. It is separate from the
roster-driven Player Spotlight card and is not a general-purpose video player.

- Operators select a roster and player first, then choose an approved
  player/season-linked highlight clip.
- The clip uses the same feature-stage geometry as Sponsor Spotlight: a
  theme-driven player identity/information band at the top, aspect-preserving
  video below it, and the protected scorebug beneath the stage.
- Player name, number, position, grade, and the operator-entered recognition
  note remain visible in the top band without being burned into the source
  video.
- A touchdown recorded during the clip follows the existing Player Spotlight
  rule: it enters the graphics queue and plays exactly once after the clip ends
  or the operator hides it.
- Clip approval, season/player association, playback cutoff, replay behavior,
  cancellation, muted/default audio, and OBS program-audio routing require
  focused tests before this presentation can be marked available.

#### Sponsor broadcast creative package

One sponsor logo must not be stretched, cropped, or repurposed across every
broadcast placement. Each commercial sponsor should provide or approve a
placement-tagged creative package. Until an exact rendition exists, the system
must letterbox the closest approved asset without cropping it.

Required package renditions:

- **Primary transparent logo:** square 1200 × 1200 PNG, with at least 8 percent
  transparent safe space on every edge;
- **Feature-stage still:** 1600 × 500 PNG or high-quality JPEG, designed for the
  Sponsor Spotlight media region below its top information band;
- **Feature-stage video:** 1600 × 500 H.264 MP4 or WebM, with critical content
  inside a 5 percent safe area and a separately declared audio policy;
- **Lower-third sponsor mark:** 1200 × 300 transparent PNG;
- **Scorebug sponsor bug:** 600 × 180 transparent PNG; and
- **Full 16:9 master:** 1920 × 1080 still/video retained as the archival master
  and for future true full-screen uses.

Asset records must gain an explicit placement/rendition role rather than
inferring suitability from filename or generic `Logo`, `Background`, `Overlay`,
or `Video` type alone. Sponsor Spotlight should prefer the feature-stage still
or video, while other graphics expose only renditions compatible with their
placement. Rights approval remains per asset or may be inherited from a
documented sponsor-package approval covering the submitted package.

#### Deferred commercial presentation concept — starting lineups

This is recorded for later design discussion and is not a Gate 4 blocker or
part of the currently approved frozen-football scope.

- Present starting lineups as full-screen broadcast graphics.
- Split the presentation into three units:
  - offense: 11 starters;
  - defense: 11 starters;
  - special teams: 4 roles only — punter, kicker, holder, and long snapper.
- Determine during commercial-version design whether each unit appears as one
  complete full-screen board, cycles through smaller player groups, or uses a
  controlled sequence combining both treatments.
- Preserve operator control so a unit can be shown, advanced, repeated, or
  skipped without disturbing the scorebug or live game state.

#### Deferred usability repair — template discovery and preview

Operators must not be required to know or type a template/theme name before
they can evaluate it. The current Settings interface exposes a free-text theme
field, while the separate Graphics Theme Manager already has catalog cards and
a non-live preview action; those experiences must be consolidated and made
discoverable.

- Replace normal free-text template selection with a catalog-backed selector
  or visual card browser.
- Show a thumbnail or representative rendered preview, template name,
  category, intended use, aspect ratio, and active/selected state.
- Allow full-size preview before activation without changing on-air graphics.
- Provide filters for graphic type and production context.
- Keep direct template IDs/names available only in an explicitly labeled
  advanced control.
- Include representative template states in Gate 6 visual-regression approval.

### Gate 6 — Visual regression

Render and approve:

- home and visitor teams;
- headshot present/missing;
- school logo present/missing;
- short and long names;
- touchdown, turnover, field goal, Player Spotlight card, Player Highlight
  video, and Player of the Game;
- scorebug, ticker, lower third, sponsor, caption, weather, and social states;
- desktop, phone, and production-resolution views.

Exit condition: approved screenshots exist for all material states.

### Gate 7 — Software-only rehearsals

Run two complete games from one exact commit, including:

- New Broadcast and venue population;
- full football workflow;
- statistics;
- sponsors;
- social drafts without unintended publication;
- recap/article;
- archive and reopen;
- application termination and state recovery;
- wrong-team and stale-draft prevention.

Exit condition: two software rehearsals pass with no blocking defects.

### Gate 8 — P4next and OBS commissioning

- isolated P4next channels;
- gain and headphone mixes;
- multitrack backup;
- OBS audio and recording;
- browser sources;
- phone/Chromebook control;
- network-loss response;
- caption-channel assignments.

Exit condition: commissioning report passes.

### Gate 9 — Formal Phase 6.6 rehearsals

Complete two operator-recorded rehearsals and required recovery drills:

- OBS loss;
- network loss;
- application termination;
- caption-worker loss;
- weather-service loss;
- mixer/USB loss;
- safety-snapshot restore;
- weather delay and resumption.

Exit condition: all drills pass and no blocking defect remains.

### Gate 10 — Freeze release candidate

- record exact commit SHA;
- record version/build;
- preserve tests and rehearsal evidence;
- preserve approved screenshots;
- generate rollback artifact;
- write release manifest;
- tag the commit.

Suggested first tag:

```text
v1.13.0-football-rc1
```

### Gate 11 — Customer-ready product

- Windows installer/uninstaller;
- stable external customer-data location;
- upgrade preservation;
- clean default data;
- rollback;
- customer-safe support bundle;
- licensing/entitlement completion;
- signed artifacts where available;
- operator and installation manuals.

### Gate 12 — Pilot and final release

1. Private/unlisted broadcast.
2. Supervised live game.
3. Correct pilot defects.
4. Second live game.
5. Final 1.0 approval.

---

## 11. Definition of done

CSRN football is finished only when:

- a clean Git commit is authoritative;
- a clean machine can install and launch it;
- all automated tests pass;
- all blocking visual and functional defects are closed;
- frozen football scope is complete;
- two software-only rehearsals pass;
- P4next/OBS commissioning passes;
- two formal Phase 6.6 rehearsals and all recovery drills pass;
- the release candidate is tagged and reproducible;
- installer, upgrade, rollback, documentation, and clean customer data are ready;
- at least two controlled live pilots succeed.

“Works on the current Drive folder” is not the definition of done.

---

## 12. Change-control rules

Every code change must:

1. Start from a named Git branch and recorded commit.
2. State the defect or approved requirement.
3. Identify the exact active files and routes.
4. Add or update tests.
5. Avoid live customer/runtime data.
6. Pass focused tests before broad tests.
7. Receive visual verification when presentation changes.
8. Update changelog and this Bible when material.
9. Produce a commit before packaging.
10. Package only from the tested commit.

Never:

- patch duplicated Drive search results without grounding the active folder;
- build a release from chat-generated files that are not committed;
- overwrite the running project using an unverified installer;
- claim testing passed when only compilation or static review ran;
- advance rehearsals with an open blocking identity, score, persistence, or recovery defect;
- use unrelated CSRN branding as an automatic player/team fallback;
- allow a new chat to infer project state from its title or memory.

---

## 13. Project Bible update protocol

Update this file whenever any of these changes:

- authoritative folder;
- Git branch;
- commit SHA;
- version/build;
- product scope;
- approved or removed feature;
- current gate;
- open blocker;
- resolved blocker;
- test count or result;
- rehearsal result;
- release tag;
- source-of-truth policy.

Each update should add an entry to the decision/status log below.

---

## 14. Decision and status log

### 2026-07-30 — Continuity and source audit

- Confirmed the synchronized development folder as the operational folder.
- Confirmed `RUN_CSRN_COMMAND_CENTER.bat` launches `app.py`.
- Confirmed Flask serves `templates/index.html`.
- Confirmed active branch `phase/6.9-social-publishing-engine`.
- Confirmed committed version `alpha.6i` and worktree version `alpha.8f`.
- Confirmed 26 modified and 21 untracked paths.
- Confirmed PR #86 is documentation-only and based on stale `main`.
- Confirmed source recovery is the immediate next action.
- Confirmed release status is blocked.

### 2026-07-30 — Gate 0/1 preservation checkpoint

- Reverified the operational checkout at commit `838708b047e7` on `phase/6.9-social-publishing-engine`.
- Reverified 26 modified tracked paths and 68 actual untracked files (shown by Git as 22 summarized untracked paths after this Bible was added).
- Created remote branch `recovery/alpha-8f-source-alignment` from `phase/6.9-social-publishing-engine`.
- Captured all 94 changed and untracked files in verified commit `8ad61cdd3e07ee4f3f01ec25aba0a87ccc6b11a4`.
- Verified recovery tree `7dc09dbf213d5656365175ce3896100fddcc2c4c` and a clean worktree against the captured commit.
- Packaged the complete commit and history in `CSRN_GATE_1_RECOVERY.bundle`; the guarded completion script verifies its SHA-256 before importing it.
- Local installation and remote push remain pending because the Codex runtime cannot write the operational checkout's hidden `.git` metadata or provide network access to spawned Git.
- Prepared `COMPLETE_CSRN_GATE_1.ps1` to make a safety stash, import the verified bundle, switch to the recovery branch, verify the exact commit and clean status, and push it to `origin`.
- Gate 0 is complete. Gate 1 is preserved and reproducible, but it is not complete until the guarded script succeeds.

### 2026-07-30 — Gate 1 source-hygiene checkpoint

- Verified recovery commit `ce432e4aadc6024b868ec5a717e892f4517fb6fb` locally and on GitHub with zero divergence.
- Retained safety stash `fb862149215d23eebbf4e5b714ca54079963ee08`.
- Confirmed local recap, social-card, Facebook connection, and encrypted credential files are ignored and not tracked.
- Removed the duplicate root `index.html`; Flask continues to serve `templates/index.html`.
- Removed the obsolete standalone player-headshot utility.
- Removed the temporary Facebook tunnel launcher and retained direct manual tunnel instructions.
- Consolidated fictional headshots, school logos, and sponsor logos into the Northwood–Pine Valley fixture tree.
- Removed fictional fixture venues from operational venue data.
- Removed `Data/Social/social_state.json` from Git tracking without deleting the local runtime file.
- Added source-hygiene regression coverage.
- Committed and pushed `9f37189c5b4fed6c76b8e6228fe8c3086f7c5290`.
- Independently verified the local worktree is clean, local/origin divergence is
  `0/0`, and the connected GitHub branch resolves to the same commit.
- Gate 1 is complete. Gate 2 governance repair is active.

### 2026-07-30 — Gate 2 canonical identity decision

- Selected `1.13.0-alpha.8f — Player Identity Repair and Source Alignment`.
- Selected build `V1.13A8F-SOURCE-ALIGNMENT`.
- Rejected `1.0/1.2 Alpha`, `v1.5.0-alpha`, runtime `alpha.8e`, and build
  `V1.13A8A-FOOTBALL-RC-READINESS` as stale current-state identities.
- Synchronized the runtime fallback, `VERSION.txt`, README files, roadmap,
  changelogs, build journal, and this Bible.
- Added regression coverage that fails when the canonical version or build
  identity drifts across authoritative files.
- Closed draft PR #86 without merge as superseded by the verified recovery
  branch.
- Compared the recovery branch with `develop-1.13` on GitHub. Before the Gate 2
  commit, recovery is three commits ahead and one ancestry-only commit behind;
  the develop-only comparison contains no file changes, so no source payload
  must be imported from `develop-1.13`.

### 2026-07-30 — PR #88 CI remediation checkpoint

- Completed the Gate 2 governance checkpoint at
  `d40467e5b2ab9128493ad82bfec0b6b6e514f547`.
- Added canonical multiline `VERSION.txt` support to the development workflow
  and committed it at `0d16f17f23b7b60c5ea4720cdc695b55fbc4216a`.
- Closed PR #87 without merge after a remote-ref race made its snapshot
  unreliable, then opened PR #88 from the verified branch head.
- Verified that PR #88 passes Python compilation, clean-diff validation, and
  canonical version/build identity checks on both CI platforms.
- Classified the full-suite result of `16 failed, 1197 passed`.
- Corrected the Facebook callback to return to `/social`, use one single-use
  server-side OAuth state store, and remain the only intentional public social
  endpoint.
- Restored editable HTTPS callback configuration and removed the obsolete HTTP
  loopback fallback from the Social Publishing interface.
- Restored grounded lead-change, turnover, and weather descriptions to recap
  prose.
- Aligned route, navigation, social-policy, and documentation regression tests
  with the current Facebook/assisted-manual-X architecture.
- Local dependency-free validation passes all 12 recap-service tests and nine
  focused architecture/grounding checks. Full Flask integration remains
  delegated to GitHub CI because the synchronized `.venv` points to a missing
  Python 3.14 installation.
- Committed and pushed the bounded repair at
  `098390cac84f37f7aa8e9e13241a71aac4f15ad4`.
- GitHub Actions run `30565845144` passed on both
  `ubuntu-latest / Python 3.13` and `windows-latest / Python 3.13`.
- PR #88 is mergeable and ready to merge into `develop-1.13`.

### 2026-07-30 — Gate 2 merged and Gate 3 opened

- Revalidated final PR #88 head
  `1dda30dde905ef52842ee142cc62accf18aed35e` with GitHub Actions run
  `30566281259`.
- Both `ubuntu-latest / Python 3.13` and
  `windows-latest / Python 3.13` passed.
- Merged PR #88 into `develop-1.13` with merge commit
  `ef9d4a5d11b7c0aa6535e501d0a6503907120f76`.
- Gate 1 source recovery and Gate 2 governance repair are complete.
- Gate 3 reproducible environment and test/build workflow is active.
- Gate 3 work must begin on `gate3/reproducible-environment` from the exact
  merged commit and must not alter live runtime data.

### 2026-07-30 — Gate 3 reproducibility implementation checkpoint

- Audited the operational launcher, dependency declarations, GitHub Actions,
  synchronized virtual environment, and release builder.
- Confirmed normal startup previously upgraded installer tools and installed
  dependencies on every launch.
- Confirmed the synchronized `.venv` points to an unavailable Python 3.14
  installation and standardized local validation and CI on Python 3.13.14.
- Added exact runtime and development dependency locks and one shared
  environment verifier for local use and CI.
- Added explicit runtime and development setup launchers. An incompatible
  environment is renamed and preserved instead of recursively deleted.
- Removed all package installation and upgrade behavior from normal Command
  Center startup.
- Made repository compilation validation read-only so it no longer creates
  `__pycache__` files or depends on writable source directories.
- Confined pytest discovery to the authoritative `tests` tree so synchronized
  runtime data and historical installer backups cannot contaminate validation.
- Rebuilt release packaging around exact committed Git-object bytes, a clean
  tracked-tree guard, canonical version/build identity, commit-derived
  timestamps, stable manifests, and fixed ZIP metadata.
- Verified 383 Python files parse, all dependency declarations are exact, and
  two independent builds of the same tracked fixture produce the same SHA-256
  while excluding untracked and runtime data.
- The clean Python 3.13.14 environment passed 28 focused Gate 3 tests and all
  1,221 authoritative repository tests. GitHub CI remains pending.
- Four Pillow `Image.getdata()` deprecation warnings are recorded for later
  maintenance; they do not affect current behavior or Gate 3 acceptance.

### 2026-07-30 — Gate 3 merged and Gate 4 opened

- Opened PR #89 from `gate3/reproducible-environment` at
  `db85bc28a6a867c3787ea1b990ea3f0a63c39bb1`.
- GitHub Actions run `30568541729` passed on Windows and Ubuntu with Python
  3.13.14.
- Merged PR #89 into `develop-1.13` at
  `09329821e2b13ebe066dc7c8d42b872afb789618`.
- Created and pushed `gate4/blocking-product-repairs` from that exact merge.
- Re-audited Gate 4 blockers: play-detail styling and obsolete utility removal
  are already resolved; player/team CSRN-logo fallbacks, duplicate import IDs,
  and missing roster-media visibility remained active.
- Removed the duplicate personnel-module school-import controls, added roster
  headshot/team fallback visibility and an explicit missing-headshot state,
  and introduced neutral player silhouette/monogram treatments.
- Added Gate 4 regression contracts for unique IDs, neutral identity fallback,
  roster media visibility, and the versioned silhouette asset.
- Passed 32 focused Gate 4 tests and all 1,225 authoritative repository tests
  locally on Python 3.13.14. The four previously recorded Pillow deprecation
  warnings remain non-blocking.
- Visual verification of the roster rows and player graphic fallbacks is the
  final acceptance step before the first Gate 4 checkpoint commit.
- Visual review confirmed player photos and neutral silhouette rendering, and
  exposed two follow-up defects: approved Caledonia branding was stored in
  `primary_logo` but not resolved by the preview, and narrow preview columns
  allowed position/number/details to overflow.
- Corrected the identity order to player photo, team logo, then silhouette.
  Team monograms are reserved for the separate team-logo/watermark treatment.
- Added `primary_logo` resolution and a compact two-column preview layout for
  constrained Command Center widths.
- Follow-up visual review showed the school list API omitted `primary_logo`
  even though the Caledonia asset and file route were valid. Added the approved
  logo fields to the school display payload.
- Moved the Player Preview below the Show/Update controls at full workspace
  width; the compact two-column treatment is now limited to phone-width views.
- Visual acceptance confirmed the full-width preview and approved team-logo
  fallback. Blank positions and explicit generic `Athlete` position values are
  standardized as `ATH` in both the Command Center preview and live overlay.
- Checkpointed and pushed the accepted identity/UI repairs on
  `gate4/blocking-product-repairs` at
  `977ffb9aa7526ac4a3d41388b3f31c13afbe36fc`; 39 focused tests and all 1,226
  authoritative tests passed on Python 3.13.14.
- Began the next Gate 4 repair set: fixed event-label contrast independent of
  team accent, explicit event/name/detail spacing, dynamic long-name fitting,
  play-detail containment, and invalid home/visitor logo hiding.
- Checkpointed and pushed that accepted event/media repair set at
  `222c85143c840b080d6ee9714076d3039b9dd52b`; 40 focused tests and all 1,227
  authoritative tests passed on Python 3.13.14.
- Gate 4 exit audit found and removed the overlay's transitional mutation
  observer: player portrait and watermark media now follow the required
  fallback order directly, without first assigning unrelated CSRN branding.

---

## 15. Copy-ready prompt for a new chat

Use this prompt when starting any new ChatGPT or Codex conversation:

```text
Continue the CSRN Production Suite using the living project Bible located at:

C:\Users\Darth\My Drive\CSRN\Development\CSRN-Production-Suite\CSRN_PROJECT_BIBLE.md

Read the entire Bible before recommending or changing anything. Treat it as the authoritative continuity and release-control document unless I explicitly change a decision.

Gate 1 source recovery and Gate 2 governance repair are complete. PR #88
passed final GitHub Actions run `30566281259` on Windows and Ubuntu and merged
into `develop-1.13` at
`ef9d4a5d11b7c0aa6535e501d0a6503907120f76`.

The active objective is Gate 3 on `gate3/reproducible-environment`: establish a
clean declared local development/test environment, separate setup/update from
normal startup, keep the full CI suite green, and add a deterministic build
command. Maintain canonical identity `1.13.0-alpha.8f` /
`V1.13A8F-SOURCE-ALIGNMENT`. Do not add product features, apply installer ZIPs,
or modify live runtime data.

Before acting, report:
1. the development folder you inspected;
2. the current Git branch and commit;
3. the worktree status;
4. the current release gate;
5. any discrepancy between the Bible and the repository.

Then proceed only within the next incomplete gate documented in the Bible.
```

---

## 16. Immediate next action

The next action is:

```text
Install Python 3.13.14 with `py install 3.13.14`. Then close CSRN and Python
processes, pause Google Drive sync, run
`SETUP_CSRN_DEVELOPMENT_ENVIRONMENT.bat`, and run the focused and full
validation suite before committing or pushing the Gate 3 repair.
```

Do not begin Gate 4 visual fixes or new features until Gate 3 passes Windows
and Ubuntu CI and merges into `develop-1.13`.
