# CSRN Production Suite — Project Bible

Document role: Living source of truth, continuity record, and new-chat handoff  
Product: CSRN Production Suite  
Primary release target: Finished Windows-hosted football broadcasting product  
Owner: Jason Chrest  
Last audited: 2026-07-30  
Current status: **GATE 6 ACTIVE — scorebug, ticker, runtime resilience, halftime, logo fallback, and legacy managed-logo URL slices accepted; final material-state visual matrix pending**

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

**Status: implementation complete; commit, push, CI, and merge pending.** Branch `gate5/frozen-football-scope` was created and pushed
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
- Sponsor Spotlight accepts active sponsors and their associated
  Sponsor-category image/video assets. Attaching media to a paid, active sponsor
  is the operator's assertion that the sponsor supplied or authorized it;
  `rights_status` remains useful documentation but does not block sponsor media
  from air.
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
- The existing Asset Manager now owns explicit placement roles:
  `flexible`, `sponsor_feature_still`, `sponsor_feature_video`,
  `lower_third_sponsor`, `scorebug_sponsor`, `player_highlight_video`, and
  `full_screen_master`. Existing records migrate to `flexible` so previously
  approved sponsor media remains usable.
- Asset records may be associated with a sponsor, roster, player, and season.
  Sponsor Spotlight accepts only flexible or feature-stage sponsor media and
  rejects an explicitly associated asset belonging to another sponsor.

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

Implementation status:

- Program Visual Controls now exposes Player Highlight separately from Player
  Spotlight, with roster, player, approved clip, detail, and 15/30/60/90-second
  cutoff controls.
- Only active, rights-approved `Player` + `Video` assets tagged
  `player_highlight_video` and compatible with the selected roster/player may
  reach air.
- The overlay uses the shared feature-stage geometry, places player information
  in the theme-aware top band, preserves video aspect ratio below it, and keeps
  the scorebug/ticker above the feature.
- Touchdowns generated during Player Highlight enter the existing queue and
  advance after hide, clear, or timed expiry. Player Highlight video remains
  muted until a separately validated OBS program-audio workflow is approved.
- Overlay schema revision `gate5-program-visual-v9` forces stale browser sources
  to reload this contract. Focused and authoritative validation remain required
  before this slice is committed or pushed.
- Player Highlight preparation is roster-owned: open a saved player and use the
  `Player Highlights` panel to name, describe, classify rights, and upload a
  clip. CSRN automatically creates the `Player` + `Video` asset, assigns
  `player_highlight_video`, and links the roster, player, and season. Asset
  Manager remains the advanced library rather than a required operator step.
- Roster and Asset Manager operate on the same asset record. `Remove from
  Player` clears the roster/player association while retaining the asset and
  file. `Delete Media` or Asset Manager deletion removes an unshared file only
  when it is inside CSRN-managed `/asset-files/` storage; external paths and
  media still referenced by another asset are retained.
- Asset Manager reports managed-media file count, total size, and orphan count.
  Replacing a managed upload also removes its superseded unshared file.
- Player Highlight preview and overlay video use an explicit 16:9 `contain`
  contract on a theme-backed stage. The complete source frame remains visible;
  it is never stretched or cropped to imitate sponsor banner artwork.
- The on-air `<video>` element itself is constrained to a 16:9 box rather than
  filling the wider feature-stage media region. This avoids OBS browser-engine
  differences in `object-fit` behavior and uses theme-backed side space when
  the protected-scorebug geometry is wider than the source clip.
- Overlay revision v9 derives explicit pixel width and height from the live
  feature-stage viewport and the clip's intrinsic dimensions. This prevents
  percentage-height/replaced-element layout differences from making the video
  taller than its clipped stage in OBS browser sources.

Validation evidence:

- Windows development runtime: Python 3.13.14.
- Focused roster-owned highlight and managed-media suite: 42 passed.
- Full authoritative suite: 1,250 passed with the four unchanged Pillow
  `Image.getdata()` deprecation warnings.
- Git diff and runtime identity checks passed.
- Player Highlight workflow checkpoint `8ad488164df65c488c93f08233e0f81199923517`
  is committed and pushed on `gate5/frozen-football-scope`. Operator review in
  OBS approved the complete 16:9 source frame, scorebug protection, and roster-
  owned preparation workflow. The Gate 5 branch remains intentionally unmerged.

#### Next Gate 5 implementation slice — game classification and record policy

The next frozen-football slice is broadcast planning metadata, not another
graphics feature. The current audit confirms that schools persist
`classification` and `region`, while a broadcast currently persists only one
general `classification`; it does not snapshot each team's classification,
region, overall record, or region record. It also has no structured region-game
flag, scrimmage/exhibition record rule, or special-game designation.

Preparation contract for the next slice:

- snapshot home and visitor classification and region when the broadcast is
  created so later school-database edits cannot rewrite archived game context;
- capture each team's pregame overall and region records as structured
  wins/losses/ties values;
- persist an explicit `region_game` flag rather than guessing solely from the
  two school records;
- persist a contest/record policy that distinguishes an official game from a
  scrimmage or exhibition and prevents non-official results from changing
  official records;
- allow multiple structured special-game designations, including Homecoming,
  Senior Night, rivalry, playoff, and championship;
- expose the fields in both Create Broadcast and Edit Broadcast, synchronize
  them into the active state, retain them in detail/archive records, and cover
  create/edit/load and legacy-record behavior with focused tests.

Authoritative record decision:

- wins, losses, and ties are supported across every sport;
- the broadcaster's configured primary team is tracked automatically from
  completed official CSRN broadcasts whether it appears as home or visitor;
- the operator enters each opponent's record entering the game because CSRN
  will not possess that opponent's complete schedule;
- the opponent record is a broadcast snapshot and is not retroactively changed;
- the primary team needs an operator-entered starting baseline when CSRN is
  adopted after its season has begun; and
- scrimmages and exhibitions never alter official overall or region records.

Implementation status:

- Create/Edit Broadcast now stores per-team classification and region snapshots,
  overall and region pregame records with wins/losses/ties, an explicit region-
  game flag, contest type, derived record policy, and multiple structured
  special-game designations.
- `broadcast_defaults.home_school_id` is the primary-team authority. The first
  official broadcast accepts an operator baseline; later broadcasts inherit the
  latest calculated postgame overall and region records whether the primary team
  appears as home or visitor. Opponent records remain manual snapshots.
- Completing an official broadcast advances only the primary team's record and
  supports wins, losses, and ties. Region records advance only for an explicitly
  marked region game. Scrimmages and exhibitions preserve the baseline.
- Broadcast load, active-state synchronization, reset, detail records, and
  archived records retain this planning context. Legacy records receive safe
  defaults without rewriting their stored school-era snapshots.

#### Approved refinement — scorebug record context and nonofficial clarity

- Scrimmage and exhibition planning now states explicitly that official overall
  and region win/loss/tie records will not be updated at completion.
- Nonofficial contests force `region_game` false in the interface, service, and
  active-state lifecycle; returning to Official Game re-enables the control but
  does not restore a stale checked value.
- The scorebug displays each team's persisted pregame overall record beneath
  the team name. For an official region game it appends the persisted region
  record in compact form; non-region and nonofficial contests omit the region
  segment. Legacy broadcasts without structured snapshots hide the record line,
  while an explicit 0-0 snapshot remains visible.
- This refinement is implemented but remains uncommitted pending focused/full
  validation and operator visual approval of compact and graphic scorebug modes.

#### Gate 5 final implementation acceptance

Gate 5 frozen-football implementation is accepted for branch closeout.

Final accepted behavior:

- broadcasts snapshot each team's classification, region, overall record, and
  region record so later School Database changes do not rewrite archived game
  context;
- wins, losses, and ties are represented structurally;
- official region games may advance the configured primary team's overall and
  region records;
- official non-region games may advance only the overall record;
- scrimmages and exhibitions force `region_game` to false and never advance
  official overall or region records;
- the operator warning states: "Official overall and region win/loss/tie
  records will not be updated when this game is completed.";
- multiple structured special-game designations persist through create, edit,
  load, active-state, detail, and archive workflows;
- the scorebug renders each team's persisted pregame overall record and adds
  the region record only for an official region game;
- zero ties are omitted from the compact scorebug string, explicit `0-0`
  records remain visible, and legacy broadcasts without structured record data
  do not display a fabricated record;
- overlay schema revision `gate5-program-visual-v10` refreshes stale OBS browser
  sources for the scorebug record contract.

Validation and operator evidence:

- Windows development runtime: Python 3.13.14;
- focused Gate 5 and state-route suite: 64 passed;
- full authoritative repository suite: 1,260 passed with the four unchanged
  Pillow `Image.getdata()` deprecation warnings;
- Create Broadcast, Edit Broadcast, active-state reload, and snapshot retention
  were manually accepted;
- official/nonofficial record messaging and Region Game disabling were accepted;
- compact scorebug record rendering was visually accepted without score or
  module alignment failure.

Gate 6 visual-regression item:

- move the scorebug record line below the mascot rather than between the team
  name and mascot, while preserving current score alignment, fixed scorebug
  height, long-name fitting, compact mode, and graphic mode.

Nonblocking follow-up risk:

- `tests/test_venue_repository.py::test_cache_invalidates_when_file_changes`
  can fail when run alone on the current Windows filesystem but passed in the
  final authoritative suite. Investigate file-change cache invalidation and
  timestamp-resolution assumptions before release freeze; this is not caused by
  the Gate 5 classification/record-policy changes.

Production-tree cleanup performed for this checkpoint:

- temporary `CSRN_GATE5_WORKTREE.zip` removed;
- repository-local pytest and Python cache directories removed outside `.venv`;
- no temporary patch archive is included in the commit;
- final untracked-file and diff-integrity checks are required before commit.
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

#### Gate 6 first implementation slice — scorebug identity hierarchy

Gate 6 begins from merged Gate 5 commit
`2124d6a2ca1c33944fc76f7ea85cc040f40e6362` on branch
`gate6/visual-regression`.

The first bounded visual-regression slice changes only the internal team-identity
hierarchy in the football scorebug:

- team name remains first;
- mascot appears directly beneath the team name;
- persisted pregame record appears beneath the mascot;
- an empty mascot or record collapses without reserving vertical space;
- compact scorebug geometry remains 484 / 174 / 484 pixels wide and 112 pixels
  high;
- graphic-mode geometry remains 738 / 248 / 738 pixels wide and 224 pixels
  high;
- score columns, center module, logos, possession treatment, ticker clearance,
  and Gate 5 record-policy formatting remain unchanged;
- overlay revision `gate6-visual-regression-v1` forces stale OBS browser sources
  to refresh the new hierarchy.

Acceptance requires focused and authoritative tests plus operator screenshots in
compact and graphic modes covering short and long names, long and missing
mascots, official region and non-region records, explicit 0-0, legacy missing
records, valid and missing logos, and both possession states. No commit or push
is allowed before visual approval.
#### Gate 6 slice 1 acceptance — scorebug identity hierarchy

The first Gate 6 visual-regression slice is accepted for branch checkpoint.

Accepted production behavior:

- the operational Graphic-mode scorebug now renders team name, mascot, then
  pregame record for both home and visitor;
- overall and region record display rules remain unchanged from Gate 5;
- score values, center game-status module, scorebug height, logos, possession
  indicators, and event ticker alignment remain unchanged;
- long school names and long mascot names remain readable in the supported
  Graphic-mode production path;
- empty mascot and legacy missing-record handling remain defensive automated
  behaviors and do not require operator screenshots because current production
  school records are expected to include mascots;
- overlay revision `gate6-visual-regression-v1` forces stale OBS browser sources
  to reload the revised hierarchy.

Validation evidence:

- focused Gate 6 suite: 18 passed;
- full authoritative suite: 1,265 passed with the four unchanged Pillow
  `Image.getdata()` deprecation warnings;
- Graphic-mode operator inspection approved the name/mascot/record ordering,
  fixed geometry, region-record visibility, and home/visitor possession states.

Deferred visual state:

- the smaller internal scorebug geometry is not an operator-accessible Compact
  mode today. Camera mode has not been implemented, so manual compact/camera
  visual approval is deferred until that workflow exists. Automated geometry
  tests continue to protect the dormant layout contract without treating it as
  a supported production state.

#### Gate 6 runtime repair — state polling and worker exhaustion

Scorebug/ticker visual review exposed a blocking runtime defect before the
remaining ticker matrix could be completed. With no browser clients open,
`/api/state` measured approximately 1.77–1.89 seconds while
`/api/security-status` remained near 15 milliseconds. During normal Command
Center and overlay polling, Waitress reported a growing task queue, the local
port remained open, and state requests stopped completing.

Root cause and approved repair scope:

- `StateService.load()` advanced a running clock and replaced the complete state
  file on every read; therefore each polling client continuously wrote state to
  synchronized storage;
- the overlay started `/api/state` every 300 milliseconds with `setInterval`,
  allowing requests to overlap when a response exceeded the interval;
- Command Center polling also lacked an in-flight guard and bounded timeout;
- running-clock reads must derive the visible clock without writing; explicit
  mutations remain responsible for persistence;
- overlay polling becomes completion-scheduled, single-flight, timeout-bounded,
  and backed off after failures;
- Command Center polling becomes single-flight and timeout-bounded;
- overlay revision `gate6-runtime-resilience-v1` refreshes stale browser sources;
- focused tests must prove repeated running-clock reads perform no repository
  replacements and both browser pollers reject overlap.

This repair is implemented locally but is not accepted, committed, or pushed.
Runtime latency, worker-queue stability, operator responsiveness, focused tests,
and the full authoritative suite must pass before ticker visual review resumes.


#### Gate 6 runtime acceptance and halftime/ticker refinement

Operator stability testing accepted the single-flight runtime repair under a
Command Center, overlay, and direct state-request workload:

- controls responded immediately;
- state changes appeared promptly on the overlay;
- no Waitress task-queue warnings occurred;
- no state requests failed; and
- measured loaded `/api/state` latency ranged from approximately 690 to 1,274
  milliseconds. Further latency optimization remains desirable, but bounded
  single-flight polling prevented worker exhaustion.

The same review identified two bounded presentation defects before scorebug and
ticker visual regression can close:

- entering halftime must keep the scorebug visible and replace the center game
  status with `HALFTIME`; clock and down/distance are suppressed in the overlay
  for halftime without destroying the underlying game fields, so normal status
  returns when halftime ends and the game advances to the third quarter;
- the Fast ticker preset increases from 126 to 189 pixels per second, exactly
  1.5 times the prior value; Very Slow, Slow, and Normal remain unchanged.

Overlay revision `gate6-runtime-resilience-v2` refreshes stale browser sources
for this presentation contract. This refinement is implemented locally and must
pass focused/full tests plus operator halftime and Fast ticker review before
commit or push.

#### Gate 6 runtime resilience and halftime/ticker acceptance

The runtime-resilience and remaining scorebug/ticker state slice is accepted.

Root cause and repair:

- `/api/state` previously advanced the running clock and wrote the complete state
  file on every read;
- Graphic overlay polling at 300 milliseconds and Command Center polling at 750
  milliseconds caused overlapping Google Drive-backed writes, Waitress worker
  exhaustion, queued requests, delayed operator actions, and apparent connection
  failures;
- state reads now advance the visible clock without replacing the persisted state
  file;
- Command Center and overlay polling are single-flight and use request timeouts;
- overlay failures use controlled retry/backoff rather than accumulating requests;
- no Waitress thread-count increase was used to mask the underlying defect.

Measured and operator-accepted behavior:

- unloaded `/api/state` latency improved from approximately 1.8 seconds to
  approximately 0.35-0.40 seconds;
- under the supported live Command Center and overlay load, controls remained
  responsive with no Waitress queue warnings, request failures, or unexpected
  connection-loss banner;
- quarter changes through Q1-Q4 and OT updated promptly;
- scorebug-only, ticker-only, both-visible, and both-hidden states worked;
- scorebug and ticker state changes appeared live without overlay refresh;
- runtime polling no longer exhausted the server worker pool.

Halftime presentation:

- entering halftime keeps the scorebug visible;
- the center status displays `HALFTIME`;
- clock and down/distance are suppressed during halftime;
- scores, team identities, records, possession treatment, and ticker remain
  visible;
- exiting halftime resumes Q3 and normal center-module presentation;
- halftime exit resets football field state to `1st & 10`.

Ticker speed:

- Very Slow, Slow, and Normal remain unchanged;
- Fast increases from 126 to 189 pixels per second, exactly 1.5 times the prior
  speed;
- operator review accepted Fast as visibly faster while still readable, with no
  overlap, blank loop, or visible jump.

Validation evidence:

- focused runtime, state, game-operations, and Gate 6 suites: 78 passed;
- full authoritative repository suite: 1,269 passed;
- the four existing Pillow `Image.getdata()` deprecation warnings remain
  unchanged;
- final live operator verification accepted halftime entry, Q3 `1st & 10`
  resume, ticker speed, runtime responsiveness, and queue stability.

