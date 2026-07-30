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

- The overlay still uses `/static/csrn-logo.png` as a final automatic fallback for player portraits and team watermarks.
- The Command Center player preview also falls back to the CSRN logo.
- Unrelated CSRN branding must not automatically replace a missing player or school identity.

Required fallback order:

Player portrait area:

1. Player headshot
2. Selected player’s team logo
3. Neutral player silhouette

Team watermark area:

1. Selected player’s team/school logo
2. School monogram
3. Neutral blank treatment

### 8.3 Roster headshot visibility

The roster list currently displays:

- jersey number;
- player name;
- position;
- class;
- active/inactive status.

It does not display:

- headshot thumbnail;
- team-logo fallback;
- explicit missing-headshot indicator.

This must be corrected so operators can verify player media without opening each record.

### 8.4 Obsolete headshot utility

Resolved in Gate 1: the obsolete standalone headshot utility was removed after
the integrated player-edit upload path was retained.

### 8.5 Player-event visual defects

- Event-label color is derived from team accent color and can become unreadable on dark treatments.
- Event label, player name, and supporting details require explicit independent spacing.
- Long player names need shrink/wrap containment.
- `pg-onair-play-detail` is populated but has no CSS rule.
- Missing and invalid media states require visual regression coverage.

### 8.6 Duplicate HTML IDs

The active Command Center contains duplicate IDs for the school-import interface:

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

These must be made unique.

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
6. Player Highlight using the existing Player Identification Card.
7. Team-filtered player selection for Player Highlight.
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

### Gate 5 — Complete frozen football scope

- regional data and record rules;
- special-game designations;
- Player Highlight;
- tests and documentation.

Exit condition: approved football scope is complete.

### Gate 6 — Visual regression

Render and approve:

- home and visitor teams;
- headshot present/missing;
- school logo present/missing;
- short and long names;
- touchdown, turnover, field goal, player highlight, and Player of the Game;
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