This checkpoint does not claim that `/api/state` has reached its long-term
performance target. Further optimization may reduce loaded latency, but the
worker-exhaustion failure mode is corrected and the supported production path is
stable enough for continued Gate 6 visual-regression work.
#### Gate 6 logo fallback integrity slice

A visual-regression review found that some synthetic/test teams left the
scorebug logo column blank even though teams without any logo reference correctly
displayed a monogram. Caledonia's valid logo continued to render.

The confirmed presentation defect is the distinction between a missing logo
reference and a non-empty reference whose image cannot be loaded:

- a valid logo must render unchanged;
- a missing logo must render the existing team monogram;
- a stale, deleted, corrupt, unreadable, or otherwise broken logo reference must
  also render the team monogram rather than leaving a blank identity column;
- once a logo URL fails, the overlay must retain the fallback for that URL rather
  than retrying the broken file on every state poll;
- if the URL or team name later changes, the overlay may attempt the new logo or
  rebuild the correct monogram;
- this defensive overlay behavior does not replace the later data-integrity audit
  of why synthetic team records retained stale asset paths.

Overlay revision `gate6-logo-fallback-v1` refreshes OBS browser sources for this
contract. Acceptance requires automated coverage for valid, missing, and broken
logo states plus Graphic-mode operator verification that a broken test-team logo
degrades to a monogram while Caledonia's valid logo remains intact.
#### Gate 6 logo fallback integrity acceptance

The scorebug logo-fallback integrity slice is accepted for the supported Graphic
mode.

Operator verification confirmed:

- Caledonia's valid approved logo still renders normally;
- no duplicate monogram appears behind or over a valid logo;
- Northwood and Pine Valley no longer leave blank logo columns when their approved
  logo references fail to load;
- broken-logo states now render team monograms;
- teams with no logo reference continue to render monograms;
- no repeated broken-image flicker or repeated image-load failures were observed;
- the overlay retains fallback state for the same failed URL rather than retrying
  it on every state poll.

Automated validation:

- focused logo-fallback and identity-contract suite: 29 passed;
- full authoritative suite: 1,271 passed;
- the four existing Pillow `Image.getdata()` deprecation warnings remain
  unchanged.

A separate fixture asset-integrity defect remains documented and does not block
this slice:

- the Northwood and Pine Valley fixture records reference
  `assets/school-logos/<school-id>/logo.png`;
- both PNG files physically exist inside the fixture package and have normal file
  sizes;
- therefore the remaining defect is not missing or corrupt source files;
- the fixture import/runtime path translation is failing to convert fixture-relative
  logo paths into browser-served application asset URLs;
- a later asset-integrity slice must inspect fixture asset copy/remapping for
  school logos and confirm approved fixture logos render instead of requiring the
  defensive monogram fallback.

The fallback remains required for commercial resilience even after fixture path
remapping is corrected because deleted, moved, corrupt, or unreadable customer
assets must never leave blank broadcast identity columns.
#### Gate 6 legacy managed-logo URL normalization slice

Investigation of the Northwood and Pine Valley approved fixture logos disproved
the initial fixture-copy and Flask-route hypotheses:

- each runtime PNG exactly matches its fixture source by SHA-256;
- Pillow validates both runtime PNG files;
- each `/school-logos/<school-id>/logo.png` route returns HTTP 200,
  `image/png`, and the exact expected byte count;
- the School Database records contain browser-served absolute logo URLs;
- the persisted broadcast and embedded live-state snapshots contain the correct
  frozen logo identity, but legacy entries omit the leading slash:
  `school-logos/<school-id>/logo.png`;
- `StateService` correctly rejected those relative values as unsafe, causing
  `/api/state` to expose an empty `logo` while retaining
  `logo_certified: true`.

The approved repair is a compatibility normalization at the public-state media
boundary:

- known CSRN-managed legacy relative prefixes are converted to root-relative
  browser URLs;
- `school-logos/...`, `asset-files/...`, `roster-headshots/...`, and
  `personnel-headshots/...` become `/school-logos/...`, `/asset-files/...`,
  `/roster-headshots/...`, and `/personnel-headshots/...`;
- Windows separators in those known managed paths are normalized to `/`;
- arbitrary relative paths, traversal paths, and local filesystem paths remain
  blocked;
- current absolute URLs, data-image URLs, and HTTP(S) URLs remain unchanged;
- the persisted frozen broadcast snapshot is not rewritten and the current
  School Database is not consulted.

Acceptance requires automated proof that legacy managed logo URLs render through
public state, unsafe paths remain suppressed, certification metadata is
preserved, and public normalization does not mutate the frozen raw state.
#### Gate 6 legacy managed-logo URL normalization acceptance

The legacy managed-media URL normalization slice is accepted.

Operator verification confirmed:

- Northwood's approved logo renders from the frozen broadcast identity;
- Pine Valley's approved logo renders from the frozen broadcast identity;
- neither team displays the monogram fallback when its approved logo is
  available;
- no logo flicker or repeated image-load failures were observed.

The investigation established the final root cause:

- fixture source PNG files were present and valid;
- runtime PNG copies exactly matched their fixture sources by SHA-256;
- `/school-logos/<school-id>/logo.png` returned HTTP 200 with `image/png` and
  the correct byte count;
- School Database records contained valid root-relative URLs;
- older persisted broadcast snapshots stored otherwise-correct managed logo
  paths without the leading slash;
- `StateService` therefore suppressed them at the public-state safety boundary.

The accepted compatibility repair normalizes only known CSRN-managed legacy
relative prefixes at public-state publication. It does not rewrite the frozen
broadcast record, consult current School Database branding, or permit arbitrary
relative filesystem paths.

Automated validation completed with:

- focused state and Gate 6 suite: 39 passed;
- full authoritative suite: 1,274 passed;
- four unchanged Pillow `Image.getdata()` deprecation warnings.

Although the branch retains its original investigative name
`gate6/fixture-logo-remapping`, no fixture importer or asset-copy defect was
found and no fixture remapping code was added.
#### Gate 6 final material-state visual matrix

Gate 6 is not closed merely because the scorebug and runtime slices passed. The
formal Gate 6 exit condition remains approved evidence for every material
operator-accessible visual state.

Already accepted:

- Graphic-mode scorebug home/visitor identity hierarchy;
- overall/region records and possession states;
- Q1-Q4, overtime, and halftime center-module behavior;
- scorebug/ticker visible and hidden combinations;
- ticker live updates and speed presets;
- valid logo, missing-logo monogram, broken-logo monogram, and legacy managed
  logo URL recovery;
- loaded Command Center and overlay runtime stability without Waitress worker
  exhaustion.

Deferred because no supported operator workflow exists:

- dormant compact scorebug geometry;
- camera mode.

Remaining manual acceptance matrix:

1. Player graphic with a valid headshot.
2. Player graphic with missing headshot and correct team-logo fallback.
3. Touchdown player graphic.
4. Turnover player graphic.
5. Field-goal player graphic.
6. Player Spotlight card.
7. Player Highlight video.
8. Player of the Game graphic.
9. Lower third with short copy.
10. Lower third with intentionally long copy.
11. Sponsor Spotlight still image.
12. Sponsor Spotlight video, when a valid fixture video is available.
13. Sponsor missing/invalid creative containment.
14. Captions visible with short text.
15. Captions visible with long text.
16. Captions hidden.
17. Weather normal state.
18. Weather alert state.
19. Weather hidden state.
20. Social draft/card preview with no publication action.
21. Command Center phone-width control layout.
22. Overlay at the production browser-source resolution.

For each state, acceptance requires readable content, correct identity, no
overflow or clipping, no unintended overlap with scorebug/ticker, prompt live
updates, and no unexpected request or media-load errors.

Evidence is stored outside runtime/customer data under
`Documentation/Acceptance/Gate6`. Screenshots are documentation evidence only;
they must not include credentials, access tokens, private callback data, or
customer information.

No application redesign or new feature belongs in this slice. Any blocking
defect discovered during the matrix receives its own bounded repair, focused and
full tests, and operator retest before Gate 6 closes.
#### Gate 6 theme production-readiness slice

The existing Graphics Theme Service already provides eight original presets,
controlled overrides, generated shared CSS, non-persistent preview, activation,
saved variants, and an optional season lock. The production defect was operator
discovery and preview:

- the catalog showed only a small scorebug sample;
- Preview returned generated CSS but did not apply it to a representative stage;
- the operator could not compare lower third, player, sponsor, weather, and
  caption treatments before activation;
- category filtering and catalog search were absent;
- activation remained available without a deliberate preview-first workflow;
- advanced controls occupied the main workflow instead of remaining optional.

This slice replaces the Theme Manager presentation without changing the
underlying theme service contract:

- searchable, category-filtered catalog cards;
- explicit selected, previewed, and active states;
- a representative 16:9 preview stage;
- Scorebug, Lower Third, Player, Sponsor, Weather, and Captions preview tabs;
- generated preview CSS applied locally without changing live graphics;
- separate Preview Selected and Activate Selected actions;
- a warning before activating a theme that has not been previewed with the
  current overrides;
- visible production-coverage checks;
- advanced overrides, variants, and season lock retained in secondary panels;
- responsive single-column behavior at phone/tablet widths;
- safe escaping of catalog-supplied names and descriptions.

This is a production-readiness improvement to the existing theme engine, not a
new package format, customer theme importer, or multi-sport expansion. No theme
is activated by this implementation script. Operator visual acceptance and the
full automated suite are required before commit or push.
#### Gate 6 theme discovery and preview repair

Operator inspection found that the Theme Manager was not discoverable from the
Command Center, Settings retained a misleading editable legacy Theme field,
inactive preview panels remained stacked onscreen, and the representative
presets were not visually distinct enough to evaluate.

The repair adds direct Theme Manager access, read-only active Theme Engine status
in Settings, isolated preview tabs, a Restore CSRN Default action, and stronger
preset-specific preview treatments. No theme is activated by the repair script.
#### Gate 6 distinct commercial broadcast themes

Operator review rejected token-only theme variation. Commercial theme selection
must provide materially different broadcast identities rather than minor font,
radius, or shadow changes.

The production contract requires distinct retro, early-cable, modern,
minimal-radio, heritage, stadium, neon, and collegiate identities with
preset-specific geometry, border systems, surfaces, depth, typography, and
emphasis. The same identity rules apply to preview and live generated CSS.
Theme Manager is exposed in shared navigation, open overlays refresh theme CSS,
and Modern Network with no overrides remains the CSRN Default recovery point.

Team colors, logos, score alignment, safe areas, and data contracts remain
stable across every theme.
#### Gate 6 shared scorebug layout engine

Commercial-theme review established that token and surface changes were not
sufficient. The scorebug now uses bounded internal layouts while preserving its
external OBS anchor, maximum footprint, state behavior, logo bounds, text
containment, ticker relationship, and API contracts.

Each theme can reorder logo, team identity, score, and center information and
change internal module proportions. The Theme Manager scorebug preview uses the
same DOM class contract and generated CSS as the live overlay. Preview-only
theme impersonation rules were removed; the preview harness controls placement
only.

Other graphic families remain unchanged until the scorebug layouts receive
operator acceptance.

#### Gate 6 component-based scorebug theme engine

Operator review rejected the CSS-only layout experiment because it forced one
DOM structure into incompatible packages, caused preview compression and style
leakage, and did not produce truly distinct broadcast identities.

The replacement scorebug engine uses theme manifests plus a shared component
renderer. Each preset selects a distinct render tree assembled from reusable
team identity, logo, score, possession, clock, quarter, and down/distance
components. The production overlay and Theme Manager preview call the same
renderer.

The standard 1142x112 and graphic-mode 1724x224 outer footprints remain fixed.
Preview renders at production pixel dimensions and scales the completed result;
it never compresses internal columns. Existing runtime element IDs are
preserved for score updates, clock state, possession, logo fallback, records,
and operator controls.

Generated theme CSS remains responsible for skin tokens and materials. It no
longer defines scorebug structure. Other graphic families remain unchanged
until scorebug acceptance.

#### Gate 6 flagship scorebug package direction

The component renderer is retained, but the first package set is deliberately
redrawn for silhouette-level differentiation. Early Cable Sports is replaced
by **8-Bit Gameday**, an original pixel-grid sports HUD influenced broadly by
late-1980s and early-1990s console presentation without reproducing any game,
brand, proprietary artwork, or exact screen composition. Heritage Press Box is
refined into **Heritage Press**, using monochrome or restrained sepia sports-page
typography, newspaper rules, paper texture, and halftone character rather than
gold modern-network panels.

The primary layouts now differ structurally: Modern uses a three-piece network
bar; Classic uses five independent boxes; 8-Bit uses a self-contained arcade
HUD; Minimal uses two stacked information rows with a separate state rail;
Heritage Press uses a newspaper sheet; Stadium resembles a physical LED board;
Digital Neon uses opposing angular wings; and Collegiate uses framed crests and
a central institutional shield.

Preview CSS targets the generic renderer root so both `#scorebug` and
`#previewScorebug` receive the same package. A visible preview error state is
required; silent blank previews are prohibited.

#### Gate 6 scorebug parity and package refinement

Operator review accepted the component renderer direction but found live OBS
output diverged from Theme Manager previews. The renderer stylesheet is now
authoritative and loads after generated theme skin CSS in both contexts.
Generated skins may supply brand tokens, but they cannot override package
geometry or critical material treatment.

This refinement also establishes:

- Minimal Radio contains only team names, scores, quarter, clock, and
  down-and-distance. Logos, mascots, and records are suppressed.
- Friday Night Stadium renders as a physical high-school scoreboard with
  HOME/GUEST labels, LED scores, a dedicated time cell, quarter cell, and
  down/to-go rail.
- Digital Neon owns its dark/cyan game-state module and cannot inherit the
  Modern Network red center treatment.
- Pixel, Press, Minimal, Stadium, and Neon include explicit parity guards for
  their defining center and material systems.

Scorebug preview/live parity remains a manual acceptance requirement before
the theme renderer is extended to other graphic families.

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

Gates 1 through 4 are complete. Gate 4 merged through PR #90 at
`10afa40c99877dca9b4362a1ad4ef4c950db362d`. The active branch is
`gate5/frozen-football-scope`, based on committed head
`442f9e4438630f612d821729e5f6c0c897fc49b5`.

Gate 5 Program Visual Coordinator work is intentionally uncommitted pending
operator acceptance. The current slice adds Player Spotlight, Sponsor
Spotlight, queued touchdown handling, player-linked highlight video, explicit
asset placement roles, and a roster-owned Player Highlights workflow. The
roster workflow creates and links the Asset Manager record automatically;
unshared CSRN-managed media is deleted with its asset, while shared or external
media is retained. Highlight video must preserve the complete 16:9 frame above
the protected scorebug. Maintain canonical identity `1.13.0-alpha.8f` /
`V1.13A8F-SOURCE-ALIGNMENT`. Do not commit, push, or merge until the operator
visual check and validation checkpoint are accepted.

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
Launch CSRN, open Roster Engine, select a saved player, and exercise the new
Player Highlights panel with a test MP4 or WebM. Confirm that the clip appears
automatically in Program Visual Controls, preserves the full 16:9 source frame
above the scorebug, and that Remove from Player retains the Asset Manager record.
Then run `VALIDATE_CSRN_GATE_5_PLAYER_HIGHLIGHT_WORKFLOW.ps1` and return its
complete output before any commit or push.
```

After this slice is checkpointed, continue the frozen Gate 5 game-classification
and record-policy work documented above. Do not begin Gate 6 visual regression
until every Gate 5 frozen-football slice is complete.

#### Gate 6 halftime resume field normalization

Operator validation confirmed that the revised halftime presentation remains visible,
clearly displays `HALFTIME`, suppresses clock and down/distance presentation, resumes
Q3, and keeps the ticker responsive without Waitress queue warnings. One final state
normalization was required: ending halftime now begins the third quarter at `1st & 10`
instead of retaining the pre-halftime down and distance. Entering halftime still preserves
the underlying live-game fields until the explicit third-quarter resume transition.

### Gate 7 — Broadcast Layout Engine architecture foundation

Gate 6 proved that a theme cannot be reduced to colors, fonts, and a single
shared scorebug silhouette. The commercial product requires complete
**broadcast packages** whose component structure, screen position, safe zones,
collision behavior, and sport-specific information hierarchy may differ.

The Gate 7 architecture foundation is intentionally introduced in parallel
with the validated Gate 6 production renderer. Production OBS output is not
changed by this foundation slice.

The foundation establishes:

- a normalized broadcast-state contract shared by preview and live output;
- self-contained package manifests with package-owned scorebug, ticker,
  player-card, highlight, sponsor, and caption markup families;
- sport profiles for football, basketball, baseball, and softball;
- screen zones supporting top, bottom, corner, center, split, and stacked
  component placement;
- component-specific dimensions rather than treating an entire zone as a
  component rectangle;
- placement fallbacks and collision detection;
- presentation scenarios so graphics that are not intended to appear
  simultaneously are not forced onto the same canvas;
- package-level positioning for scorebug, ticker, player card, highlight
  video, sponsor panel, and captions;
- a standalone Layout Lab at `/static/csrn-layout-lab.html`;
- diagnostic outlines identifying component names, zones, and unresolved
  collisions;
- a 192-case package/sport/scenario runtime matrix;
- manifest validation and Chromium runtime smoke testing.

Migration policy:

1. Keep the Gate 6 renderer as the production fallback.
2. Validate the Broadcast Layout Engine independently.
3. Migrate Modern Network first.
4. Require Theme Manager, overlay preview, and OBS parity before migrating
   another package.
5. Migrate packages individually with rollback checkpoints.
6. Retire the Gate 6 renderer only after every production package passes.
7. Add complete baseball, softball, and basketball component families after
   the football package migration is stable.

This architecture treats each package as a production system rather than a
visual skin.

### Gate 7.1 — Scorebug Composer and sport-variant authoring

The isolated Broadcast Layout Lab now includes a scorebug-composer foundation. Package authors may select, drag, resize, save, reset, and export scorebug modules without altering the production overlay. Drafts are browser-local and keyed by package and sport.

Scorebug rendering now uses explicit home and visitor identity semantics instead of generic row reversal. Baseball and softball receive dedicated scorebug structures, Heritage Press receives a box-score treatment, Friday Night Stadium receives a ballpark board, and 8-Bit Gameday receives sport-owned decorative rails. Football, basketball, baseball, and softball decorations are no longer assumed to share a football field metaphor.

Production migration remains prohibited during this slice. The Gate 6 renderer remains the OBS and overlay fallback until an individual package and sport profile is visually accepted and frozen.

### Gate 7.2B — Cross-browser scorebug release candidate

Gate 7.2B stabilizes the isolated Broadcast Layout Lab after Windows Chromium
runtime validation exposed platform-sensitive module-boundary failures and a
composer canvas that could cover its inspector at narrow browser widths.

This checkpoint provides:

- sport-specific scorebug structures and package styling from Gate 7.2;
- fixed-footprint hardening for Modern, Digital Neon, Collegiate, Classic,
  Heritage Press, Minimal Radio, 8-Bit Gameday, and Friday Night Stadium;
- a cross-browser scorebug audit that keeps zero-size and material-overflow
  failures while treating minor clipped edges as diagnostic warnings;
- structural parent-module ownership for nested logo, identity, and score cells;
- explicit Digital Neon baseball and softball grid containment;
- constrained baseball-board children and game-state panels;
- a Layout Lab canvas that cannot cover the composer inspector;
- Layout Lab asset contract version 4 and engine version 1.2.0;
- a 192-case package, sport, and scenario browser matrix;
- multi-viewport composer visibility and selection validation.

The production overlay and OBS remain on the Gate 6 renderer. Gate 7.2B is an
isolated release candidate and may not be migrated into production until the
operator accepts the Layout Lab results.

### Gate 7.4 — Modern Network visual stabilization

Gate 7.4 is the first package-specific visual-polish checkpoint. It is limited
to Modern Network baseball and softball while preserving the accepted Modern
football and basketball renderer.

This checkpoint establishes:

- one complete, same-direction row for each baseball or softball team;
- explicit HOME and VISITOR row labels;
- a fixed RUNS cell owned by each team row;
- a separate fixed-width red inning, count, outs, and bases module;
- stable two- and three-digit score containment;
- long-name and no-logo containment;
- preserved football possession and basketball state contracts;
- Layout Lab asset contract version 6.

The production overlay and OBS path remain on the Gate 6 renderer. Modern
Network is not frozen until operator visual acceptance.

### Gate 7.4B — Modern sport-state panel refinement

Modern baseball and softball now use HOME and VISITOR labels inside their run
cells, role-aware pitcher and at-bat detail, a taller two-row panel, and a
lowered inning/count/bases module. Modern football restores the accepted CSRN
possession treatment: an outside-corner football plus a highlighted team panel.

The production overlay and OBS path remain on the Gate 6 renderer.

### Gate 7.5 — Modern Network final visual acceptance

Modern baseball and softball now use the approved row composition: run label and
score, team logo, team identity, and a dedicated role column for pitcher or
at-bat information. The inning state remains isolated in the red module.

The Layout Lab now exposes football possession and baseball/softball inning-half
controls, accepts explicit logo URLs, and attempts to load active team identity
from same-origin suite state endpoints while retaining initials as a fallback.

Modern football retains the accepted outside-corner football and active-team
highlight. The production overlay and OBS path remain on the Gate 6 renderer.

### Gate 7.6 — Modern Network final alignment

Modern baseball and softball now keep pitcher and at-bat information in the
same fixed role column, move HOME and VISITOR labels upward within the run
cells, and use the same yellow accent as the role labels. The red game-state
module remains a full-height right-side panel.

Modern football team logos are clipped into circular frames with a one-pixel
white border so rectangular image backgrounds cannot appear as black boxes.

The production overlay and OBS path remain on the Gate 6 renderer.

### Gate 7.7 — Modern Network freeze polish

Modern Network now uses a rounded-square glass logo treatment across football, basketball, baseball, and softball. Football and basketball use a narrower center game-state module so both team identity panels receive additional width. Baseball and softball retain the approved red state-module width while using the approved two-line inning/count alignment and a dedicated bases column.

Football possession highlighting resolves the possessing team's primary color, falls back to its secondary color when primary is black or near-black, and uses CSRN Scarlet when no usable team color exists.

The production overlay and OBS path remain on the Gate 6 renderer.

### Gate 7.8 R4 — Heritage Press design lab

Heritage Press uses independent football, basketball, baseball, and softball
Sport State Panel compositions in the isolated Broadcast Layout Lab.

The package uses warm paper, print texture, double rules, serif typography,
newspaper score rows, pull-quote captions, sports-wire ticker, framed sponsor
advertising, and editorial player cards.

Heritage retains the established Gate 7.7 engine and asset contract
(version 1.5.2 and asset query v=10). The diamond renderer also preserves the
legacy bl-press-boxscore compatibility class while using the new editorial
composition.

The internal package name remains available in Theme Manager and Layout Lab
controls but is not rendered inside broadcast graphics.

The production overlay and OBS path remain on the Gate 6 renderer.

### Gate 7.8 R6 — Heritage pseudo-element separation

Heritage Press inset newspaper frames now use ::after while Layout Lab
diagnostic labels retain exclusive use of ::before. This prevents the
diagnostic yellow label from inheriting the frame's inset geometry and
covering the broadcast component.

The diagnostic label is constrained to compact max-content width, and
Heritage content remains layered above the decorative frame. The production
overlay and OBS path remain on the Gate 6 renderer.

### Gate 7.9 — Heritage editorial system and wire ticker

Heritage Press baseball and softball now assign the pitcher to the defensive
team row and the batter to the offensive team row. Period-style line
illustrations identify each role.

Heritage-only team logos and player photography use monochrome print
treatment. Player-of-the-game modules use an early chewing-gum-card
composition with sport-specific game-stat fields.

The Heritage ticker now behaves as a newsroom wire: each queued story types
letter by letter, pauses, advances left, and begins the next story. Reduced
motion displays a complete static story.

Sponsor advertising restores a strong double-rule newspaper frame. Production
overlay and OBS remain on the Gate 6 renderer.

### Gate 7.10 — Heritage team-row alignment

Heritage football and basketball now share the accepted two-row geometry.
The home row is logo, left-aligned team information, score, then the shared
game-state column. The visitor row is score, right-aligned team information,
logo, then the same uninterrupted game-state column.

Heritage baseball and softball preserve the home-row direction while fully
mirroring the visitor row as score, batter/pitcher illustration and player
name, right-aligned team information, then logo.

Team records now share the HOME or VISITOR metadata line. Production overlay
and OBS remain on the Gate 6 renderer.

### Gate 7.11 — Heritage approved-layout rebuild

Heritage football and basketball use a fixed two-row team region with a
single uninterrupted game-data column occupying the complete right side.

Heritage baseball and softball use the approved mirrored visitor row:
score, vintage player illustration and player name, right-aligned team
information, then logo. The right-side inning, three-base indicator, and
balls/strikes/outs panel is fully contained.

Approved vintage pitcher and batter image assets are registered with the
layout engine and installed under static/heritage for program access.
Player and sponsor modules use the approved collectible-card and period-ad
compositions. Production overlay and OBS remain on the Gate 6 renderer.

### Gate 7.12 — Heritage final geometry polish

Heritage football and basketball now use a balanced three-column clock row,
centered score cells, vertically centered visitor identities, and a structured
foul display.

All Heritage sport-state panels are five percent taller. Baseball and softball
use the additional height to contain player-role labels and the complete
balls/strikes/outs row. The player-card header is reduced to one clean SPORTS
EXTRA line while retaining an accessible player-of-the-game label.

Production overlay and OBS remain on the Gate 6 renderer.

### Gate 7.13 — Heritage shared frame cleanup

The shared Heritage framing now terminates internal horizontal rules at the
eight-pixel inset editorial frame for football, basketball, baseball, and
softball. The separator before each home score and after each visitor score
is intentionally preserved.

No geometry, sizing, DOM, asset, player-card, sponsor, ticker, or production
overlay behavior changed.

### Gate 7.14 — Heritage inset-frame artifact removal

The redundant Heritage scorebug inset-frame pseudo-element was removed across
football, basketball, baseball, and softball. This eliminates the three
remaining exposed line fragments while retaining the real editorial border,
outline, box-shadow, and the approved home/visitor score separators.

No geometry, sizing, DOM, assets, cards, sponsors, ticker, or production
overlay behavior changed.

### Gate 7.15 — Heritage visitor score separator correction

The inherited border before each Heritage visitor score was removed across
football, basketball, baseball, and softball. The approved separator after
the visitor score remains, and the separator before the home score remains.

No other framing, geometry, sizing, DOM, asset, card, sponsor, ticker, or
production-overlay behavior changed.

### Gate 7.16 — Neon Sports Network Design Lab foundation

Digital Neon has been advanced into the Neon Sports Network design-lab package.
The package now provides team-aware cyan/magenta fallback accents, independent
football/basketball and baseball/softball scorebug compositions, glass logo
frames, possession emphasis, energy rails, sport-specific player statistics,
live ticker treatment, sponsor, captions, and highlight modules.

Motion is CSS-only and honors prefers-reduced-motion. Production overlay and
OBS remain isolated on the Gate 6 renderer. The internal package name is not
rendered inside broadcast graphics.

### Gate 7.19 — Neon future-broadcast composition

Neon Sports Network now owns a full-width top scoreboard lane across football,
basketball, baseball, and softball. Football possession is represented by a
glowing football marker attached to the team currently possessing the ball.
Diamond sports use a horizontal future-broadcast architecture rather than the
Modern or Heritage two-row scorebug.

Team names use neon-sign glow, the ticker reserves an independent LIVE capsule,
captions move below the top scoreboard, and Neon diagnostic/collision outlines
are suppressed so the broadcast design remains visible during Layout Lab review.

Production overlay and OBS remain isolated on the Gate 6 renderer.

### Gate 7.20 — Neon-native composition rebuild

Neon Sports Network no longer attempts to skin shared Modern or Heritage
scorebug markup. It owns a dedicated three-module scorebug DOM, independent
team shells, a central command core, responsive team-name sizing, logo halos,
mascot neon treatment, and an inline SVG football possession emitter.

Baseball and softball use the same native future-broadcast architecture with a
diamond-state command core rather than inherited two-row layouts. Player,
highlight, ticker, sponsor, and caption components also own dedicated Neon
shells and nested contours.

The Layout Lab remains isolated from the Gate 6 production renderer and OBS.

### Gate 7.21 — Neon five-zone scorebug rebuild

The Neon scorebug now uses five independent visual zones: home identity, home
score bay, command core, visitor score bay, and visitor identity. Scores are no
longer embedded inside the identity wings. Each score bay owns an illuminated
angular shell, and football possession is integrated beneath the score bay for
the team currently possessing the ball.

Captions are positioned directly above the ticker with a controlled separation.
Production overlay and OBS remain isolated on Gate 6.


### Gate 7.22 — Team-adaptive Neon visual fidelity

The Neon Sports Network package now derives primary and secondary lighting from each team, deepens all five scorebug zones with layered glass and interlocking bevels, strengthens logo and score illumination, and preserves the dedicated Gate 7.21 structure. Baseball occupied-base indicators use electric blue; softball occupied-base indicators use pink/magenta. Motion is subtle and disabled when reduced motion is requested. Production overlay and OBS remain on Gate 6.

### Gate 7.23 — Neon Broadcast Package geometry engine

Neon is now treated as a dedicated broadcast package rather than a shared-theme
skin. The existing five-zone functional contract remains intact, while the
visual renderer uses interlocking identity pods, floating score crystals, a
command cockpit, continuous team-driven energy rails, layered glass, restrained
motion, and root-level home/visitor lighting variables.

Football possession remains attached to the team currently possessing the ball.
Baseball occupied bases use electric blue neon, and softball occupied bases use
pink/magenta neon. Reduced-motion preferences disable package animation.
Production overlay and OBS remain isolated on Gate 6.


## Gate 7.24 — Neon Concept-Fidelity Composition

Gate 7.24 preserves the Gate 7.23 five-zone renderer and applies the approved
heavy chrome/glass broadcast-package material language. It enlarges logos and
mascot typography, deepens identity pods, score crystals, and the central
command cockpit, replaces the moving identity highlight with a stationary
ambient reflection, and carries the same material treatment into shared
components and the ticker. Baseball occupied bases remain electric cyan;
softball occupied bases remain hot pink. Production overlay and OBS remain on
Gate 6.


## Gate 7.25 — Neon Approved Concept Chassis Fidelity

Gate 7.25 is a visual-only convergence pass over the stable Gate 7.24 package.
It increases separation between identity pods, score crystals, and the command
cockpit; strengthens team-primary and team-secondary lighting; enlarges logo
chambers; raises mascot typography to broadcast-readable size; deepens the
industrial chrome/glass materials; and binds the five zones with continuous
team-driven rails. The moving identity highlight remains disabled. Baseball
occupied bases remain electric cyan and softball occupied bases remain hot
pink. Production overlay and OBS remain on Gate 6.


## Gate 8.0 — Neon Rendering Engine v1

Gate 8.0 introduces a dedicated material and instrument rendering layer over
the stable Gate 7.25 R2 five-zone composition. It does not change placement,
production overlay, or OBS contracts. The renderer adds interlocking chassis
cuts, optical score crystals, powered logo chambers, deeper chrome/glass
materials, sport-specific command instrumentation, unified CAD-like component
frames, and restrained non-translational power pulsing. Baseball occupied bases
remain electric cyan and softball occupied bases remain hot pink.


## Gate 8.1 — Neon Vector Chassis Asset Renderer

Gate 8.1 introduces the first reusable vector geometry asset library for the
Neon broadcast package. Identity pods, score crystals, the command cockpit,
logo chambers, the continuous chassis spine, and shared component frames are
now supplied by standalone SVG alpha masks in `static/neon/`. CSS recolors the
assets from each team's palette, while the HTML layer remains responsible only
for live data and instruments. This replaces the previous attempt to derive the
approved concept solely from rectangular HTML shells and CSS clip paths.
Production overlay and OBS remain on Gate 6.


## Gate 8.2 — Neon Scorebug Asset Fidelity

Gate 8.2 freezes shared components and concentrates exclusively on matching the
approved top scorebug. It corrects the SVG alpha-mask construction introduced
in Gate 8.1: black shapes in alpha masks were still opaque and produced broad
white connector slabs. The replacement assets use transparent even-odd frame
geometry. This pass also deepens score crystals, enlarges logos, strengthens
team and mascot hierarchy, and introduces sport-specific football and
baseball/softball cockpit composition. Production overlay and OBS remain on
Gate 6.


## Gate 9.0 — Neon True Chassis Compositor

Gate 9.0 replaces the visual composition model rather than adding another skin.
The Neon scorebug now renders seven independent structural pieces: a home logo
endcap, home identity wing, home score crystal, sport command cockpit, visitor
score crystal, visitor identity wing, and visitor logo endcap. Dedicated v2 SVG
assets define each piece. Existing class names remain on the new elements only
to preserve runtime and test compatibility. The data model, package selection,
placement engine, production overlay, and OBS contracts are unchanged.

## Gate 9.1 — Approved Concept Visual Convergence

Gate 9.1 preserves the validated seven-piece compositor and frozen 1840×220
runtime footprint while replacing the visually rectangular Gate 9.0 treatment
with a compact, interlocking chassis modeled on the approved Neon Sports
Network concept. Logo chambers are larger, identity wings are shorter and
tapered, score crystals face inward, and the command cockpit is narrowed into
an hourglass instrument module. White/silver slab gradients no longer dominate
the frame; home and visitor energy colors now carry their respective halves and
meet through a neutral center bridge. Football, basketball, baseball, and
softball retain independent state contracts, including blue occupied baseball
bases and pink occupied softball bases. Production overlay and OBS remain on
Gate 6. No production migration is authorized by this gate.

## Gate 10.0 — Approved Concept System Rebuild

Gate 10.0 replaces the 220 px Layout Lab scorebug constraint with a 1,840×270
approved-concept proportion. The scorebug remains a seven-piece, sport-aware
renderer, but its dark chassis, colored rim lights, integrated logo chambers,
identity fields, score crystals, and command cockpit are now designed as one
broadcast instrument instead of adjacent colored panels. The support modules
are rebuilt as a separate cyan/violet/magenta Neon system: dark player, replay,
sponsor, caption, and ticker frames never use the two competing teams as a
broad gradient. The player renderer now accepts `player.headshot`; where no
headshot is supplied, it deliberately renders a neutral silhouette portrait
bay. Football, basketball, baseball, and softball contracts remain intact,
including football possession and the independent blue baseball / pink softball
occupied-base indicators. Production overlay and OBS remain on Gate 6.

## Gate 11.0 — Isolated Approved-Concept Renderer

Gate 11.0 stops the cumulative Neon override chain. The Layout Lab manifest now
mounts Neon with the dedicated `package-neon-approved` root, so the eighteen
historical `.package-neon` styling generations cannot participate in the final
render. The validated placement engine and seven-piece semantic DOM remain in
service, while one isolated renderer owns the complete visual result.

The primary scorebug uses the approved 1,840×250 proportion and a fixed
200/350/190/360/190/350/200 grid: integrated logo chambers, readable identity
wings, inward-facing score crystals, and one sport-specific command cockpit.
Dark glass and near-black chassis surfaces carry the system; display-safe home
blue and visitor green appear as energy edges, glow channels, and instrument
accents instead of broad color slabs. Football includes game clock, quarter,
down-and-distance, possession, and play clock; basketball substitutes shot
clock; baseball and softball expose inning/half, count, outs, and occupied-base
state with their independent cyan and magenta base indicators.

Player, highlight, sponsor, caption, and ticker modules share a separate dark
cyan/magenta system frame. Player cards retain the headshot-ready portrait bay,
and sponsor cards accept an image logo while preserving a readable text
fallback. Layout Lab fixtures are sport-aware rather than reusing football copy
for every sport. Gate acceptance requires all 192 runtime combinations, exact
lane separation, full Python coverage, and Windows Chromium pixel checks that
reject washed-out support surfaces or missing scorebug energy. Production
overlay and OBS remain on Gate 6; Gate 11.0 authorizes no production migration.

## Gate 11.1 — Approved-Concept Clarity and Team Energy

Gate 11.1 preserves the Gate 11.0 renderer, seven-piece DOM, 1,840×250
scorebug, placement geometry, sport contracts, and production isolation. It is
a visual clarity refinement based on rendered Layout Lab acceptance images.
The team-name, score, and game-clock treatments now keep solid glyph interiors
and dark anchoring shadows while limiting neon bloom to a restrained outer
edge. Continuous top and bottom chassis rails are suppressed so the seven
directional pieces retain clean individual silhouettes without bright bars
crossing their joints.

Player, highlight, sponsor, caption, and ticker renderers now receive the same
display-safe home and visitor palette used by the scorebug. Their interiors
remain near-black; team colors are restricted to frame edges, instrument
details, labels, and low-intensity ambient energy. Left-side player treatment
is home-led, right-side highlight and sponsor treatment is visitor-led, and
full-width caption/ticker treatments carry both teams from left to right.
Production overlay and OBS remain on Gate 6; Gate 11.1 authorizes no production
migration.
### Gate 11.2 — Approved-concept closeout cockpit cleanup

Gate 11.2 removes the redundant luminous chassis asset layered over the Neon
command cockpit while retaining the single dark, shaped information shell. The
approved Neon renderer no longer emits play-clock or shot-clock elements. Team
records, baseball/softball inning and count state, and football possession text
are enlarged by 75 percent, with the reclaimed cockpit space assigned to the
period and primary game clock. Production overlay and OBS remain on Gate 6.

### Gate 11.3 — Final center boundary and support-copy legibility

Gate 11.3 removes the remaining rectangular cyan command-core boundary at the
section, diagnostic, and inner-shell levels. Player and highlight descriptive
copy is enlarged by 50 percent. Player-stat labels and values are enlarged by
75 percent while retaining the four-column stat grid. Scorebug geometry,
component placement, team-energy propagation, production overlay, and OBS
isolation remain unchanged.

### Gate 11.4 — Remove the command-core module boundary completely

The approved Neon command core is display-only and no longer participates in
the Layout Lab editable-module boundary system. The outer command section and
its inner game-state content omit `data-module="game.state"`, preventing the
Lab from painting a rectangular selection or module boundary around the center
cockpit. Live game bindings, sport state, seven-piece geometry, diagnostics,
and production isolation remain intact.

Deferred multi-sport requirement: when CSRN resumes expansion and refinement of
the baseball and softball packages, add explicit current **At Bat** and
**Pitcher** identities to their live scorebug/state presentation. This is a
required future correction, not part of the Gate 11 Neon closeout scope.

### Gate 11.5 — Final phantom-glow removal

The approved Neon command core, its pseudo-elements, its direct core shell, and
the direct `.bl-neon-state` / sport-state child must not render a border,
outline, box shadow, or filter. This explicit child-state rule prevents the
legacy `.bl-neon-state` border and 22-pixel cyan box shadow from leaking into
the approved renderer. Internal clock, period, down-and-distance, possession,
inning/count, and base-state illumination remains intact. Gate 11.5 R3 is the
final pre-freeze Neon visual baseline.

### Gate 11.6 — Neon Sports Network visual freeze

The Neon Sports Network package is visually approved and frozen from the
installed Gate 11.5 R3 baseline. Its approved renderer geometry, scorebug,
sport-state presentation, support modules, typography, team-energy behavior,
and phantom-glow correction must not change during work on another package.

Frozen renderer fingerprints (re-pinned 2026-08-31, Round 9 — the shared
`csrn-broadcast-layout-engine.*` was intentionally rebuilt after this freeze:
Neon was disabled as a selectable production-template option in Round 6, and
the shared engine was extended for the "Collegiate Tech" package series. This
is an authorized re-pin of the fingerprints to the shipped bytes; no Neon
renderer behaviour was changed in Round 9. Prior fingerprints:
`4641A675512EA8C92E1408E421B690F862B49EA509D1009903A5F0B5EFB655EF` /
`961E39C83C94C1F12194E2D984247E576E96916FB8E5D35BBEC77EFF5B5EA68D`):

- `static/csrn-broadcast-layout-engine.css`: `822755B7ABBA1F6D7439246904DB3AAEEFDE9649C617461457B73053672A02C9`
- `static/csrn-broadcast-layout-engine.js`: `CE29D87BCB4DE6F5E21F00B8F61DBA76F18ABB5C340D2D5DF165BF8A6CD3B2A2`

Future Neon changes require an explicit unfreeze decision, a new isolated
checkpoint, visual comparison against the approved concept, the complete
192-case runtime matrix, and full-suite regression approval. The deferred
baseball/softball **At Bat** and **Pitcher** requirement remains recorded but
does not authorize changes while Neon is frozen. Production overlay and OBS
remain on Gate 6.

### Gate 12.0 — Friday Night Stadium approved system contract

Friday Night Stadium is approved as a separate, full-display broadcast system,
not as a conventional compact scorebug and not as an extension of the frozen
Neon renderer. Its isolated engine shadows the earlier Layout Lab placeholder
package while leaving the Gate 11.6 Neon files and the Gate 6 production/OBS
overlay untouched.

The 1,920×1,080 composition reserves a full-width LED ticker at the top, a
physical stadium-scoreboard cabinet across nearly the entire remaining display,
and a protected caption lane at the lowest broadcast-safe position. The cabinet
is home-team controlled and carries a venue plaque. The plaque may combine the
school and mascot only when the combined identity fits its approved character
budget; otherwise it uses the school name alone. Visitor is always presented on
the left and Home on the right.

Only the large central video-board opening changes content. The outer cabinet,
team score towers, sport instruments, and sponsor rail stay on screen when the
video board switches from the default team-clash presentation to a highlight,
sponsor, player, or broadcast-video presentation. The default clash uses the
available team names, mascots, and logos but is expected to vary from the concept
when real logo proportions differ. This logo variation is the only approved
concept exception.

The engine owns deterministic 5×7 LED glyph geometry instead of relying on an
operating-system approximation of a scoreboard font. Football exposes score,
game clock, quarter, down and distance, possession, and timeouts. Basketball
uses its own instrument row for score, game clock, period, possession, fouls,
bonus, and timeouts; each basketball score is a fixed-width three-digit field
that cannot shrink or reflow at 100–999. Baseball and softball use a materially
different line-score layout with runs, hits, errors, inning/half, balls, strikes,
outs, occupied bases, and explicit **At Bat** and **Pitcher** identities.

Gate 12 acceptance requires all four sport structures, all six Layout Lab
presentation scenarios, central-only video replacement, collision-free ticker
and caption lanes, long-name and missing-logo stress cases, deterministic LED
markup, frozen-Neon fingerprint verification, JavaScript syntax validation,
Chromium DOM and screenshot inspection, and the full authoritative Python suite.
No production migration is authorized by this gate.

### Gate 12.4 — Sport environment and diamond R/H/E contract

- Friday Night Stadium clash mode uses four immutable photographic environment plates beneath the separately composited, runtime-recolored athlete layer.
- Football uses a night football field and football-specific tower lighting. Basketball uses an indoor hardwood gym with ceiling illumination only—never outdoor stadium lights or floodlight towers.
- Baseball uses a blue-hour baseball diamond with slender outfield ballpark poles. Softball uses a distinct compact golden-hour softball park with a visible pitching circle, yellow-topped fence, and its own lighting treatment.
- The environmental plates never contain athletes, team marks, captions, sponsor copy, or the VS asset. Those remain independent presentation layers so every non-clash video mode can replace the video-board opening cleanly.
- Baseball and softball R/H/E strips are removed from the score towers and occupy the left and right sides of the lower diamond control bank around the centered inning and bases instruments.
- Gate 12.4 preserves the Gate 12.3 athlete masters, shading-preserving runtime uniform recoloring, corrected softball pitcher orientation, reduced side logos, frozen Neon renderer, and Gate 6 production isolation.
- No production migration is authorized by this gate.

### Gate 12.5 — Friday Night Stadium freeze-candidate instrument contract

- Baseball and softball retain conventional R/H/E labels, but every R/H/E value is rendered through the same deterministic dot-matrix LED glyph engine as the other scoreboard numbers.
- The word `BASES` is removed. The three-base occupancy instrument is centered horizontally and vertically in its existing control-bank compartment.
- Football spells `QUARTER` in full. `DOWN`, `TO GO`, `BALL ON`, and `QUARTER` labels are enlarged approximately 75 percent from the Gate 12.4 compact scale.
- Baseball and softball `BALLS`, `STRIKES`, and `OUTS` labels are enlarged approximately 75 percent. Basketball `FOULS`, `BONUS`, `TIMEOUTS`, and `DOUBLE BONUS` labels are enlarged approximately 50 percent.
- The larger labels must remain single-line, centered, and contained at 1920×1080 without changing the approved cabinet, video-board opening, sport backgrounds, athlete compositor, ticker, or caption geometry.
- Gate 12.5 is the Friday Night Stadium freeze candidate. Freeze authorization occurs only after user visual acceptance; production overlay and OBS remain isolated on Gate 6.

### Gate 12.6 — Friday Night Stadium visual freeze contract

- User visual acceptance of Gate 12.5 authorizes the Friday Night Stadium freeze. The eleven frozen renderer and artwork files are the stadium JavaScript engine, stadium stylesheet, silver lightning VS asset, four keyed athlete masters, and four sport environment plates.
- Every frozen file is protected by an authoritative SHA-256 contract. Any byte change fails the suite and is prohibited unless a later installer is explicitly designated as an explicit user-authorized unfreeze gate.
- Re-pinned 2026-08-31 (Round 9): `csrn-friday-night-stadium-engine.js` / `.css` were rebuilt for the "Collegiate Tech" package series and commit `9064c67` ("Friday Night Stadium test broadcast readiness"). The SHA-256 contract in `tests/test_gate126_friday_night_stadium_visual_freeze.py` was re-pinned to the shipped bytes for those two files; the nine artwork fingerprints are unchanged. No renderer behaviour was changed in Round 9.
- The approved frozen behavior includes all four full-display sport cabinets, top ticker, video-board-owned captions, five video modes, sport-specific backgrounds, runtime team-color athlete uniforms, corrected softball pitcher orientation, LED R/H/E, centered unlabeled base occupancy, full `QUARTER` wording, and the accepted sport label scales.
- Layout Lab must load the frozen stadium engine and stylesheet once each at asset query `v=12.6`. The shared Layout Lab may evolve for other packages only while this route and all frozen hashes remain intact.
- Friday Night Stadium remains a Layout Lab package. Production overlay and OBS remain on Gate 6; this freeze does not authorize production migration.

### Gate 12.1 — Friday Night Stadium fit-and-finish contract

- The complete physical cabinet, including every sport control bank, must remain inside the 1920×1080 broadcast canvas without bottom clipping.
- Captions belong inside the central video-board opening. They overlay its lower edge on a translucent, shadowed non-LED plate in clash, highlight, sponsor, player, and broadcast modes; they do not create a separate bottom-lane component.
- Football timeout indicators are compact cabinet instruments. They may not displace the clock, state, or down-distance row.
- Basketball retains fixed-width three-digit scores and moves both team logos fully above the lower control deck.
- Baseball and softball use a compressed R/H/E bank, place the base diamond beside the inning display, keep At Bat and Pitcher in the upper control tier, and reserve the shorter lower tier for Balls, Strikes, and Outs.
- The clash screen vertically raises both team marks and uses the transparent silver lightning `VS` asset at `static/friday-night-stadium/vs-lightning-silver.png`; typed VS text is not an approved substitute.
- Cabinet plates use layered brushed-metal gradients and inset edge highlights while LED wells remain dark.
- Gate 11.6 Neon remains frozen, and this gate does not authorize production-overlay or OBS migration.

### Gate 12.2 — Sport clash presentation and scoreboard rebalancing contract

- The Gate 12.1 physical cabinet, in-video captions, metallic treatment, and central-only replacement behavior remain the canonical baseline.
- Football removes timeout tracking and duplicate plain-text quarter/down-distance. Its clock is centered under the video board, possession moves beneath the active team score with a football marker, and the lower LED bank remains the single authoritative quarter/down/distance display.
- Basketball moves possession beneath the active team score with a basketball marker. Visitor timeouts read inward as `TIMEOUTS ○ ○ ○ ○`; Home timeouts mirror as `○ ○ ○ ○ TIMEOUTS`.
- Baseball and softball move **At Bat** and **Pitcher** into their corresponding team score towers. The compact R/H/E banks remain between score and identity space, and inning plus bases share the center instrument.
- Clash mode is sport-owned artwork: football uses a marked field and opposing football athletes; basketball uses a restrained hardwood court with a visitor defender and home shooter; baseball and softball use a diamond with a visitor batter and home pitcher. Baseball athletes are male-presenting and softball athletes are female-presenting.
- Clash athletes are project-owned inline vector art whose uniforms inherit the current team palettes. The silver lightning VS asset remains centered at approximately two-and-one-half times its Gate 12.1 size. Side-tower team logos remain visible and are not duplicated in the clash opening.
- Highlight, sponsor, player, and broadcast modes continue to replace only the central video-board opening. Gate 11.6 Neon remains frozen, and no production-overlay or OBS migration is authorized.

### Gate 12.3 — Layered athlete compositor contract

- The temporary geometric SVG athletes are retired. Football, basketball, baseball, and softball clash presentations use approved high-detail transparent raster masters with realistic anatomy, sport equipment, and opposing poses.
- Each master carries two controlled uniform keys. The canvas compositor replaces the visitor cyan key and Home magenta key with the current teams' display colors while retaining source luminance, fabric folds, painted shadows, highlights, skin, equipment, and outlines.
- Football uses a ball carrier and defender; basketball uses a defender and jump shooter; baseball uses a male batter and pitcher; softball uses a female batter and a female fastpitch pitcher whose delivery is directed toward the batter.
- Basketball does not display a possession-ball icon. Football retains its possession football below the active score.
- Side-tower logos are rendered at ninety percent of their Gate 12.2 size so every real-world logo remains contained within its window.
- The keyed masters are immutable project assets. Runtime presentation may recolor uniform material, but it may not redraw, simplify, or substitute the approved athletes.
- Gate 12.2 remains the rollback baseline. Frozen Neon and the Gate 6 production overlay remain untouched, and no OBS migration is authorized.

### Gate 13.0 — 8-Bit Gameday approved system contract

8-Bit Gameday is an isolated full-display renderer inspired by an original,
premium late-1980s sports game that never reached production. It does not
reuse the frozen Neon or Friday Night Stadium renderers. Its visual language is
crisp pixel geometry, dark CRT/LED wells, hard-edged metallic cabinet pieces,
deterministic 5×7 dot-matrix numbers, restrained team-color illumination, and
no modern blur-based glass or bloom.

The 1,920×1,080 presentation reserves a full-width out-of-town ticker above a
single physical arcade-scoreboard cabinet. The cabinet has a press-box and
stadium-light topper with the fixed `CSRN / 8-BIT GAMEDAY` brand plate,
visitor tower on the left, Home tower on the right, a
large central video-board opening, and a sport-owned instrument bank. Only the
central opening changes among **Clash**, **Highlight**, **Sponsor**, **Player**,
and **Broadcast** modes. Captions are an opaque-enough, shadowed overlay at the
bottom of that opening in every mode.

Football, basketball, baseball, and softball are separate structures:

- Football has logo-free helmet emblems, fixed player numbers, a pixel night
  field, game clock, quarter, down, to-go, ball-on, and football possession.
  Football does not track or display timeouts.
- Basketball has logo-free basketball emblems, fixed player numbers, a quiet
  hardwood court without stadium-light clutter, three-digit scores, clock,
  period, fouls, bonus, mirrored timeouts, and no basketball possession icon.
- Baseball and softball share the approved diamond scoreboard architecture but
  retain sport-specific athletes. Both expose score, R/H/E, inning/half,
  occupied bases, balls, strikes, outs, At Bat, and Pitcher. Softball uses a
  female-presenting batter and pitcher; baseball uses male-presenting athletes.

Clash athletes are project-owned transparent pixel-art raster masters with
fixed anatomy, equipment, racial diversity, sport-specific poses, and jersey
numbers. Football, basketball, baseball, and softball each own a separate
master. An awaited canvas compositor decomposes the keyed uniform pixels into
visitor/Home primary and secondary materials. Dark fabric folds are rebuilt as
neutral charcoal/black/gray and highlights as neutral light gray/white before
the live team colors are applied; generated blue, cyan, pink, or magenta shadow
hues may not survive into the completed canvas. The engine does not require a
separate raster image for every school color.

Each sport also owns an immutable clash-only environment plate. Football uses
a high-school night field with aluminum bleachers, a modest press box, and
community-field light poles. Basketball uses an indoor hardwood gym with only
ceiling-mounted illumination. Baseball uses a blue-hour traditional ballpark
with narrow baseball light poles. Softball uses a compact golden-hour park with
a pitching circle and open foul-territory edges rather than foreground dugout
boxes. These plates, the athletes, and VS disappear together whenever the
central opening switches to Highlight, Sponsor, Player, or Broadcast mode.
Team logos are intentionally omitted from this package. A large project-owned
silver lightning VS remains independent of the uniforms and environments, so
all layers retain their approved contrast under arbitrary team colors.

Gate 13 acceptance requires all four sport cabinets, five video modes, all
existing Layout Lab scenarios, long identities, three-digit basketball scores,
dynamic primary/secondary uniform colors, captions contained in the video
opening, JavaScript syntax validation, Chromium DOM and screenshot inspection,
and the full authoritative Python suite. Gate 11.6 Neon and Gate 12.6 Friday
Night Stadium remain frozen. Production overlay and OBS remain on Gate 6; this
gate authorizes no production migration.

### Gate 13.2 — approved baseball-family pixel cabinet correction

The approved football concept image is the canonical cabinet reference for the
8-Bit Gameday family. The renderer uses chunky stepped silver/white rails, a
pixel-stadium press-box and light-tower topper, large team-owned side towers,
bright readable score digits, a dominant central video opening, and large
modular bottom instruments. Football uses helmet emblems in its side towers.
Basketball and both diamond sports keep their separate instruments and sport
art while following the same cabinet family.

Saturated keyed athlete pixels remain live team colors even at high source
brightness. Only genuinely dark keyed folds become neutral grayscale; existing
low-saturation white/gray highlights remain untouched. The prior rule that
converted all high-value keyed pixels to white is rejected because it erased
the team colors and made uniform numbers difficult to read.

### Gate 13.3 — generated approved-concept cabinet correction

The CSS-built nested rails are retired. A project-owned transparent pixel-art
cabinet plate, generated directly from the user-approved football concept,
owns the press box, high-school stadium light towers, chunky silver structure,
side tower openings, central video opening, and modular lower instrument bank.
Live HTML remains responsible for all scores, names, game state, captions,
ticker copy, and video modes; generated artwork may not contain data text.

The side-tower ball, globe, and generic sport emblems are removed. Each lower
side well receives a small crop of that side's already approved and recolored
athlete master in every video mode. The miniature therefore retains the same racial
identity, uniform number, and live primary/secondary team materials as the
full clash athlete. Friday Night Stadium's frozen five-by-seven LED glyph
matrix and dot geometry are reused exactly for every numeric instrument.

Acceptance rejects duplicate VS artwork, ticker clipping or low contrast,
caption overflow, basketball control collisions, unreadable team identities,
missing miniature athletes, and any mismatch between the Stadium and 8-Bit LED
geometry. The frozen Stadium renderer itself remains unchanged.

### Gate 13.4 — measured cabinet openings and readable instruments

All live content uses measured coordinates taken from the generated cabinet
plate. The venue marquee, both team towers, the central video opening, and all
six lower instrument wells have explicit frame-owned rectangles. The central
clash, highlight, sponsor, player, and broadcast content is clipped above the
lower structural rail and may not intrude into the instrument bank.

The marquee uses the active sport name above `8-BIT GAMEDAY`; the prior doubled
blue/green `CSRN` word treatment is removed. Every sport uses the same approved
high-school stadium/press-box/light-tower cabinet language while football,
basketball, baseball, and softball retain their correct playing surfaces and
sport-specific game state.

The lower chassis is a single row of six explicit modules. Football owns clock,
quarter, down, to-go, ball-on, and possession. Basketball owns visitor fouls,
visitor bonus, clock/period, both timeout indicators, home bonus, and home
fouls. Baseball and softball own visitor R/H/E, balls/strikes, inning, bases,
home R/H/E, and outs. No hidden second control row may exist behind the frame.
The softball clash master holds the ball in the pitcher's raised throwing hand;
no released ball or motion streak may appear between pitcher and batter. The
ball's yellow pixels are explicitly excluded from uniform-material recoloring.

### Gate 13.5 — metadata marquee and sport-owned information wells

The cabinet marquee displays the persisted scheduled date on its first line and
the game classification on its second. Both camelCase active-state fields and
snake_case persisted broadcast fields are accepted. A structured special-game
designation such as Homecoming, Senior Night, Rivalry, Playoff, or Championship
takes precedence. Without one, Scrimmage and Exhibition remain explicit;
official games display Regular Season. Missing preview dates display `DATE TBD`.

Football possession moves from the score well to the possessing team's identity
plate beside the team name and mascot. The vacated sixth instrument is removed;
football retains only clock, quarter, down, to-go, and ball-on because no play
clock update is part of the operational data contract. Basketball's fouls, bonus, clock/period, timeout,
and home-state labels increase approximately 75 percent, including the V/H
timeout indicators and their squares, while remaining inside their frame wells.

Baseball and softball no longer use miniature clash athletes in their lower side
wells. Those wells display live `AT BAT` and `PITCHING` role cards with the batter
and pitcher names. The former role line beneath the score is removed. Diamond
instrument labels increase toward the same legibility scale; R/H/E values retain
distinct columns, and the balls/strikes pair shifts left to preserve its narrow
physical frame opening. Football and basketball retain their approved miniatures.

### Gate 13.6 — explicit football possession well

Football possession moves out of the team identity plate and into the fifth
lower instrument well. It displays the explicit word `VISITOR` or `HOME`, never
an icon or ambiguous arrow. `BALL ON` moves into the sixth, far-right well.
Football therefore owns clock, quarter, down, to-go, possession, and ball-on,
while continuing to expose no play-clock instrument or timeout tracking.

### Gate 13.7 — LED possession closeout candidate

The football possession value remains in the fifth lower instrument well and
continues to read `VISITOR` or `HOME`, but it now uses the renderer's frozen
dot-matrix LED alphabet. Its amber color, glow, height, and dark instrument-well
treatment match the adjacent clock, quarter, down, to-go, and ball-on displays.

### Gate 13.8 — 8-Bit Gameday visual freeze

Gate 13.7 R16 is the approved 8-Bit Gameday visual baseline. Gate 13.8 makes no
visual changes. It permanently SHA-256 locks the isolated renderer, stylesheet,
generated cabinet frame, four athlete masters, and four sport environment plates.
The Layout Lab route remains fixed at `v=13.7` and `pixel_gameday` remains owned
by the isolated 8-Bit engine. Any later visual modification requires an explicit
user-authorized unfreeze gate.

`CSRN_THEME_CONTINUITY_HANDOFF.md` records the next-chat theme sequence and the
asset/compositing workflow established by Friday Night Stadium and 8-Bit Gameday.
Friday Night Stadium Gate 12.6 and 8-Bit Gameday Gate 13.8 are complete and frozen.
Heritage Press is the next concept review, followed by an explicitly authorized
Neon review/unfreeze decision, then Collegiate, Classic, Modern, and Minimal.
This freeze authorizes no production migration; the production overlay and OBS
remain on Gate 6.

### Gate 14.0 — Heritage Press newspaper-system implementation candidate

Heritage Press R2 is an isolated Broadcast Layout Lab renderer that presents the
complete theme as an authentic full-page newspaper sports section. The current
shared-engine Heritage renderer remains the R1 fallback and is not edited by
this gate. Rolling back Gate 14.0 removes the isolated R2 renderer and restores
the prior Layout Lab routing without reconstructing or approximating R1.

The R2 page owns a newspaper masthead, sport section headline, integrated score
box, editorial side columns, central transparent live-video opening, Sports
Wire footer, print rules, monochrome media treatment, and a protected generated
newsprint texture. Football, basketball, baseball, and softball have separate
editorial structures. Basketball supports three-digit scores. Baseball and
softball use At Bat, Pitching, count, runners, inning, and current R/H/E line
language sourced only from available live state. Missing optional totals display
an em dash instead of fabricated information.

Highlight, sponsor, player, feature, and broadcast presentation modes replace
only the central opening. Captions remain inside that opening. Outside Layout
Lab diagnostics, the broadcast opening is transparent. All readable information
regions are code-owned and use live state, verified operator text, or explicit
missing-data language; no fake article paragraphs are generated.

The isolated files are `static/csrn-heritage-press-engine.js`,
`static/csrn-heritage-press-engine.css`, and
`static/heritage/press-newsprint-texture.png`. The four existing Heritage
illustration assets remain available and are not altered. The shared Gate 11
layout engine, frozen Gate 12.6 Friday Night Stadium package, frozen Gate 13.8
8-Bit Gameday package, frozen Gate 11.6 Neon package, production overlay, and
OBS path remain unchanged.

Gate 14.0 requires JavaScript syntax validation, all four sports, six
presentation scenarios, three-digit basketball, captions, transparent opening
behavior, asset loading, clipping checks, focused tests, the full authoritative
suite, and user review of actual Layout Lab screenshots. This is an
implementation candidate, not a visual freeze. No production migration is
authorized by this gate.

### Gate 14.1 — Heritage Press live dispatch and diamond desk candidate

Heritage Press R2.3 retains the Gate 14.0 full-page newspaper architecture and
keeps the installed Gate 14.0 R2 files as its exact rollback fallback. The
unchanged shared-engine Heritage renderer remains the deeper R1 fallback. This
correction does not touch Gate 6 production, OBS, Friday Night Stadium, 8-Bit
Gameday, or frozen Neon.

Football and basketball replace the static Player Watch/Broadcast Note column
with a live newspaper dispatch. Baseball and softball move both active-role
illustrations into a stacked left column and use the right column for the same
fact-bound dispatch system. Baseball uses the existing male batter and pitcher
illustrations. Softball uses separate female batter and fastpitch pitcher assets;
baseball artwork cannot be selected by the softball renderer.
The final softball masters are the user-approved full-body female batter and
pitcher engravings. Their beige scan paper is removed to transparency so the
theme-owned newsprint color and texture show through; the baseball masters and
all baseball rendering remain unchanged. The two approved softball PNGs are
exact-hash protected by the Gate 14.1 regression contract.

The dispatch accepts an optional `heritageDispatch` object containing phase,
event type, factual event fields, an operator headline/body override, and an
optional lively-line identifier. Without a major event it produces a brief
matchup preview from known team, record, venue, and start-time fields. Live
articles are assembled only from verified structured facts. Missing facts are
omitted rather than inferred. Operator-written headline or body copy takes
precedence.

A twelve-entry original period-inspired phrase library supplies at most one
compatible lively line per article. Lines are tagged by sport and event type,
selected deterministically, and may be explicitly selected or disabled. They
are style copy, not attributed historical quotations. Event facts, scores,
player names, inning, clock, conversion result, and game consequence remain
code-owned data.

Baseball and softball now expose an inning-by-inning line score for innings one
through nine, expanding through twelve when needed. The line-score contract
accepts home and visitor inning arrays plus optional hits and errors. Missing
inning values, hits, or errors display an em dash; no scoring history is
fabricated before the future statistics engine supplies it.

The Sporting News-inspired text hierarchy approved during visual review is
retained while the Gate 14.0/R1 newspaper score numeral face remains unchanged.
Highlight, sponsor, player, feature, and broadcast modes still replace only the
central opening, and captions remain inside it. Gate 14.1 is an implementation
candidate requiring actual Layout Lab review before any freeze. No production
migration is authorized.

### Gate 14.2 — Heritage Press visual freeze

Heritage Press R2.3 is visually accepted and frozen. Gate 14.1 R5 is the
accepted visual baseline; Gate 14.2 is a no-visual-change protection gate. It
does not alter the renderer, stylesheet, Layout Lab route, dispatch behavior,
typography, inning line score, central opening, baseball artwork, softball
artwork, or presentation-mode behavior.

The authoritative eleven-file Heritage visual freeze locks:

1. `static/csrn-heritage-press-engine.js`;
2. `static/csrn-heritage-press-engine.css`;
3. `static/csrn-layout-lab.html`;
4. `tests/test_gate14_heritage_press_engine.py`;
5. `static/heritage/press-batter-1920s.png`;
6. `static/heritage/press-pitcher-1920s.png`;
7. `static/heritage/press-softball-batter-1920s.png`;
8. `static/heritage/press-softball-pitcher-1920s.png`;
9. `static/heritage/press-sponsor-truck.png`;
10. `static/heritage/press-player-placeholder.png`; and
11. `static/heritage/press-newsprint-texture.png`.

The accepted package retains the fact-bound Gridiron, Courtside, and Diamond
Dispatch system, its deterministic twelve-line period-inspired phrase library,
Sporting News-inspired text hierarchy, R1-style score numerals, transparent
central video opening, inning-by-inning baseball/softball line scores, stacked
diamond-role column, and the exact approved transparent full-body female
softball batter and pitcher engravings. Baseball artwork remains unchanged.

Installed Gate 14.0 R2 remains the exact correction fallback. The unchanged
shared-engine Heritage renderer remains the deeper R1 fallback. Gate 6
production, OBS, Friday Night Stadium, 8-Bit Gameday, and Neon remain
unchanged. No production migration is authorized by this freeze.

The next theme task is the explicitly authorized Neon Sports Network concept
recovery and comparison. Neon Gate 11.6 remains frozen until a separate,
intentional unfreeze gate is approved after concept review.

### Gate 14.3 — Heritage Press shared-catalog freeze amendment

Gate 14.3 makes no visual change to Heritage Press. It corrects the protection
boundary established by Gate 14.2: the shared `static/csrn-layout-lab.html`
catalog can register later isolated themes without invalidating the accepted
Heritage package.

The Heritage-owned ten-file visual hash freeze remains exact for the isolated
renderer, stylesheet, Gate 14.1 contract test, two baseball engravings, two
softball engravings, sponsor truck, player placeholder, and newsprint texture.
The shared Layout Lab is protected semantically instead of by a complete-file
hash. Its Heritage CSS and JavaScript routes, engine identity, renderer
selection, manifest registration, and validation registration must each remain
present exactly once.

No Heritage renderer, stylesheet, asset, dispatch rule, typography rule,
scoreboard geometry, central opening, or presentation pixel changed. Gate 14.0
R2 remains the exact correction fallback and the shared-engine R1 fallback
remains untouched. No production migration is authorized.

### Gate 15.0 R1 — Neon Sports Network protected-graphics candidate

The user approved an explicit Neon redesign and authorized this isolated R1
candidate. Gate 11.6 remains byte-for-byte available as the exact Neon fallback.
R1 adds new renderer and stylesheet files plus one protected chassis frame and
four sport-specific clash plates; it does not edit the frozen Gate 11 renderer
or stylesheet.

The page places the ticker at the top, the theme-owned live-video opening in the
center, and the sport-specific scoreboard at the bottom. School identity uses
live initials rather than mascot artwork. Team primary and secondary colors own
the controlled neon light channels. The broadcaster's configured primary team
may drive the featured athlete only when that school is one of the two teams in
the active game.

Athlete artwork retains neutral black and gray shading beneath runtime team
color. Football uses a featured running back, basketball a dunking athlete, and
baseball/softball use pitcher-to-batter clash scenes. Diamond scenes do not use
side portraits. The pitcher and catcher share one team's uniform colors, the
batter uses the opponent's colors, and the ball is shown at the contact plane.

Gate 15.0 R1 remains a visual candidate. It requires successful Windows
Chromium and authoritative test evidence plus user inspection of the actual
four-sport Layout Lab output before cleanup or freeze. No production migration,
commit, or push is authorized.

### Gate 15.1 — Neon Sports Network R2 approved visual candidate

Gate 15.1 replaces the rejected R1 presentation with the user-approved Neon R2
direction. R2 is isolated in new renderer, stylesheet, frame-layer, and
sport-action files. Gate 11.6 remains the exact original Neon fallback and the
R1 files remain available for rollback evidence.

The chassis uses neutral graphite structure plus independent left/right neon
core and bloom masks. Runtime team colors drive the tube cores, bloom, reflected
edge light, glowing initials, scores, and selected uniform regions. Sport action
plates retain neutral grayscale shadows and highlights above separate left/right
uniform masks, preventing the sample concept colors from muddying actual team
colors.

Football uses a possession chevron beside the game clock. In statistician mode,
the football state instrument adds a field view with ball spot and drive
direction. The rejected Top Performers panels are absent. Baseball and softball
share the approved diamond-sport structure, use exactly three base diamonds,
use AT BAT, and omit mascot logos. Basketball retains the approved R2 structure.

This remains a Layout Lab visual candidate. Windows Chromium matrices, focused
freeze contracts, the full authoritative suite, and user inspection of the
installed four-sport renders are required before visual freeze. No production
migration, commit, or push is authorized.

### Gate 14.3A — Shared Neon registration contract amendment

Gate 14.3A makes no Heritage visual change and no Neon visual change. It corrects
the shared-catalog governance test so the Layout Lab may advance from one
approved isolated Neon revision to the next.

The contract continues to require Heritage CSS, JavaScript, renderer dispatch,
manifest validation, and manifest selection exactly once. It now requires
exactly one active Neon CSS route, one active Neon JavaScript route, and one
matching Neon engine registration, rather than permanently requiring the
rejected R1 route names.

This preserves the Heritage freeze boundary while allowing the approved Neon R2
renderer to replace R1. No production migration, commit, or push is authorized.

### Gate 15.0A — Neon R1 fallback-contract amendment

Gate 15.0A makes no visual change. It corrects the original R1 candidate test so
R1 is protected as fallback evidence rather than permanently required as the
active Layout Lab route.

The R1 renderer, stylesheet, frame, and four clash assets must remain present.
The shared Layout Lab must register exactly one active isolated Neon revision.
A later approved revision may replace the active R1 route while preserving the
R1 files for rollback and audit purposes.

This amendment allows the approved Gate 15.1 R2 renderer to become active
without weakening Gate 11.6, Heritage, Friday Night Stadium, or 8-Bit Gameday
protections. No production migration, commit, or push is authorized.

### Gate 15.1 R10 — Transparent Neon chassis rebuild

R10 rejects the opaque converted frame layers used by the failed R2 render. The chassis is rebuilt as sparse transparent graphite panels and rails. Left/right neon cores and bloom are narrow grayscale masks with explicit nonrepeating browser mask geometry. The central clash opening is alpha-tested and remains unobstructed. The approved R2 sport layouts and action content are unchanged.

### Gate 15.1 R15 — RGBA mask and stacking repair

All Neon R2 sport and frame masks now carry grayscale intensity in a true RGBA alpha channel. A transparent perimeter prevents any mask from becoming an opaque browser rectangle. The action artwork, recolor masks, bloom, chassis, score, ticker, and identities use an explicit safe stack. Regression tests reject grayscale-only masks and unsafe layer ordering.

### Gate 15.1 R16 — Bright neon core and bloom repair

R16 separates raw team colors from bright display-neon colors. Raw colors remain on athlete recolor masks, while rails, initials, scores, and glow use hue-preserving brightened values. The frame now uses a white-hot narrow core, a 10-pixel bloom, and stacked 18/36-pixel color halos. The neutral chassis remains unchanged.

### Gate 15.1 R17 — Football field-position module

Football alone now uses the lower chassis field for an overhead field-position display. The module renders neutral yard geometry, team end zones, a possession-colored neon ball-position line, a football marker, ball-spot label, and directional arrow. It accepts explicit ball side and drive direction, with possession-based fallbacks. Basketball does not receive this module; baseball and softball retain their batter, in-the-hole, and pitching strip. The field remains fully inside the 1080 canvas.

### Gate 15.1 R18 — Football field compatibility amendment

R18 preserves the football overhead field-position module while restoring the existing statisticianMode compatibility contract. The field remains available for football and exposes statistician-mode state through a class and data marker. No visual geometry or sport scope changes are made.

### Gate 15.1 R20 — Sport lower-deck and clash-color correction

R20 brightens the football field into a clearly neon surface and recalculates football score/field geometry to remain inside the 1080 canvas. Basketball receives a decorative neon court with no data. Baseball and softball replace the three-box strip with AT BAT, a full inning scoreboard, and PITCHING; IN THE HOLE is removed. Clash uniform masks now use bright display-neon colors with stronger opacity, saturation, light spill, and team-color bloom while retaining the neutral athlete base.

### Gate 15.1 R21 — Clash glow contract amendment

R21 makes no visual change. It corrects the R16 glow regression contract so raw team colors remain available as source identity values while the approved R20 clash recolor layers use bright display-neon colors. Wide bloom, white-hot cores, and hue-preserved neon display variables remain protected.

### Gate 15.1 R22 — Glow test source-location amendment

R22 makes no visual change. Raw team-color variables are validated in the JavaScript renderer where they are injected as inline package variables. Bright clash recolor, bloom, and hot-core rules remain validated in CSS.

### Gate 15.1 R23 — Sport data and clipping correction

Football field geometry is moved upward, score height reduced, and field numbers are 2.5x larger and upright. Basketball adds fouls, bonus, and possession and moves the decorative court inside the canvas. Baseball and softball remove the redundant title bar, enlarge inning cells, and raise the lower deck. Basketball and diamond-sport clash screens receive a stronger team-color pass.

### Gate 15.1 R24 — R23 stale-test amendment

R24 makes no visual or renderer change. It updates the football field-position and sport lower-deck tests to the approved R23 geometry. The diamond lower-deck contract now explicitly requires removal of the redundant INNING SCOREBOARD title bar.

### Gate 15.1 R25 — Commercial lower-assembly rebuild

R25 replaces the patched lower geometry with one shared lower assembly containing the score module and a fixed sport deck. Obsolete lower boxes and rails are removed from the neutral chassis and frame masks. Football, basketball, baseball, and softball render inside the same bounded lower-deck rectangle with a 50-pixel bottom safe margin. Diamond line scores use a true fixed-layout HTML table with separate nine-inning baseball and seven-inning softball contracts. Basketball fouls and bonus state are integrated into the corresponding team score sections. Nonfootball clash coloring uses the authored masks with reduced broad wash and stronger semantic color blending.

### Gate 15.1 R26 — Commercial visual convergence

R26 corrects implementation gaps remaining after the R25 structural rebuild. Football now renders two independently distributed upright yard-number rows and hash marks. Baseball and softball restore exactly three bases in the center cockpit, retain fixed-layout line-score tables, and highlight the active inning. The clash opening and lower assembly share a clean boundary at y=730. Basketball court, ticker, player panels, score hierarchy, and chassis materials receive a final integration pass. Nonfootball authored masks are expanded and alpha-boosted at the asset level while broad environmental wash is reduced.

### Gate 15.1 R27 — Approved clash integration

R27 removes the failed runtime uniform-recolor path and installs clean precolored football, basketball, baseball, and softball clash assets derived directly from the approved Neon reference. No expanded or noisy player masks remain active. R26 layout, score, field, court, bases, inning tables, ticker, and lower-assembly structure are retained.

### Gate 15.1 R28 — Release layout correction

R28 enlarges and expands the baseball/softball line score to the full lower deck, moves AT BAT and ON THE MOUND information into the appropriate team identity panels, simplifies basketball to clock and period while doubling team and foul typography, re-aligns score-row team names, installs a graphic football-field layer, uses non-neon team logo images in the end zones when available, and triples the football/ball-position indicator. The baseball clash receives a rear three-quarter overhand pitcher replacement with the ball retained in the throwing hand.

### Gate 15.1 R29 — Final sport corrections

R29 increases football quarter and down/distance typography by 50 percent, replaces the flat football surface with a textured numbered field graphic based on the approved reference, and reduces field lighting. Highlight/broadcast video now owns the complete clash opening. Basketball and softball clash assets are byte-for-byte preserved from R28. Baseball is rebuilt from the approved softball composition with a male rear-view overhand pitcher holding the ball before release.

### Gate 15.1 R30 — Baseball-only clash and field cleanup

R30 replaces only the baseball clash asset with a new male pitcher, male catcher, male batter, and umpire composition. Football, basketball, and softball clash hashes are locked and unchanged. Diamond team-panel highlights are reduced for legibility. Softball uses PITCHING while baseball retains ON THE MOUND. Football uses the upper field texture only, with one HTML yard-number row and one restrained hash zone.

### Gate 15.1 R31 — Baseball rerender and field alignment

R31 replaces only baseball clash artwork with a fresh male baseball composition, removes fixed helmet marks, corrects the softball ball to a regulation yellow softball, removes all glow from diamond player-information blocks, removes the HTML football-number overlay, aligns the ball marker to the baked field coordinate system, and expands football down-and-distance wording.

### Gate 15.1 R32 — Swap and visual cleanup

R32 removes the football possession glyph and all HTML field-number overlays, restores the approved naturally integrated softball, replaces baseball with a clean standalone action crop, removes fixed helmet initials, adds an explicit Layout Lab Swap Teams control, mirrors clash artwork when teams are swapped, and enforces crisp non-glowing baseball/softball player-information typography.

### Gate 15.1 R33 — Commercial art and color validation

R33 removes baked football helmet marks and baseball team lettering, preserves the current compositions, adds subtle regulation softball seams to the existing integrated ball, removes clash mirroring from team swaps, and adds independent home/visitor color controls plus broadcast color presets to the Layout Lab. Basketball and the approved football field remain unchanged.

### Gate 15.1 R34 — Adaptive clash-color pipeline

R34 restores Standard B adaptive artwork for Neon. Each football, basketball, baseball, and softball clash uses a neutralized base plus constrained left-team and right-team uniform masks. Runtime home and visitor colors tint authored uniform/equipment regions while skin, officials, balls, bats, gloves, and backgrounds remain neutral. The Neon manifest declares artworkColorMode adaptive. Heritage Press and Minimal remain the only approved fixed-art exceptions.

### Gate 15.1 R35 — Football layered-color proof

R35 replaces football's post-render segmentation with a coordinated layered contract: neutral base, home primary mask, home secondary mask, visitor primary mask, visitor secondary mask, neutral uniform shadows, and neutral uniform highlights. Tight garment regions and connected-component seeds prevent background energy, skin, the football, and equipment from entering the color layers. The Layout Lab exposes secondary colors. Basketball, baseball, and softball remain on the R34 pipeline pending visual approval of the football proof.

### Gate 15.1 R36 — Football alpha-cutout proof

R36 replaces the football overlay-color experiment with a true cutout composite. The complete clash master has physically transparent uniform regions. Home and visitor primary/secondary color planes sit underneath those openings. Neutral midtone, shadow, highlight, number/detail, and restrained team-colored smoke-halo layers sit above them. Basketball, baseball, and softball remain unchanged.

### Gate 15.1 R37 — Football luminance cap

R37 strengthens the alpha-cutout proof with a near-opaque grayscale garment luminance plate using luminosity blending. The plate preserves the team-color hue underneath while blocking flat color with the source fabric brightness, folds, pad contours, and helmet reflections. Cutouts are tightened around the football, gloves, exposed arms, faces, facemasks, numbers, and neutral equipment.

### Gate 15.1 R38 — New-render exact-pixel football cutout

R38 replaces the inherited football clash with a new neutral render designed for the cutout architecture. Only exact checker-textured uniform pixels and exact blue/green smoke pixels become transparent. Team-color planes sit beneath those openings. A nearly opaque luminance cap and restrained texture cap reconstruct garment depth while the ball, skin, gloves, facemasks, visors, and neutral background remain opaque in the whole master.

### Gate 15.1 R39 — Neutral smoke texture cutout

R39 removes all baked blue and green from the football smoke system. The whole clash master converts former colored smoke pixels to neutral grayscale. Separate home and visitor smoke masks expose team-color planes beneath the master. Neutral grayscale smoke luminance, texture, shadow, and highlight layers restore wispy density and depth without contributing any hue. Uniform luminance and texture remain independent.


Gate 15.1 R40 — Adaptive blacklight football clash opening installed as a Neon R2 candidate.
No production migration is authorized by this package.


Gate 15.1 R40A — Full-opacity player occlusion underlay prevents blacklight field lines from showing through the players. No production migration is authorized.


Gate 15.1 R40B — Removed the misaligned adaptive secondary uniform stripe masks from the Neon football clash. Primary uniform recoloring, player opacity, field glows, chassis, geometry, and other sports remain unchanged. No production migration is authorized by this package.


Gate 15.1 R40C — Removed the two baked molded center grooves from the ball-carrier and defender helmet shells across the neutral master, opaque occlusion underlay, luminance, shadow, and highlight layers. Helmet contours, facemasks, visors, team-color masks, field, chassis, geometry, and other sports remain unchanged. No production migration is authorized by this package.


Gate 15.1 R40D — Corrected the actual deployed helmet-center stripe coordinates on both football players. The stripe pixels were rebuilt across the neutral master, opaque underlay, luminance, shadow, and highlight layers. Uniform color masks, player silhouettes, facemasks, visors, field, chassis, geometry, and other sports remain unchanged. No production migration is authorized by this package.


Gate 15.1 R40E — Filled the transparent center gaps in the current R40A-hardened primary helmet masks. This prevents the neutral underlay from appearing as a contrasting helmet stripe. Secondary masks remain disabled. No other visual or runtime systems changed.


Gate 15.2 R41E — Installed adaptive basketball clash layers while preserving the frozen R40 version, manifest string, and Layout Lab cache contract required by existing authoritative tests. Includes full split-team neon court paint, rim/net glows, home-colored ball channels, exact player recoloring, and player occlusion. Football R40E, baseball, softball, chassis, and score modules remain unchanged.


## Gate 15.2 R41G — Neon Basketball Visual Freeze
The Neon R2 basketball adaptive clash is visually frozen at the R41F runtime state. The authoritative freeze covers the complete 15-layer basketball asset stack, the Neon CSS integration, the R41F JavaScript asset-variable integration, and the R41F focused runtime test. No basketball redesign, mask replacement, color-pipeline change, court-line change, rim/net change, ball-channel change, player geometry change, or luminance/depth adjustment is authorized without a new explicit unfreeze gate. Football R40E remains frozen and unchanged. Baseball and softball remain unfinished and outside this freeze.


Gate 15.3 R42A — Installed the accepted Neon softball template-driver stack as a supplemental renderer. The seven 1208×840 RGBA assets preserve the accepted V6 jersey masks and recolor only the home batter jersey and visible visitor catcher jersey fabric. The frozen football R40E and basketball R41G renderer files and assets remain unchanged. This gate is Layout Lab validation only; no production overlay migration, commit, or push is authorized.

## Gate 15.3 R43A — Neon Baseball Template Driver

The approved corrected baseball jersey-cutout package is integrated as a supplemental Neon driver. Baseball uses exact 1163×665 source-aligned layers with `home_primary` controlling the batter jersey and `visitor_primary` controlling the catcher jersey sleeves. The driver loads after the accepted softball supplemental driver and does not rewrite frozen football or basketball renderer files. Source artwork, masks, protected pixels, and runtime color-slot geometry remain authoritative and unchanged.

No commit, push, or production migration is authorized by this gate.

## Gate 15.3 R43B Current-State Neon Four-Sport Freeze

The accepted development state for Neon Football R40E, Basketball R41G/R41F, Softball R42A, and Baseball R43A is protected by an authoritative current-state SHA-256 contract generated from the installed repository files. This is an interim development freeze, not commercial-release approval. A later commercial-cleanup gate remains required. No production migration is authorized.

## Gate 16.0 Production Overlay Resumption

Theme-development status and sequencing decision:

- **Friday Night Stadium:** frozen for now. Its current implementation remains protected, but its sport graphics must be revisited before commercial release.
- **Neon:** frozen for now in its accepted four-sport development state. Commercial cleanup remains deferred.
- **CSRN Cartoon:** approved as a future CSRN-exclusive theme rather than a replacement for Modern. Planned capabilities include recognizable host caricatures, host-specific microphone-reactive motion, speech-bubble captions, event cards, and dynamic sponsor content.
- **Modern:** retained as a general commercial theme.
- **Theme-development pause:** additional theme construction is paused while development returns to the production overlay, OBS/browser-source workflow, operator controls, event integration, game-state reliability, persistence, and full-broadcast validation.

Gate 16 begins with a production-overlay resumption audit. The first implementation change after this audit must be based on the actual active overlay route and current repository state. Frozen theme visuals must not be modified by Gate 16 unless Jason explicitly reopens a theme.
## Gate 16.1 R1 — Production Theme Integration Boundary Audit

- Compared the real OBS overlay loader with Layout Lab.
- Confirmed approved themes remain isolated from the production overlay.
- Established Gate 16.2 as a production-only theme host plus state-adapter slice.
- Frozen theme files remain untouched.
- Audit record: `CSRN_GATE161_PRODUCTION_THEME_INTEGRATION_BOUNDARY_AUDIT.md`.
## Gate 16.2 R1 — Production Theme Host and Adapter

- Added a production-only theme host beside the existing legacy overlay DOM.
- Added deterministic normalization for runtime and public theme state.
- Activation requires an explicit approved package identifier.
- Missing or invalid package state retains the legacy production overlay.
- Frozen theme engines and assets were not modified.
- This gate establishes the integration boundary only; approved engine rendering remains disabled pending Gate 16.3 validation.
## Gate 16.3 R2 — Isolated Theme Engine Readiness Probe

- Preserved the Gate 7 prohibition against loading Layout Lab engines in the live production overlay.
- Added an isolated static readiness page at `/static/csrn-production-theme-readiness.html`.
- The page loads approved engines by reference and reports browser globals and render entry points.
- It performs no polling, state mutation, theme activation, rendering, or production-overlay suppression.
- The live OBS route remains on the Gate 6 renderer.
- Frozen theme engines and visual assets were not modified.
## Gate 16.4 R1 — Selectable Production Template Menu

- Added a production-template selector to the existing Graphics Theme Manager.
- Menu choices: Legacy, Friday Night Stadium, 8-Bit Gameday, Heritage Press, and Neon.
- The staged selection persists in the operator browser.
- The interface explicitly marks the selection as not on air.
- No server state, OBS route, production renderer, or frozen theme asset is changed by this gate.
- Gate 16.5 will add authoritative persistence and production binding.
## Gate 16.5 R4 — Authoritative Production Template State

- Production-template state is implemented through the existing Phase 5 Blueprint route layer.
- No new endpoint is registered directly on `app.py`.
- The installer discovers the Blueprint that already owns `/api/themes/public-state` and reuses its existing authenticated POST-route decorator.
- Added authenticated `GET/POST /api/production-template` endpoints inside that Blueprint.
- Existing public theme state is enriched with the authoritative production-template identifier without adding a new public endpoint.
- Legacy remains the state fallback and production render binding remains disabled.
- Gate 7 production-overlay isolation remains intact.
## Gate 16.6 R1 — Production Render Binding

- Authoritative production-template selection now drives the OBS overlay.
- `templates/overlay.html` loads only a generic production-theme runtime; frozen Layout Lab engine filenames remain absent from the overlay template.
- The runtime dynamically loads the selected approved engine and invokes its established `renderPackage(target, packageId, sport, state, options)` contract.
- Menu aliases are translated through each loaded engine's authoritative `packageId` rather than duplicating frozen package identifiers.
- Runtime state is mapped onto the broadcast engine's own `defaultState()` contract.
- The themed package replaces only the legacy scorebug after a successful render; ticker, lower-third, player, personnel, sponsor, and event systems remain on the existing production path.
- Legacy scorebug remains automatic fallback for Legacy selection, invalid selection, load failure, or render failure.
- Production render binding is now reported as enabled.
- Frozen engine files and visual assets were not modified.
## Gate 16.6 R2 — Scorebug-Only Production Binding Correction

- Gate 16.6 R1 runtime behavior was visually rejected because the generic runtime passed the complete baseline scenario to `renderPackage()`, causing the selected theme's full package to render over production.
- Production binding is now explicitly constrained to `activeComponents: ["scorebug"]`.
- A successful render is rejected unless the engine reports exactly the `scorebug` component.
- Legacy `#scorebug` suppression now uses an explicit production-active root class plus `display:none!important` so existing overlay CSS cannot override the handoff.
- Deactivation clears the themed host and removes the suppression class, restoring Legacy immediately.
- Ticker, lower-third, player, personnel, sponsor, event, and all other production graphics remain on the legacy production path.
- Frozen theme engines and visual assets remain unchanged.
## Gate 16.7 R2 — Theme-Owned Live Ticker Binding

- The selected production theme now owns both the live scorebug and live ticker presentation.
- Friday Night Stadium, 8-Bit Gameday, and Neon render their frozen `ticker` component in a dedicated production ticker host.
- Heritage Press uses a production wrapper built from its frozen `hp-footer`, `hp-wire-title`, and `hp-wire-copy` classes because its frozen engine binds `ticker.text` inside the newspaper footer rather than exposing a standalone ticker component.
- Live ticker text is mapped from the production state into `state.ticker.text`.
- The legacy `#eventTicker` is suppressed only after both themed scorebug and themed ticker render successfully.
- Any selection/load/render failure removes both production-active classes, clears the theme hosts, and restores the legacy scorebug and ticker.
- Frozen engine files and visual assets were not modified.
- Heritage clash-screen concept remains a deferred enhancement; no Heritage clash asset is introduced by this gate.
## Gate 16.7 R4 — Live Event Ticker and Themed Player Correction

- The themed ticker now derives from the same authoritative `/api/state.events` collection as the legacy production ticker.
- Undone events are excluded; event description/label, team name, quarter, score snapshot, ticker speed, and ticker pause settings are honored.
- Theme ticker text is written into `state.ticker.text` before scorebug rendering.
- The runtime mounts a real scrolling track inside each theme's frozen ticker location: Friday Night Stadium LED strip, 8-Bit top marquee, Heritage Sports Wire, and Neon ticker.
- The separate Gate 16.7 ticker host is deprecated and no longer used.
- The legacy `#eventTicker` is suppressed only when the themed scrolling ticker is successfully mounted.
- A dedicated themed-player host was added.
- Friday Night Stadium, 8-Bit Gameday, and Heritage Press render their frozen `player` component from `/api/state.player_graphic` when that graphic is visible.
- The legacy `#playerGraphic` is suppressed only after a themed player component renders successfully.
- Neon does not expose a frozen player component and therefore intentionally retains the legacy player graphic until a Neon-specific player treatment is designed.
- Player Highlight remains a separate production graphic and is not migrated by this gate.
- Frozen theme engines and visual assets were not modified.
## Gate 16.7 R5 — Game-State Semantics Correction

- Production football period state now synchronizes `period`, `quarter`, and period-label aliases so `OT` cannot fall back to a frozen numeric fixture in approved themes.
- Clock visibility is authoritative. A hidden clock renders `-` instead of a frozen fixture clock.
- Down and Distance are independently authoritative.
- If Down is disabled/Off, the designed Down box displays `-`.
- If Distance is disabled/Off, the designed Distance/To-Go box displays `-`.
- If both are disabled, both structural boxes remain present and display `-`.
- `downDistance` is always explicitly populated from production values to prevent frozen defaults such as `3RD & 7` from leaking into production.
- The working live-event themed ticker and R4 themed-player behavior remain unchanged.
- Heritage-specific masthead, clash-screen, and visual corrections remain deferred for a single Heritage correction package.
- Frozen theme engines and visual assets were not modified.
## Gate 16.7 R8 — Deterministic Game-State Binding

- Gate 16.7 R7 proved that 8-Bit Gameday and Friday Night Stadium internally reduce football period to digits and default to quarter 2, and parse Down/Distance with a numeric-only regular expression that defaults to 3 and 7.
- R8 preserves the frozen engines and applies production-only post-render overrides to their structural CLOCK, QUARTER, DOWN, and TO GO cells.
- OT therefore displays as `OT` without modifying frozen engine source.
- Disabled Down and/or Distance display `-` in their existing boxes without modifying frozen engine source.
- Visible game clock derives from the production `clock`/`game_clock` value or authoritative `clock_seconds`; hidden clock displays `-`.
- Production `date` / `scheduled_start` is mapped to theme `scheduledDate` so the 8-Bit venue header no longer falls back to `TBD` when a date is available.
- 8-Bit and Friday Night player events now activate their existing integrated `videoMode: player` presentation inside the main themed board instead of attempting a nonexistent standalone `player` component.
- The legacy player card is suppressed only while that integrated player mode is active.
- The working live-event themed ticker remains unchanged.
- Heritage-specific visual corrections remain deferred to the consolidated Heritage correction package.
- Frozen theme engines and approved visual assets were not modified.
## Gate 16.7 R9 — Player Event Reliability

- 8-Bit Gameday and Friday Night Stadium continue to use their frozen integrated `videoMode: player` presentation.
- Player media is preflighted before render. A valid headshot is preferred; a valid team logo is the secondary fallback; otherwise the frozen theme's number-based player placeholder is used.
- Broken player-media URLs no longer intentionally reach the frozen player renderer. A post-render image error guard also replaces a failed player image with the player's number.
- A production `player-pending` state suppresses the legacy `#playerGraphic` before themed rendering completes, preventing the modern player card from flashing ahead of the themed presentation.
- Player activation identity includes `player_graphic.updated_at`, `expires_at`, player identity, and the latest active event identity so a subsequent event can re-arm player mode even when it involves the same player.
- Undo/inactive player state clears both pending and active player suppression and returns the themed board to clash mode on the next render.
- Player Highlight remains explicitly outside this gate.
- Date, OT, clock, Down/Distance, ticker, and other Gate 16.7 R8 behavior are not changed.
- Frozen engines and approved visual assets were not modified.
## Gate 16.7 R10 — Player Transition Continuity

- The approved themed player presentation from Gate 16.7 R9 is unchanged.
- When themed player mode becomes pending, all legacy `#playerGraphic` Web Animations, CSS transitions, and CSS animations are cancelled before the themed presentation is rendered.
- The legacy player card is forced fully hidden during both themed-player pending and active ownership so no slide-in or slide-out remnant can cross the themed board.
- Before themed ownership is released, the legacy card is synchronously placed at its normal `hidden` endpoint with motion disabled.
- Its normal legacy transition/animation properties are restored only after the themed pending/active classes are gone and the hidden endpoint has been committed.
- This prevents the modern player card from appearing during either the incoming or outgoing themed-player handoff.
- Player media fallback, player-event re-arm behavior, date, OT, clock, Down/Distance, ticker, and all other R8/R9 behavior are preserved.
- Player Highlight remains outside this gate.
- Frozen engines and approved visual assets were not modified.
## Gate 16.7 R11 — Player Presentation Legibility

- The integrated themed player presentation from Gates 16.7 R9/R10 remains structurally and behaviorally unchanged.
- Production-only CSS increases the `PLAYER SPOTLIGHT` label, player name, and play-detail text for broadcast readability.
- Player name is increased to 34 px; play detail to 20 px; spotlight label to 18 px.
- Text wrapping width is expanded without changing the existing portrait proportions or main themed-board geometry.
- Number-placeholder fallback is enlarged for better readability when no usable player image or team logo exists.
- Player duration/timing remains controlled by the existing production player-graphic system.
- Player transition suppression, media fallback, Undo/re-arm behavior, date, OT, clock, Down/Distance, and ticker behavior are preserved.
- Player Highlight remains outside this gate.
- Frozen engines and approved visual assets were not modified.
## Gate 16.7 R12 — Player Text Scale

- The Gate 16.7 R11 integrated player presentation text is increased by approximately 75 percent at the user's request.
- Production-only CSS now renders the spotlight label at 32 px, player name at 60 px, and play-detail line at 35 px.
- Player text wrapping allowance is expanded while preserving portrait geometry and the main themed-board structure.
- Number-placeholder fallback is enlarged to 96 px.
- Player event lifecycle, duration, media fallback, transition continuity, date, OT, clock, Down/Distance, and ticker behavior are unchanged.
- Manual Show/Update failures for Player Spotlight, Player Highlight, and Sponsor Spotlight are recorded as a separate functional follow-up and are not modified by this visual-only gate.
- Frozen engines and approved visual assets were not modified.
## Gate 16.7 R13 — Player Text Scale iPhone Follow-up

- The integrated production player presentation receives a second legibility pass for small-screen and iPhone viewing.
- Player Spotlight label is increased to 44 px.
- Player name is increased to 86 px.
- Play-detail line is increased to 52 px.
- Number placeholder fallback is increased to 116 px.
- This gate is visual-only and does not change player-event timing, ticker behavior, OT/date/clock binding, or manual Show/Update channel behavior.
## Gate 16.7 R14 — Player Text Selector Correction

- R11-R13 typography overrides targeted the Friday Night-specific player replacement selector and therefore did not reliably reach the 8-Bit integrated player presentation.
- R14 targets the shared `[data-video-mode="player"]` contract used by the frozen themed player presentation.
- Intended iPhone-scale typography remains 44 px spotlight label, 86 px player name, and 52 px play detail.
- No player-event behavior, timing, transition logic, image fallback, ticker, OT/date/clock, or manual Show/Update channel behavior is changed.
## Gate 16.7 R15 — Player Text Final Tuning

- The corrected shared `[data-video-mode="player"]` selector from R14 remains authoritative.
- Player typography is reduced approximately 30 percent from R14 after visual review.
- Production player spotlight label is 31 px.
- Player name is 60 px.
- Play detail is 36 px.
- Number-placeholder fallback is 82 px.
- No player-event lifecycle, duration, transition, media fallback, ticker, OT/date/clock, Down/Distance, or manual spotlight channel behavior is changed.
- Manual Show/Update failures for Player Spotlight, Player Highlight, and Sponsor Spotlight remain the next functional audit target.
## Gate 16.7 R17 — Manual Spotlight Show/Update Bridge

- Gate 16.7 R16 confirmed that Player Spotlight, Player Highlight, and Sponsor Spotlight are independent primary graphic channels with valid authenticated routes and persisted visible/expiry state.
- Program Visual Player Spotlight Show/Update now explicitly posts `action: show` and `visible: true` to `/api/graphics/player` so the service cannot interpret an update-only payload as hidden.
- Player Spotlight continues to use the selected production theme's integrated player presentation where supported.
- Player Highlight and Sponsor Spotlight continue using their existing validated legacy overlay presentations for this bridge gate.
- While a production theme is active, visible `#playerHighlight` and `#sponsorSpotlight` are elevated above the themed board so Show/Update can actually be seen.
- The graphics service remains authoritative for primary-channel arbitration: activating one primary graphic hides the other primary channels.
- No fake themed Player Highlight or Sponsor Spotlight component was introduced.
- The eventual themed visual treatment of Player Highlight and Sponsor Spotlight remains a separate design/integration task.
- Frozen theme engines and approved visual assets were not modified.
## Gate 16.7 R18 R2 — Superseded Contract Correction

- R18 R1 correctly introduced native multi-mode central video-board ownership for Player Highlight and Sponsor Spotlight.
- R18 R1 failed focused validation because inherited R8-R17 tests still required the older player-only `videoMode:playerModeFor(...)` contract and prohibited runtime access to manual highlight/sponsor state.
- R18 R2 explicitly supersedes those stale assertions with the new `themeVideoModeFor` / `activeVideoMode` contract.
- Historical player transition, player fallback, typography, game-state, and explicit Player Spotlight activation protections remain tested.
- All test files modified by this installer are included in the rollback set.
- Runtime behavior is otherwise unchanged from R18 R1.
## Gate 16.7 R19 — Central Video-Board Media Polish

- Player Highlight now replaces the entire central video-board content opening with the selected video rather than retaining frozen placeholder copy beside a nested media box.
- Highlight video uses full board width and height with contain scaling and autoplay-safe muted playback.
- Sponsor Spotlight now uses a production-owned central-board composition with larger theme-appropriate typography.
- Sponsor media fallback order is selected media, sponsor logo, then text-only sponsor identity; failed media cannot intentionally leave a broken image.
- Player Spotlight, ticker, scores, date, OT, clock, and other R18 behavior remain unchanged.
- Frozen theme engines and approved visual assets were not modified.
## Gate 16.7 R20 — Central Video-Board Boundary Correction

- Gate 16.7 R19 proved highlight media playback but mounted 8-Bit production media too broadly, covering the full themed composition.
- The approved 8-Bit media boundary is the physical central video-board opening only.
- 8-Bit Highlight and Sponsor now mount into a dedicated production overlay constrained to that center-board geometry.
- The themed ticker, date panel, visitor/home score towers, and bottom clock/quarter/down/to-go/possession/ball-on instruments remain visible.
- Highlight video uses `object-fit: contain` inside the bounded center board.
- Sponsor Spotlight uses the same bounded board while retaining the R19 media/logo/text fallback chain and production typography.
- Friday Night Stadium retains its existing native theme host behavior in this gate; R20's geometry correction is specific to the visually verified 8-Bit board.
- Frozen theme engines and approved visual assets were not modified.
## Gate 16.7 R21 — Central Board Layer Ownership + Sponsor Scale

- R20 established the correct 8-Bit center-board geometry, but visual testing showed the production media overlay was not reliably winning the frozen engine's internal stacking order.
- R21 applies the approved center-board geometry directly to the production overlay at runtime and raises that bounded overlay above the frozen center-board content.
- The overlay remains constrained to left 22.5%, top 23.5%, width 55%, height 57.5%.
- Highlight video remains `object-fit: contain` inside that exact boundary.
- Sponsor Spotlight uses the same bounded production layer.
- Sponsor lead-in and caption are increased to 44 px; sponsor name to 84 px, approximately 45 percent larger than the prior R20 targets.
- Sponsor copy is explicitly centered horizontally and vertically.
- R19 sponsor media -> logo -> text-only fallback behavior is retained.
- Ticker, date panel, side score towers, and bottom game-state instruments remain outside the production media layer.
- Frozen theme engines and approved visual assets were not modified.
## Gate 16.7 R23 — Native 8-Bit Video-Board Binding

- Gate 16.7 R22 proved the frozen 8-Bit center-board owner is `.bl-8bit-video-board` inside `.bl-8bit-main-display`.
- The frozen engine inserts the active `clash`, `highlight`, `sponsor`, `player`, or `broadcast` mode directly inside that native video-board section.
- R23 removes the R20/R21 percentage-positioned production overlay approach from active runtime behavior.
- For 8-Bit Highlight and Sponsor, production now locates `.bl-8bit-video-board` and populates its existing direct `[data-video-mode]` child.
- Highlight replaces the native `VIDEO` placeholder and title/detail children with the actual highlight video inside the exact frozen video-board geometry.
- Sponsor replaces the native sponsor placeholder contents in the same mode element, preserving media -> logo -> text fallback.
- Sponsor lead-in/caption remain 44 px and sponsor name 84 px, centered using the 8-Bit Courier-style typography.
- Highlight/Sponsor production mode transitions are neutralized on the native mode node to prevent legacy transition remnants.
- Player Spotlight remains on its existing proven native player mode.
- Frozen theme engines, frozen engine CSS, approved assets, ticker, date panel, team towers, and bottom game-state instruments were not modified.
## Gate 16.8 R2 — Native Friday Night Stadium Production Binding

- Gate 16.8 R1 proved Friday Night Stadium uses `.bl-fns-video-board` as its native center media host.
- The active `clash`, `highlight`, `sponsor`, `player`, or `broadcast` element is a direct child of that native board.
- Gate 16.8 R2 extends the accepted Gate 16.7 R23 native-host architecture to Friday Night Stadium.
- Production Highlight and Sponsor now populate the existing Friday Night mode element rather than relying on generic or secondary overlay geometry.
- Highlight video remains `object-fit: contain` inside the native board.
- Sponsor media/logo/text fallback remains intact and centered.
- Highlight and Sponsor transition/animation transforms are neutralized only on the active native media mode.
- Existing shared Player Spotlight typography and fallback behavior remain unchanged.
- Existing theme-owned ticker and production game-state binding remain unchanged.
- Frozen Friday Night engine JS/CSS and approved visual assets were not modified.
## Gate 16.8 R3 — Production Identity Authority + Strict Native Media Host

- Selected-game identity is now authoritative for the production theme runtime.
- The runtime consumes the actual broadcast identity schema: `broadcast_name`, `official_name`, mascot/nickname, primary/secondary colors, certified/generated logo, and school ID.
- `home_team` / `visitor_team`, school IDs, full identity objects, venue, and venue ID are included in the render signature so changing the selected matchup forces an immediate theme rerender even when scores and clock are unchanged.
- Venue data is preserved in normalized production theme state.
- 8-Bit and Friday Night Highlight/Sponsor media are fail-closed to their audited native hosts: `.bl-8bit-video-board` and `.bl-fns-video-board`.
- The audited stadium themes cannot fall through to a broad outer `[data-video-mode]` target.
- Legacy full-screen `#playerHighlight` and `#sponsorSpotlight` layers are suppressed by both runtime enforcement and CSS while the theme owns Highlight/Sponsor presentation.
- Suppression is enforced on every production-state poll, including unchanged render signatures.
- Existing 8-Bit and Friday Night ticker, game-state, OT, Player Spotlight, and cabinet behavior remain unchanged.
- Frozen 8-Bit/Friday Night engine JS/CSS and approved visual assets were not modified.
- Clash player recoloring remains deferred.
## Gate 16.9 R2 — Heritage Native Production Binding + Clash Foundation

- Gate 16.9 R1 proved Heritage Press is a full-page newspaper engine with a native `.hp-opening` story/media region.
- Highlight production media now mounts only inside `.hp-highlight-window[data-module="video.board"]`.
- Sponsor production media now owns only the native `.hp-sponsor-feature[data-video-mode="sponsor"]` opening.
- Heritage Player Spotlight is promoted to the accepted integrated player path.
- Football OT, clock visibility, and Down/Distance state receive the same production-authoritative override semantics used by accepted themes.
- Selected-game identity continues to use the Gate 16.8 R3 production authority path.
- The Sports Wire remains theme-owned through `.hp-wire-copy` and the existing live-event ticker feed.
- Football neutral/broadcast mode now uses the native `.hp-live-opening` as a Heritage clash foundation with live team marks and names.
- The foundation reserves the center artwork layer for the approved black-and-white leather-helmet newspaper engraving in a later visual gate.
- The clash foundation is football-only; basketball/baseball/softball remain on their frozen Heritage broadcast opening pending separate visual authorization.
- Frozen Heritage engine JS/CSS and approved Heritage visual assets were not modified.
## Gate 16.9 R3 — Heritage Native Spotlight Ownership + Newspaper Media Finish

- Heritage Player Spotlight now repopulates and owns the native player opening after every render, eliminating the transient flash/drop behavior.
- Player imagery is grayscale with a restrained press treatment.
- Highlight video remains in the native Heritage highlight frame and is grayscale for newspaper continuity.
- Sponsor artwork remains full color while the surrounding frame, typography, rules, and paper treatment remain Heritage-native.
- Legacy player/highlight/sponsor layers are suppressed whenever Heritage-native modes own presentation.
- Existing selected-game identity, Sports Wire, OT/game-state behavior, and clash foundation are preserved.
- Frozen Heritage engine JS/CSS and approved assets were not modified.
## Gate 16.9 R4 — Heritage Native Spotlight Ownership + Newspaper Media Finish

- Heritage Player Spotlight now repopulates and owns the native player opening after every render, eliminating the transient flash/drop behavior.
- Player imagery is grayscale with a restrained press treatment.
- Highlight video remains in the native Heritage highlight frame and is grayscale for newspaper continuity.
- Sponsor artwork remains full color while the surrounding frame, typography, rules, and paper treatment remain Heritage-native.
- Legacy player/highlight/sponsor layers are suppressed whenever Heritage-native modes own presentation.
- Existing selected-game identity, Sports Wire, OT/game-state behavior, and clash foundation are preserved.
- Frozen Heritage engine JS/CSS and approved assets were not modified.
## Gate 16.9 R6 — Heritage Standard Neutral Clash Build

- The prior logo-driven Heritage clash direction is rejected and superseded.
- Heritage football clash now uses one reusable neutral black-and-white leather-helmet football illustration for every school.
- No team logo, mascot artwork, helmet mark, or school-specific image is used in the clash.
- Visitor/home identity is communicated entirely through live team name, mascot, record, and role typography.
- The clash remains inside the native `.hp-live-opening[data-video-mode="broadcast"]` Heritage story region.
- Venue metadata remains live-bound when available.
- Accepted Heritage Player Spotlight, Sponsor, Highlight, Sports Wire, score/game-state, and selected-game identity behavior are unchanged.
- Frozen Heritage engine JS/CSS remain untouched.
## Gate 16.9 R6 R2 — Heritage Full Video-Box Clash Build

- The prior logo-driven and text-heavy Heritage clash directions are rejected and superseded.
- Heritage football clash now uses one reusable neutral black-and-white leather-helmet football illustration as a full-frame plate inside the video box.
- No team logo, mascot artwork, helmet mark, or school-specific image is used in the clash.
- Visitor/home identity is no longer rendered inside the clash; the surrounding Heritage newspaper rails already carry matchup information.
- The clash remains inside the native `.hp-live-opening[data-video-mode="broadcast"]` Heritage story region.
- No interior venue or matchup copy is rendered inside the clash plate.
- Accepted Heritage Player Spotlight, Sponsor, Highlight, Sports Wire, score/game-state, and selected-game identity behavior are unchanged.
- Frozen Heritage engine JS/CSS remain untouched.
## Gate 16.9 R6 R4 — Heritage Clash Matches Player Highlight Frame

- Heritage Clash no longer maintains independent media geometry.
- The neutral clash artwork is mounted inside the exact accepted Heritage Player Highlight media-frame classes: `hp-highlight-window`, `csrn-production-native-video-mode`, and `csrn-production-heritage-highlight-window`.
- The clash image also inherits the accepted `csrn-production-highlight-video` media contract, with a clash-specific `object-fit: cover` override.
- No team names, logos, records, captions, or venue copy are rendered inside the clash.
- The Gridiron Dispatch / surrounding Heritage newspaper rails continue to carry matchup information.
- Accepted Player Spotlight, Sponsor, Highlight, Sports Wire, and game-state behavior are unchanged.
- Frozen Heritage engine JS/CSS remain untouched.
## Gate 16.9 R7 — Heritage Highlight Grayscale Finish

- Heritage Player Highlight video is now forced to black-and-white in the browser with CSS `grayscale(100%)` and a restrained `contrast(1.05)` adjustment.
- The change is scoped to the Heritage Press highlight window only.
- No video transcoding, duplicated media, codec changes, or source-file conversion is required.
- Heritage Clash, Player Spotlight, Sponsor, Sports Wire, game state, and frozen Heritage engine files are unchanged.
## Gate 16.9 R8 — Heritage Newsprint Media Tone Finish

- Heritage Player Spotlight image, Player Highlight video, and neutral Clash artwork now use a common paper-toned newsprint treatment.
- Media is converted in-browser with grayscale plus restrained sepia/contrast/brightness and `mix-blend-mode: multiply` against the Heritage paper background.
- The result preserves dark ink while shifting white/light regions toward the page's cream newsprint color instead of hard digital white.
- Player Highlight still requires no transcoding, media duplication, or codec changes.
- Sponsor artwork remains full color and normal blend.
- Clash geometry, Player Spotlight layout, Sponsor geometry, Sports Wire, score/game state, and frozen Heritage engine files are unchanged.
## Gate 16.9 R9 — Heritage Readability Finish

- Increased Gridiron Dispatch editorial copy size and line height for better readability in OBS preview and Facebook/mobile playback.
- Increased Sports Wire title, ticker copy, and page-id text size while preserving the approved Heritage newspaper structure.
- Preserved the approved Heritage clash frame, spotlight layout, sponsor layout, and R8 newsprint media tone.
- No frozen engine files, geometry foundations, or non-Heritage themes were changed.
## Gate 17.0 R1 R2 — 8-Bit Dynamic Clash Production Binding

- The frozen 8-Bit football clash renderer remains the visual source of truth; no replacement clash artwork was introduced.
- Production now explicitly preserves 8-Bit `clash` as the native idle/default center-board mode.
- The existing frozen 8-Bit material recoloring continues to bind the visitor player to visitor team colors and the home player to home team colors from the selected broadcast identity.
- Highlight, Sponsor, and Player modes continue to temporarily own the native center board and return to Clash when dismissed.
- Production runtime does not duplicate or mutate the frozen 8-Bit `paintClash` / material-decomposition implementation.
- No frozen 8-Bit engine or asset files were modified.
- R2 supersedes the stale Heritage Gate 16.9 R2 ternary-expression assertion with the equivalent explicit per-theme default-mode contract.
## Gate 17.0 R1 R3 — 8-Bit Athlete Asset Path Fix

- Corrected the production-only URL resolution mismatch for frozen 8-Bit JavaScript athlete image loads.
- Document-relative 8bit-gameday/... image URLs are normalized to Flask's /static/8bit-gameday/... tree by the generic production runtime.
- Frozen 8-Bit engine code, recolor masks/thresholds, geometry, and canonical athlete art remain unchanged.
- Canonical football, basketball, baseball, and softball athlete PNGs are guarded and recovered only if absent.
## Gate 17.0 R2 — 8-Bit Lower Data Readability Polish

- Increased the production 8-Bit football Clock value from 44 px to 66 px and Quarter/Down/To Go values from 38 px to 57 px.
- Tightened the production LED glow to improve crispness after OBS and social-media compression.
- Possession, Ball On, team scores, dynamic clash players/recoloring, athlete asset routing, frozen engine geometry, and other themes are unchanged.
## Gate 17.1 R1 — Friday Night Stadium Dynamic Clash Production Ready

- Production now waits for the frozen Friday Night Stadium dynamic clash render to finish before accepting the clash board.
- The native football athlete canvas must report art-ready and continue using the frozen visitor/home primary-color recolor pipeline.
- Existing football keyed-athlete, field-background, and VS assets are required but are not modified.
- Highlight, Sponsor, Player Spotlight, ticker, scorebug, and game-state geometry remain unchanged.
## Gate 17.1 R2 R2 — Friday Night Layered Dynamic Clash Players

- Replaces the production-visible keyed cyan/magenta uniform recolor result with a production-owned layered compositor while preserving the frozen Friday Night Stadium engine and geometry.
- Football clash athletes are decomposed into neutral anatomical/equipment detail, visitor/home primary uniform masks, visitor/home secondary helmet masks, and a shared grayscale uniform texture layer.
- Visitor and home primary and secondary team colors are applied only through the masks, then neutral texture/detail is restored so fabric contours and lighting remain intact.
- Highlight, Sponsor, Player Spotlight, ticker, scorebug, field background, VS mark, team labels, and frozen Stadium engine files are unchanged.
## Gate 17.1 R3 — Friday Night Uniform Detail Polish

- Preserves the production-owned layered Friday Night clash compositor while enhancing the secondary-color masks with visible trim detail.
- Adds secondary-color shoulder/sleeve stripes, pant striping, and generic jersey-number treatment to reduce the flat solid-color look.
- Keeps the frozen Friday Night Stadium engine, geometry, field background, and clash host unchanged.
- Advances runtime binding to v40 and cache pins to 17.1-r3 so the refreshed layer assets are loaded.
## Gate 17.1 R4 — Friday Night Integrated Uniform Detail Polish

- Preserves the production-owned layered Friday Night clash compositor while refining the secondary-color trim so it reads as part of the fabric rather than a pasted decal.
- Narrows and softens the generic jersey numbers and stripe accents, and slightly reduces trim intensity for better visual integration at Facebook/mobile viewing sizes.
- Keeps the frozen Friday Night Stadium engine, geometry, field background, and clash host unchanged.
- Advances runtime binding to v41 and cache pins to 17.1-r4 so the refreshed layered assets are loaded.
## Gate 17.1 R5 — Friday Night Perspective Uniform Remap

- Preserves the production-owned layered Friday Night clash compositor while remapping the secondary-color trim to more natural shoulder, chest, and side-seam locations.
- Re-centers the generic jersey numbers and differentiates visitor and home accent placement so both uniforms feel intentionally designed instead of identically templated.
- Keeps the frozen Friday Night Stadium engine, geometry, field background, and clash host unchanged.
- Advances runtime binding to v42 and cache pins to 17.1-r5 so the refreshed layered assets are loaded.
## Gate 17.1 R6 — Friday Night Reference Placement Rebuild

- Rebuilds Friday Night secondary-detail placement from the supplied football-uniform references: sleeve/shoulder bands, true outer pant seams, and chest-centered numbers.
- Uses different visitor and home stripe layouts so the two players no longer look like the same template recolored twice.
- Keeps the frozen Friday Night Stadium engine, geometry, field background, and clash host unchanged.
- Advances runtime binding to v43 and cache pins to 17.1-r6 so the refreshed layered assets are loaded.
## Gate 17.1 R7 — Friday Night Clean Layered Visual Rollback

- Restores the accepted Gate 17.1 R2 clean layered football player masks and compositor presentation.
- Removes the R3-R6 stripe/number visual experiments while preserving the later production binding, asset loading, and native media ownership work.
- Keeps the frozen Friday Night Stadium engine, geometry, field background, VS treatment, and other production media modes unchanged.
- Advances runtime binding to v44 and cache pins to 17.1-r7 to force the restored visual assets to reload.
